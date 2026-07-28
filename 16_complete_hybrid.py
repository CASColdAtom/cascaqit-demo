"""运行完整 Hybrid 示例：理想执行、噪声执行、参数扫描和噪声参数扫描。"""

from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from cascaqit import AHSProgram, AtomRegister, Circuit, Waveform, visualize
from cascaqit.hybrid import HybridProgram
from cascaqit.parameters import ParameterScan
from cascaqit.simulators import (
    LocalBackend,
    NoiseChannel,
    NoiseModel,
    SimulationOptions,
)

# 每个单点或扫描点采样 256 次。
SHOTS = 256
# 所有本地执行使用同一个固定随机种子。
SEED = 2031
# 3x3 原子阵列和两个 Digital 区块都使用九个逻辑位点。
SITE_COUNT = 9


class DemoExecution:
    """集中保存四类执行结果，供终端摘要和 HTML 报告共同使用。"""

    # 限定实例字段，避免 Demo 容器意外增加未追踪属性。
    __slots__ = ("program", "ideal", "noisy", "sweep", "noisy_sweep", "payload")

    def __init__(
        self,
        *,
        program: HybridProgram,
        ideal: Any,
        noisy: Any,
        sweep: Any,
        noisy_sweep: Any,
        payload: dict[str, Any],
    ) -> None:
        # 保存未绑定的共享参数程序，生成报告时可按需要重新绑定。
        self.program = program
        # 保存 theta=0 的理想单点 ResultIR。
        self.ideal = ideal
        # 保存 theta=0 的物理噪声单点 ResultIR。
        self.noisy = noisy
        # 保存三个 theta 点的理想 ScanResultIR。
        self.sweep = sweep
        # 保存三个 theta 点的噪声 ScanResultIR。
        self.noisy_sweep = noisy_sweep
        # 保存适合终端输出的轻量摘要。
        self.payload = payload


def build_program() -> HybridProgram:
    """创建由四类执行共同复用的参数化 D-A-D 程序。"""
    # 创建九量子比特的 Digital 准备区块。
    prepare = Circuit(SITE_COUNT, program_id="demo.physical.prepare")
    # 声明共享参数 theta，范围限制为 [-0.8, 0.8]。
    theta = prepare.parameter("theta", lower_bound=-0.8, upper_bound=0.8)
    # q0、q1 建立 Bell 风格关联，再在 q1 上应用参数化 RZ。
    prepare.h(0).cx(0, 1).rz(theta, 1)

    # 创建 3x3 阵列的 Analog 演化区块。
    analog = AHSProgram(
        AtomRegister.square(side=3, spacing=5.0),
        program_id="demo.physical.evolve",
    )
    # 添加持续 0.1 的全局驱动波形。
    analog.drive(
        # Rabi 经过上升和回落三个采样点。
        rabi=Waveform.piecewise_linear(
            times=(0.0, 0.05, 0.1),
            values=(0.1, 0.8, 0.2),
        ),
        # Detuning 在完整时长内从 -0.3 线性变化到 0.2。
        detuning=Waveform.linear(-0.3, 0.2, duration=0.1),
        # 全局相位固定为 0.12。
        phase=0.12,
    )

    # 创建末段 Digital 修正区块。
    correct = Circuit(SITE_COUNT, program_id="demo.physical.correct")
    # 在修正区块中声明同名 theta，使两个 Digital 区块共享绑定值。
    correction = correct.parameter("theta", lower_bound=-0.8, upper_bound=0.8)
    # 先应用 -theta 抵消准备旋转，再反向执行 CX 和 H。
    correct.rz(-correction, 1).cx(0, 1).h(0)
    # 按准备、演化、修正、测量的顺序构造完整 HybridProgram。
    return (
        HybridProgram("demo.complete.physical.hybrid")
        .digital("prepare", prepare)
        .analog("evolve", analog)
        .digital("correct", correct)
        .measure_all(key="readout")
    )


