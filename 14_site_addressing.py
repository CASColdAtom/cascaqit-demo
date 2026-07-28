"""运行一个包含时变局域寻址的 3x3 Hybrid 实验。"""

from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from cascaqit import (
    AHSProgram,
    AtomRegister,
    Circuit,
    HybridProgram,
    LocalBackend,
    SimulationOptions,
    SiteMask,
    Waveform,
    visualize,
)

# 每次本地执行采样 64 次。
SHOTS = 64
# 固定后端和数值模拟随机种子。
SEED = 37
# 3x3 阵列共有九个原子位点。
SITE_COUNT = 9
# 未指定 --output 时使用的默认 HTML 报告路径。
DEFAULT_REPORT = (
    Path("examples/user/assets") / "time_dependent_site_addressing_report.html"
)


def build_program() -> HybridProgram:
    """创建包含两套独立局域寻址时序的 D-A-D 程序。"""
    # 两套局域控制和全局驱动都持续 0.6 时间单位。
    duration = 0.6
    # 创建 Analog 区块，并链式添加全局和局域控制。
    analog = (
        # 3x3 正方形阵列的位点间距为 12.0。
        AHSProgram(
            AtomRegister.square(side=3, spacing=12.0),
            program_id="demo.dynamic_addressing.evolve",
        )
        # 添加全局 Rabi、detuning 和 phase 波形。
        .drive(
            # Rabi 在完整时长内从 0.2 线性增加到 0.7。
            rabi=Waveform.linear(0.2, 0.7, duration=duration),
            # Detuning 在完整时长内从 -0.3 线性增加到 0.2。
            detuning=Waveform.linear(-0.3, 0.2, duration=duration),
            # Phase 在 0.3 时由 0.0 跳变到 0.2。
            phase=Waveform.piecewise_constant(
                times=(0.0, 0.3, duration),
                values=(0.0, 0.2, 0.2),
                value_unit="rad",
            ),
        )
        # 第一套局域控制：对选中位点施加局域 detuning。
        .local_detuning(
            # 所有被选中位点共用强度 0.45 的常量波形。
            waveform=Waveform.constant(0.45, duration=duration),
            # Move local detuning from the corners to the center cross.
            pattern=SiteMask.piecewise(
                duration=duration,
                frames=(
                    (0.0, ("q0", "q2", "q6", "q8")),
                    (0.3, ("q1", "q3", "q4", "q5", "q7")),
                ),
            ),
        )
        # 第二套局域控制：独立设置局域 Rabi 和 phase。
        .local_rabi(
            # 被选中位点使用强度 0.35 的常量 Rabi。
            rabi=Waveform.constant(0.35, duration=duration),
            # 局域 Rabi 的基础相位为 0.15。
            phase=0.15,
            # The middle frame disables every locally addressed site.
            pattern=SiteMask.piecewise(
                duration=duration,
                frames=(
                    (0.0, ("q4",)),
                    (0.2, ()),
                    (0.4, ("q0", "q8")),
                ),
            ),
        )
    )
    # 创建九量子比特的 Digital 准备区块。
    prepare = Circuit(SITE_COUNT, program_id="demo.dynamic_addressing.prepare")
    # 在中心 q4 上制备叠加态，并与角落 q8 建立纠缠。
    prepare.h(4).cx(4, 8)
    # 创建末段 Digital 读出旋转区块。
    readout = Circuit(SITE_COUNT, program_id="demo.dynamic_addressing.readout")
    # 在 q0 和 q8 上施加不同轴的末段旋转。
    readout.ry(0.2, 0).rz(-0.1, 8)
    # 按准备、演化、读出、测量的顺序组合完整 HybridProgram。
    return (
        HybridProgram("demo.time_dependent_site_addressing")
        .digital("prepare", prepare)
        .analog("evolve", analog)
        .digital("readout", readout)
        .measure_all(key="readout")
    )


def run(output: Path = DEFAULT_REPORT) -> dict[str, Any]:
    """本地执行程序、保存标准报告，并返回可检查字段。"""
    # 构造包含两套时变局域寻址的 Hybrid 程序。
    program = build_program()
    # 编译程序以获得区块拓扑图、执行计划和结构化诊断。
    compilation = program.compile()
    # graph 或 plan 缺失表示编译失败，此时原样抛出诊断。
    if compilation.graph is None or compilation.plan is None:
        raise RuntimeError([item.to_dict() for item in compilation.diagnostics])

    # 用固定种子和八个 Analog 时间步在本地执行程序。
    result = LocalBackend(seed=SEED, analog_time_steps=8).run(
        # 提交已经编译检查过的 HybridProgram。
        program,
        # 使用文件顶部定义的固定采样次数。
        shots=SHOTS,
        # 显式配置积分器、数值精度、步数和随机种子。
        options=SimulationOptions(
            integrator="fixed_step_krylov",
            dtype="complex64",
            max_steps=8,
            seed=SEED,
        ),
    ).result()
    # 把用户给出的输出路径展开并转换为绝对路径。
    resolved_output = output.expanduser().resolve()
    # 自动创建报告所在目录。
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    # 从已完成的 ProgramIR 和 ResultIR 生成独立 HTML 报告。
    report = visualize(
        result,
        program=program,
        output=resolved_output,
        title="Time-dependent site addressing",
    )
    # 读取报告中的实验设计部分，检查寻址时间线。
    design = report.section("experiment.design").payload
    # 读取运行状态部分，检查模拟器实际消费的寻址计划。
    state = report.section("experiment.state").payload
    # 从 Analog 区块中提取两套 site addressing timeline。
    timelines = [
        item
        for block in design["blocks"]
        if block["block_type"] == "analog"
        for item in block["site_addressing_timeline"]
    ]
    # 获取运行阶段记录的动态寻址消费者。
    consumers = state["dynamic_addressing_consumers"]

    # 返回编译顺序、寻址哈希、采样结果和报告信息。
    return {
        "example": "time_dependent_site_addressing",
        "site_count": SITE_COUNT,
        "block_order": list(compilation.graph.topological_order),
        "addressing_hashes": [item["addressing_hash"] for item in timelines],
        "addressing_frame_counts": [item["frame_count"] for item in timelines],
        "runtime_consumers": sorted({item["consumer"] for item in consumers}),
        "runtime_hashes": [item["addressing_hash"] for item in consumers],
        "counts": result.counts,
        "counts_total": sum(result.counts.values()),
        "probability_sum": sum((result.probabilities or {}).values()),
        "report_profile": report.profile,
        "report_path": str(resolved_output),
        "report_hash": report.stable_hash(),
        "offline_deterministic": True,
        "hardware_execution": False,
        "cloud_execution": False,
        "network_accessed": False,
        "credentials_loaded": False,
    }


def main(output: Path = DEFAULT_REPORT) -> None:
    """运行实验，并打印一份按键排序的 JSON 摘要。"""
    # run() 负责执行和写报告，main() 只处理终端输出。
    print(json.dumps(run(output), sort_keys=True))


def _cli_output_path() -> Path:
    """读取 --output，同时忽略外层培训运行器可能附加的参数。"""
    # 创建只包含本脚本参数的解析器。
    parser = ArgumentParser()
    # --output 可覆盖默认 HTML 报告位置。
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    # parse_known_args 避免外层 Notebook 或测试参数导致解析失败。
    arguments, _ = parser.parse_known_args()
    # 类型符合预期时返回用户路径，否则安全回退到默认路径。
    return arguments.output if isinstance(arguments.output, Path) else DEFAULT_REPORT


if __name__ == "__main__":
    # 直接运行脚本时解析输出路径并执行完整示例。
    main(_cli_output_path())
