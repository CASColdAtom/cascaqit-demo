"""把同一个 3x3 MIS 分别编译并运行在 Digital、Hybrid 和 Analog 模式。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

from cascaqit.problems import GraphProblemIR, ProblemCompiler
from cascaqit.simulators import LocalBackend, SimulationOptions
from cascaqit.targets import MockNeutralAtomTarget
from cascaqit.visualization import visualize

# 固定种子，使三条路线的本地采样结果可重复。
SEED = 2026
# 网格相邻节点间距，单位为微米。
SPACING_UM = 6.0


def build_grid_mis() -> GraphProblemIR:
    """创建带物理位置提示的 3x3 最近邻 MIS 图。"""
    # 按行生成 q0 到 q8 九个节点。
    nodes = tuple(f"q{row * 3 + column}" for row in range(3) for column in range(3))
    # 为每个节点生成二维坐标，供 Analog 映射和报告绘图使用。
    positions = {
        f"q{row * 3 + column}": (
            float(column) * SPACING_UM,
            float(row) * SPACING_UM,
        )
        for row in range(3)
        for column in range(3)
    }
    # edges 将只保存水平和垂直的最近邻冲突关系。
    edges = []
    # 遍历网格中的每一行。
    for row in range(3):
        # 遍历当前行中的每一列。
        for column in range(3):
            # 计算当前位置对应的节点名称。
            current = f"q{row * 3 + column}"
            # 非最右列节点与右侧邻居相连。
            if column < 2:
                edges.append((current, f"q{row * 3 + column + 1}"))
            # 非最下行节点与下方邻居相连。
            if row < 2:
                edges.append((current, f"q{(row + 1) * 3 + column}"))
    # 用统一 Problem IR 保存节点、边和物理位置。
    return GraphProblemIR.from_edges(
        problem_id="mis.problem-compiler.3x3-grid",
        nodes=nodes,
        edges=edges,
        positions=positions,
    )


def run_demo(
    *,
    output_dir: Path,
    shots: int,
    language: Literal["en", "zh"],
) -> dict[str, object]:
    """运行三种编译模式，并保存单路报告和路线比较报告。"""
    # 创建输出目录，允许自动补齐上级目录。
    output_dir.mkdir(parents=True, exist_ok=True)
    # 创建本地中性原子目标，供可行性分析和 Analog/Hybrid 编译使用。
    target = MockNeutralAtomTarget.local_ahs_v0_1()
    # 构造三条路线共享的 3x3 MIS 问题。
    problem = build_grid_mis()
    # ProblemCompiler 提供统一的 analyze、compile、optimize 和 decode 流程。
    compiler = ProblemCompiler()
    # 在编译前分析问题规范化结果、布局和各模式可行性。
    analysis = compiler.analyze(problem, target=target)
    # 三条路线共用同一个本地后端和固定时间戳。
    backend = LocalBackend(
        seed=SEED,
        target=target,
        analog_time_steps=8,
        created_at="2026-07-23T00:00:00+00:00",
    )
    # Analog 和 Hybrid 路线共用同一套轻量数值积分设置。
    options = SimulationOptions(
        dtype="complex64",
        integrator="fixed_step_krylov",
        max_steps=8,
        seed=SEED,
    )
    # 为三种模式指定算法和两个明确的参数点。
    configurations = {
        "digital": {
            "algorithm": "qaoa",
            "parameter_sets": (
                {"gamma_0": 0.16, "beta_0": 0.24},
                {"gamma_0": 0.28, "beta_0": -0.18},
            ),
        },
        "hybrid": {
            "algorithm": "qaoa",
            "parameter_sets": (
                {"gamma_0": 0.16, "beta_0": 0.24},
                {"gamma_0": 0.28, "beta_0": -0.18},
            ),
        },
        "analog": {
            "algorithm": "qaa",
            "parameter_sets": (
                {"anneal_time": 0.4, "omega_max": 1.0},
                {"anneal_time": 0.7, "omega_max": 1.4},
            ),
        },
    }
    # mode_summaries 保存终端输出所需的每种模式摘要。
    mode_summaries: dict[str, object] = {}
    # report_paths 保存三份单路报告和一份比较报告路径。
    report_paths: dict[str, str] = {}
    # executions 保存完整执行对象，供最后生成比较视图。
    executions = {}
    # 逐一编译并运行 Digital、Hybrid 和 Analog 配置。
    for mode, configuration in configurations.items():
        # 把统一 MIS 问题编译为当前模式对应的程序。
        compiled = compiler.compile(
            problem,
            mode=mode,
            algorithm=str(configuration["algorithm"]),
            target=target,
        )
        # 本地评估两个参数点，并选择本路线观测到的最佳结果。
        execution = compiled.optimize(
            parameter_sets=configuration["parameter_sets"],
            shots=shots,
            seed=SEED,
            backend=backend,
            options=None if mode == "digital" else options,
        )
        # 每种模式写入独立 HTML 报告。
        output = output_dir / f"problem_3x3_mis_{mode}.html"
        # 报告直接读取已完成的 execution，不会再次运行程序。
        report = execution.report(output, language=language)
        # 保存编译、运行、候选解和报告的关键字段。
        mode_summaries[mode] = {
            "compile_hash": compiled.compile_hash,
            "program_hash": execution.result.program_hash,
            "counts_total": sum(execution.result.counts.values()),
            "evaluation_count": len(execution.parameter_history),
            "selected_evaluation_index": execution.selected_evaluation_index,
            "objective_value": execution.objective_value,
            "best_bitstring": execution.best_observed_candidate.bitstring,
            "best_feasible": execution.best_observed_candidate.feasible,
            "report_profile": report.profile,
            "report_hash": report.html_hash(language=language),
        }
        # 记录当前模式的报告路径。
        report_paths[mode] = str(output)
        # 生成比较报告中显示的算法标签。
        algorithm_label = str(configuration["algorithm"]).upper()
        # 把完整 execution 放入比较报告的数据源字典。
        executions[f"{mode.title()} {algorithm_label}"] = execution

    # The comparison is a derived view over completed executions. It aligns the
    # shared Problem objective while keeping route-specific programs, budgets,
    # sampling, and resource evidence separate.
    comparison_output = output_dir / "problem_3x3_mis_route_comparison.html"
    # 基于三条已完成路线生成统一比较视图。
    visualize(
        executions,
        output=comparison_output,
        title="3x3 MIS route comparison",
        language=language,
    )
    # 把比较报告加入返回路径清单。
    report_paths["route_comparison"] = str(comparison_output)

    # 返回问题分析、每条路线结果、报告路径和本地执行说明。
    return {
        "example": "problem_compiler_3x3_mis",
        "problem_hash": analysis.canonical_problem.problem_hash,
        "analysis_hash": analysis.analysis_hash,
        "target_id": target.target_id,
        "layout_policy": analysis.mapping_plan.layout.layout_policy,
        "site_count": len(analysis.mapping_plan.layout.sites),
        "mode_feasibility": {
            item.mode: item.feasible for item in analysis.mapping_plan.feasibility
        },
        "modes": mode_summaries,
        "reports": report_paths,
        "offline_deterministic": True,
        "hardware_execution": False,
        "cloud_execution": False,
        "network_accessed": False,
        "credentials_loaded": False,
    }


def parse_args() -> argparse.Namespace:
    """解析报告目录、shots 和语言三个命令行参数。"""
    # 创建脚本命令行解析器。
    parser = argparse.ArgumentParser(
        description="Run a 3x3 MIS through all unified Problem compile modes."
    )
    # --output-dir 指定四份 HTML 文件的保存目录。
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/problem_compiler_3x3_mis"),
        help="Directory for three route reports and one comparison report.",
    )
    # --shots 控制每个参数点的采样次数。
    parser.add_argument("--shots", type=int, default=32)
    # --language 选择英文或中文报告。
    parser.add_argument("--language", choices=("en", "zh"), default="zh")
    # 返回解析后的参数对象。
    return parser.parse_args()


def main() -> None:
    """校验参数，执行三条路线并打印汇总结果。"""
    # 读取命令行参数。
    args = parse_args()
    # 拒绝零或负数 shots，避免无意义的采样请求。
    if args.shots <= 0:
        raise ValueError("--shots must be positive.")
    # 运行完整 Demo，并把结构化摘要输出到终端。
    print(
        run_demo(
            output_dir=args.output_dir,
            shots=args.shots,
            language=args.language,
        )
    )


if __name__ == "__main__":
    # 直接运行脚本时进入命令行流程。
    main()