def build_noise() -> NoiseModel:
    """创建包含八类可执行噪声通道的物理噪声模型。"""
    # NoiseModel 的 ID 会进入 ResultIR 中的 noise_report。
    return NoiseModel(
        "noise.demo.complete",
        (
            # 初态制备错误概率。
            NoiseChannel.preparation(0.01),
            # Analog 演化期间的退相干强度。
            NoiseChannel.dephasing(0.25),
            # Digital 门错误概率。
            NoiseChannel.gate(0.008),
            # 空闲期间的噪声强度和持续时间。
            NoiseChannel.idle(0.08, duration=0.01),
            # q0、q1 在全部控制区块中的串扰配置。
            NoiseChannel.crosstalk(
                0.04,
                duration=0.02,
                targets=("q0", "q1"),
                schedule_ref="all_control_blocks",
            ),
            # Digital/Analog 区块交界处的状态交接噪声。
            NoiseChannel.boundary(0.015),
            # q1 的原子丢失概率。
            NoiseChannel.atom_loss(0.02, targets=("q1",)),
            # 读出时 0→1 和 1→0 的分类错误概率。
            NoiseChannel.readout(0.025, p10=0.035),
        ),
    )


def execute_demo() -> DemoExecution:
    """离线完成编译、理想执行、噪声执行和两类参数扫描。"""
    # 构造四类执行共用的未绑定参数化程序。
    program = build_program()
    # 在运行前编译程序，生成区块拓扑和执行计划。
    compiled = program.compile()
    # graph 或 plan 为空表示编译失败，必须保留全部诊断。
    if compiled.graph is None or compiled.plan is None:
        raise RuntimeError([item.to_dict() for item in compiled.diagnostics])
    # 创建固定种子和八个 Analog 时间步的本地后端。
    backend = LocalBackend(seed=SEED, analog_time_steps=8)
    # 构造后续噪声单点和噪声扫描共用的 NoiseModel。
    noise_model = build_noise()
    # 执行路径 1：theta=0 的理想本地运行。
    ideal = backend.run(
        # 直接提交未绑定程序，由 params 完成本次绑定。
        program,
        # theta=0 作为理想与噪声对照的共同参数点。
        params={"theta": 0.0},
        # 使用文件顶部固定的采样次数。
        shots=SHOTS,
        # complex64 可降低九位点示例开销，同时仍经过完整阵列和状态交接路径。
        options=SimulationOptions(
            integrator="fixed_step_krylov",
            dtype="complex64",
            max_steps=8,
        ),
    ).result()
    # 执行路径 2：同一个 theta=0 程序叠加八通道物理噪声。
    noisy = backend.run(
        program,
        params={"theta": 0.0},
        # 噪声模型只影响本次运行，不会修改原始 HybridProgram。
        noise=noise_model,
        shots=SHOTS,
        # 噪声运行使用 256 条轨迹估计采样统计量。
        options=SimulationOptions(
            integrator="fixed_step_krylov",
            trajectories=256,
            max_steps=8,
            seed=SEED,
        ),
    ).result()
    # 定义理想扫描和噪声扫描共同使用的三个 theta 参数点。
    scan = ParameterScan.explicit(
        scan_id="scan.demo.theta",
        points=tuple({"theta": value} for value in (-0.6, 0.0, 0.6)),
    )
    # 执行路径 3：不加噪声的三点参数扫描。
    sweep = backend.run(
        program,
        sweep=scan,
        shots=SHOTS,
        # continue_on_error 配合有界 worker pool；子任务完成顺序不影响结果顺序。
        options=SimulationOptions(
            dtype="complex64",
            integrator="fixed_step_krylov",
            max_steps=8,
            workers="auto",
            seed=SEED,
        ),
        failure_policy="continue_on_error",
    ).result()
    # 执行路径 4：在相同三个 theta 点上加入同一个物理噪声模型。
    noisy_sweep = backend.run(
        program,
        sweep=scan,
        noise=noise_model,
        shots=SHOTS,
        # 噪声扫描使用 trajectory 方法和 256 条轨迹。
        options=SimulationOptions(
            method="trajectory",
            integrator="fixed_step_krylov",
            trajectories=256,
            max_steps=8,
            workers="auto",
            seed=SEED,
        ),
        failure_policy="continue_on_error",
    ).result()
    # 把理想扫描成功项整理为 theta、counts 和 probabilities。
    sweep_rows = []
    # successful_items 只包含执行成功的扫描点。
    for item in sweep.successful_items:
        # 理论上成功项都应包含 ResultIR；缺失时跳过，保留扫描聚合状态。
        if item.result is None:
            continue
        # 保存当前参数点的绑定值和采样分布。
        sweep_rows.append(
            {
                "theta": item.bind_set.values["theta"],
                "counts": item.result.counts,
                "probabilities": item.result.probabilities,
            }
    )
    # 把噪声扫描成功项整理为 theta、counts、激发概率和 95% 置信区间。
    noisy_sweep_rows = []
    # 逐个读取噪声扫描成功项。
    for item in noisy_sweep.successful_items:
        # 缺少 ResultIR 的成功项不参与终端摘要。
        if item.result is None:
            continue
        # 保存当前点的观测量及其置信区间。
        noisy_sweep_rows.append(
            {
                "theta": item.bind_set.values["theta"],
                "counts": item.result.counts,
                "excitation": item.result.observables[
                    "first_site_excitation_probability"
                ],
                "ci95": (
                    item.result.observables["first_site_excitation_ci95_low"],
                    item.result.observables["first_site_excitation_ci95_high"],
                ),
            }
        )
    # 汇总编译哈希、四类结果、资源记录和本地执行限制。
    payload = {
        "example": "complete_physical_hybrid_demo",
        "compile": {
            "program_hash": program.stable_hash(),
            "graph_hash": compiled.graph.stable_hash(),
            "plan_hash": compiled.plan.stable_hash(),
            "parameter_schema_hash": program.parameters.schema.stable_hash(),
            "parameter_targets": len(program.parameters.targets),
            "block_order": list(compiled.graph.topological_order),
        },
        "ideal": _result_summary(ideal),
        "noisy": _result_summary(noisy),
        "sweep": sweep_rows,
        "sweep_execution_config": sweep.metadata["simulation_execution_config"],
        "sweep_resource_plan": sweep.metadata["scan_resource_plan"],
        "sweep_resource_usage": sweep.metadata["simulation_resource_usage"],
        "noisy_sweep": noisy_sweep_rows,
        "noisy_sweep_execution_config": noisy_sweep.metadata[
            "simulation_execution_config"
        ],
        "noisy_sweep_resource_plan": noisy_sweep.metadata["scan_resource_plan"],
        "noisy_sweep_resource_usage": noisy_sweep.metadata["simulation_resource_usage"],
        "boundaries": {
            "offline_deterministic": True,
            "network_accessed": False,
            "hardware_execution": False,
            "cloud_execution": False,
            "cascaqit_compat_required": False,
        },
        # 顶层同时保留通用限制字段，方便自动检查所有用户示例。
        "network_accessed": False,
        "credentials_loaded": False,
    }
    # 返回包含完整 IR 对象和轻量 payload 的容器。
    return DemoExecution(
        program=program,
        ideal=ideal,
        noisy=noisy,
        sweep=sweep,
        noisy_sweep=noisy_sweep,
        payload=payload,
    )


