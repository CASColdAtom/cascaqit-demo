"""比较同一个带权独立集问题的四条本地执行路线。

2x2 图的节点权重不同，唯一精确解是选择 q0 和 q3，对应 bitstring ``1001``，
总权重为 9。脚本在本地依次执行 Digital QAOA、Digital VQE、Hybrid QAOA 和
Analog QAA，并为每条路线保存独立报告，最后生成一份比较报告。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from cascaqit.problems import MWISProblemIR, ProblemCompiler
from cascaqit.simulators import LocalBackend, SimulationOptions
from cascaqit.targets import MockNeutralAtomTarget
from cascaqit.visualization import visualize

# 固定随机种子，使四条路线的采样结果可以重复比较。
SEED = 2026
# 2x2 阵列相邻节点间距，单位为微米。
SPACING_UM = 6.0


def build_weighted_grid() -> MWISProblemIR:
    """创建一个最优解为两对角节点的 2x2 MWIS 问题。"""
    # from_edges 同时接收节点权重、冲突边和物理位置。
    return MWISProblemIR.from_edges(
        # problem_id 会进入规范化问题和后续编译结果。
        problem_id="mwis.problem-compiler.2x2-weighted-grid",
        # q0 与 q3 的权重和最大，为唯一最优独立集。
        node_weights={"q0": 5.0, "q1": 2.0, "q2": 3.0, "q3": 4.0},
        # 四条边只连接水平和垂直相邻节点。
        edges=(("q0", "q1"), ("q0", "q2"), ("q1", "q3"), ("q2", "q3")),
        # positions 为 Analog/Hybrid 路线提供物理布局提示。
        positions={
            "q0": (0.0, 0.0),
            "q1": (SPACING_UM, 0.0),
            "q2": (0.0, SPACING_UM),
            "q3": (SPACING_UM, SPACING_UM),
        },
    )


def _vqe_parameters(scale: float) -> dict[str, float]:
    """为内置单层 Ansatz 生成一个完整 VQE 参数点。"""
    # 每个参数点必须包含四个量子比特的 RY 和 RZ 角度。
    values: dict[str, float] = {}
    # 逐个量子比特生成与内置 Ansatz 命名一致的参数。
    for qubit in range(4):
        # RY 角度按量子比特序号递增，形成可区分的初始点。
        values[f"ry_0_{qubit}"] = scale * (qubit + 1)
        # 本例把所有 RZ 初始角固定为 0。
        values[f"rz_0_{qubit}"] = 0.0
    # 返回可直接传给 optimize(parameter_sets=...) 的完整字典。
    return values


def run_demo(
    *,
    output_dir: Path,
    shots: int,
    language: Literal["en", "zh"],
) -> dict[str, object]:
    """执行四条 MWIS 路线，并保存可检查的 HTML 报告。"""
    # 先创建报告目录，parents=True 允许自动创建缺失的上级目录。
    output_dir.mkdir(parents=True, exist_ok=True)
    # 构造唯一最优解已知的 2x2 MWIS 问题。
    problem = build_weighted_grid()
    # 使用公开的本地 AHS 模拟目标，不连接真实设备。
    target = MockNeutralAtomTarget.local_ahs_v0_1()
    # ProblemCompiler 负责 analyze、compile 和 decode 所需的统一流程。
    compiler = ProblemCompiler()
    # 先分析问题与目标的可行性，再决定各模式是否可以编译。
    analysis = compiler.analyze(problem, target=target)
    # 四条路线共用一个固定配置的本地后端，确保比较条件一致。
    backend = LocalBackend(
        # 固定后端采样随机种子。
        seed=SEED,
        # Analog 和 Hybrid 路线按同一个目标约束执行。
        target=target,
        # 用较小时间步数控制 Demo 的运行时间。
        analog_time_steps=8,
        # 固定时间戳，避免报告哈希随运行时间变化。
        created_at="2026-07-25T00:00:00+00:00",
    )
    # Analog 和 Hybrid 路线使用相同的数值积分配置。
    analog_options = SimulationOptions(
        # complex64 可减少这个小规模示例的内存占用和运行时间。
        dtype="complex64",
        # 使用固定步长 Krylov 积分器，保证离线确定性。
        integrator="fixed_step_krylov",
        # 上限与 backend 的 analog_time_steps 保持一致。
        max_steps=8,
        # 数值模拟同样固定随机种子。
        seed=SEED,
    )

    # Each route receives two concrete points. This is a deterministic route
    # comparison, not a claim that a two-point scan finds optimal parameters.
    # 每条路线都指定编译模式、算法和两个待评估参数点。
    configurations = {
        "digital_qaoa": (
            "digital",
            "qaoa",
            (
                {"gamma_0": 0.16, "beta_0": 0.24},
                {"gamma_0": 0.28, "beta_0": -0.18},
            ),
        ),
        "digital_vqe": (
            "digital",
            "vqe",
            (_vqe_parameters(0.12), _vqe_parameters(0.24)),
        ),
        "hybrid_qaoa": (
            "hybrid",
            "qaoa",
            (
                {"gamma_0": 0.16, "beta_0": 0.24},
                {"gamma_0": 0.28, "beta_0": -0.18},
            ),
        ),
        "analog_qaa": (
            "analog",
            "qaa",
            (
                {"anneal_time": 1.0, "omega_max": 1.0},
                {"anneal_time": 1.2, "omega_max": 1.0},
            ),
        ),
    }

    # route_summaries 保存终端需要打印的每条路线摘要。
    route_summaries: dict[str, object] = {}
    # report_paths 记录四份单路报告和一份比较报告的位置。
    report_paths: dict[str, str] = {}
    # executions 保留完整执行对象，供 visualize 构建跨路线比较报告。
    executions = {}
    # 逐条执行配置中的 Digital、Hybrid 和 Analog 路线。
    for route, (mode, algorithm, parameter_sets) in configurations.items():
        # 把同一个 MWIS 问题编译为当前模式和算法对应的程序。
        compiled = compiler.compile(
            problem,
            mode=mode,
            algorithm=algorithm,
            target=target,
        )
        # 对两个给定参数点进行本地评估，并选择观测到的最佳结果。
        execution = compiled.optimize(
            # parameter_sets 明确限定本次比较只评估两个点。
            parameter_sets=parameter_sets,
            # 每个参数点使用调用方指定的 shots。
            shots=shots,
            # 固定优化评估中的随机采样。
            seed=SEED,
            # 所有路线共用同一个本地后端。
            backend=backend,
            # Digital 路线不需要 Analog 数值积分配置。
            options=None if mode == "digital" else analog_options,
        )
        # 每条路线写入独立 HTML，文件名包含 route 便于区分。
        output = output_dir / f"problem_mwis_{route}.html"
        # report() 从已完成执行中生成报告，不会重新运行程序。
        report = execution.report(output, language=language)
        # 读取这条路线实际观测到的最佳候选解。
        best = execution.best_observed_candidate
        # 汇总编译哈希、采样数量、目标值和最佳候选解。
        route_summaries[route] = {
            "compile_hash": compiled.compile_hash,
            "counts_total": sum(execution.result.counts.values()),
            "evaluation_count": len(execution.parameter_history),
            "objective_value": execution.objective_value,
            "best_bitstring": best.bitstring,
            "best_feasible": best.feasible,
            "best_selected_weight": best.decoded["selected_weight"],
            "expected_selected_weight": execution.parameter_history[
                execution.selected_evaluation_index
            ].expected_selected_weight,
            "report_profile": report.profile,
        }
        # 保存当前路线报告的字符串路径。
        report_paths[route] = str(output)
        # 用易读标签保存完整 execution，作为比较报告的数据源。
        executions[f"{mode.title()} {algorithm.upper()}"] = execution

    # 四条路线完成后，生成一份并排比较的 HTML 报告。
    comparison_output = output_dir / "problem_mwis_route_comparison.html"
    # visualize 接收 execution 映射，并从已有结果派生比较视图。
    visualize(
        executions,
        output=comparison_output,
        title="2x2 MWIS route comparison",
        language=language,
    )
    # 把比较报告也加入最终返回的路径清单。
    report_paths["route_comparison"] = str(comparison_output)

    # 所有路线共享同一个精确基线，取第一条 execution 即可。
    baseline = next(iter(executions.values())).baseline
    # 该问题规模支持精确基线；缺失时应立即暴露异常。
    assert baseline is not None
    # 返回问题、基线、模式可行性、路线结果和本地执行声明。
    return {
        "example": "problem_compiler_mwis",
        "problem_hash": analysis.canonical_problem.problem_hash,
        "target_id": target.target_id,
        "node_weights": dict(problem.node_weights),
        "baseline_bitstring": baseline.bitstring,
        "baseline_selected_weight": -baseline.objective_value,
        "mode_feasibility": {
            item.mode: item.feasible for item in analysis.mapping_plan.feasibility
        },
        "routes": route_summaries,
        "reports": report_paths,
        "offline_deterministic": True,
        "hardware_execution": False,
        "cloud_execution": False,
        "network_accessed": False,
        "credentials_loaded": False,
    }


def parse_args() -> argparse.Namespace:
    """解析输出目录、shots 和报告语言三个命令行参数。"""
    # 创建命令行解析器，并在 --help 中说明脚本用途。
    parser = argparse.ArgumentParser(
        description="Run one MWIS through every unified Problem compile route."
    )
    # --output-dir 决定五份 HTML 报告的保存目录。
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/problem_compiler_mwis"),
        help="Directory for four route reports and one comparison report.",
    )
    # --shots 控制每个参数点的采样次数。
    parser.add_argument("--shots", type=int, default=32)
    # --language 只允许报告渲染器支持的英文或中文。
    parser.add_argument("--language", choices=("en", "zh"), default="zh")
    # 返回完整解析结果供 main 使用。
    return parser.parse_args()


def main() -> None:
    """校验命令行参数，执行四条路线并打印汇总字典。"""
    # 读取用户传入的输出目录、shots 和语言。
    args = parse_args()
    # shots 必须大于 0，否则采样执行没有意义。
    if args.shots <= 0:
        raise ValueError("--shots must be positive.")
    # 执行 Demo 并把结构化摘要打印到终端。
    print(
        run_demo(
            output_dir=args.output_dir,
            shots=args.shots,
            language=args.language,
        )
    )


if __name__ == "__main__":
    # 直接运行文件时进入命令行流程。
    main()