def run_demo() -> dict[str, Any]:
    """供其他 Python 代码调用，并只返回终端摘要字典。"""
    # 执行完整流程，但不在这里生成 HTML 报告。
    return execute_demo().payload


def _result_summary(result: Any) -> dict[str, Any]:
    """从单点 ResultIR 中选择终端要显示的执行和物理字段。"""
    # simulation_plan 记录模拟器实际选择的方法和精度。
    plan = result.metadata["simulation_plan"]
    # execution_config() 返回本次执行的规范化配置对象。
    execution_config = result.execution_config()
    # 本地后端结果必须保留执行配置，否则无法准确复盘。
    if execution_config is None:
        raise RuntimeError("LocalBackend ResultIR has no execution configuration.")
    # 返回采样、观测量、资源、状态交接和噪声报告。
    return {
        "counts": result.counts,
        "probabilities": result.probabilities,
        "observables": result.observables,
        "method": plan["method_selected"],
        "dtype": plan["dtype"],
        "execution_config": execution_config.to_dict(),
        "estimated_peak_bytes": result.metadata["simulation_resource_estimate"][
            "estimated_peak_bytes"
        ],
        "resource_usage": result.metadata["simulation_resource_usage"],
        "truthfulness": result.metadata["simulation_truthfulness"],
        "state_hash": result.metadata.get("state_hash"),
        "state_chain": [
            transition.to_dict() for transition in result.state_transitions()
        ],
        "noise_report": result.metadata.get("noise_report"),
    }


def main(output: Path | None = None) -> None:
    """执行完整 Demo，并在提供路径时生成四份标准报告。"""
    # 一次执行同时得到程序、四类结果和终端摘要。
    execution = execute_demo()
    # payload 会在生成报告后补充报告路径和哈希。
    payload = execution.payload
    # 未传 --output 时只打印终端摘要，不写任何 HTML。
    if output is not None:
        # 展开用户目录并规范化为绝对路径。
        resolved = output.expanduser().resolve()
        # 自动创建主报告所在目录。
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # 单结果报告需要绑定后的程序作为设计上下文；聚合报告直接读取各自结果。
        bound_program = execution.program.bind({"theta": 0.0})
        # 三份聚合报告在主文件名后追加不同后缀。
        comparison_path = resolved.with_name(f"{resolved.stem}_comparison.html")
        sweep_path = resolved.with_name(f"{resolved.stem}_sweep.html")
        noisy_sweep_path = resolved.with_name(f"{resolved.stem}_noisy_sweep.html")
        # 从已经完成的结果生成主报告、理想/噪声比较和两份扫描报告。
        reports = {
            "hybrid": visualize(
                execution.noisy,
                program=bound_program,
                output=resolved,
                title="Complete physical Hybrid experiment",
            ),
            "comparison": visualize(
                {"ideal": execution.ideal, "noisy": execution.noisy},
                output=comparison_path,
                title="Ideal and physical-noise comparison",
            ),
            "sweep": visualize(
                execution.sweep,
                output=sweep_path,
                title="Ideal Hybrid parameter sweep",
            ),
            "noisy_sweep": visualize(
                execution.noisy_sweep,
                output=noisy_sweep_path,
                title="Physical-noise Hybrid parameter sweep",
            ),
        }
        # 在终端摘要中保存主报告路径。
        payload["visualization_path"] = str(resolved)
        # 为四份报告记录路径、profile、稳定哈希和来源哈希。
        payload["visualizations"] = {
            name: {
                "path": str(path),
                "profile": reports[name].profile,
                "report_hash": reports[name].stable_hash(),
                "html_hash": reports[name].html_hash(),
                "source_hashes": reports[name].to_dict()["source_hashes"],
            }
            for name, path in (
                ("hybrid", resolved),
                ("comparison", comparison_path),
                ("sweep", sweep_path),
                ("noisy_sweep", noisy_sweep_path),
            )
        }
    # 使用排序后的 JSON 输出，方便保存日志和自动比较。
    print(json.dumps(payload, sort_keys=True))


def _cli_output_path() -> Path | None:
    """读取可选 --output，同时不消费外层运行器的其他参数。"""
    # 创建只包含本脚本参数的解析器。
    parser = ArgumentParser()
    # 不提供 --output 时，脚本只打印 JSON，不写报告。
    parser.add_argument("--output", type=Path)
    # parse_known_args 允许 Notebook 或测试运行器附加其他参数。
    arguments, _ = parser.parse_known_args()
    # 返回有效 Path；未提供时返回 None。
    return arguments.output if isinstance(arguments.output, Path) else None


if __name__ == "__main__":
    # 直接运行脚本时解析输出路径并执行完整示例。
    main(_cli_output_path())
