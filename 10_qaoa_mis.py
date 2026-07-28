"""使用 QAOA 在本地求解一个小规模最大独立集问题。"""

from __future__ import annotations

from cascaqit import QAOA, GraphProblemIR, LocalBackend, OptimizerConfig, visualize


def main() -> None:
    """依次完成问题定义、QAOA 优化、采样、解码、基线和可视化。"""
    # 用三个节点和两条相邻边定义一条长度为 3 的路径图。
    graph = GraphProblemIR.from_edges(
        # problem_id 会进入算法结果和报告，便于追踪输入问题。
        problem_id="problem.user.qaoa_mis",
        # positions 只描述可视化和物理布局，不改变图的边关系。
        positions={
            "a": (0.0, 0.0),
            "b": (5.0, 0.0),
            "c": (10.0, 0.0),
        },
        # a-b 和 b-c 冲突，因此最大独立集应选择 a 与 c。
        edges=(("a", "b"), ("b", "c")),
    )
    # 创建一层 QAOA，并直接在本地完成参数优化和最终采样。
    result = QAOA(graph, layers=1, mis_penalty=2.0).run(
        # 固定 LocalBackend 种子，使优化评估和采样可以复现。
        backend=LocalBackend(seed=21),
        # COBYLA 在最多 12 次迭代、8 次目标评估内搜索参数。
        optimizer=OptimizerConfig(
            method="COBYLA",
            max_iterations=12,
            max_evaluations=8,
            seed=21,
        ),
        # 单层 QAOA 的初始 gamma 和 beta。
        initial_parameters=(0.25, -0.35),
        # 优化完成后使用 256 shots 生成最终候选解分布。
        final_shots=256,
    )
    # 从已经完成的算法结果构建内存中的标准报告对象。
    report = visualize(result)
    # 读取最终采样中实际观测到的最佳可行候选解。
    candidate = result.best_observed_candidate
    # 读取小规模问题的精确基线，用于对照算法结果。
    baseline = result.baseline
    # 本例要求候选解和精确基线都存在，缺失时立即失败。
    assert candidate is not None and baseline is not None

    # 打印优化次数、能量、候选解、基线和报告结构。
    print(
        {
            # 稳定名称用于培训日志识别。
            "example": "qaoa_mis_workflow",
            # algorithm_kind 应为 qaoa。
            "algorithm": result.algorithm_kind,
            # evaluations 是优化器实际完成的目标函数评估次数。
            "evaluations": len(result.evaluations),
            # 最佳能量保留十位小数，便于重复运行时比较。
            "best_energy": round(result.best_evaluation.energy, 10),
            # 最终 counts 总和应等于 final_shots。
            "counts_total": sum(result.final_result.counts.values()),
            # bitstring 和 decoded 字段共同说明候选解选择了哪些节点。
            "candidate_bitstring": candidate.bitstring,
            "candidate_feasible": candidate.feasible,
            "selected_nodes": candidate.decoded["selected_nodes"],
            # baseline_value 是精确求解得到的参考目标值。
            "baseline_value": baseline.objective_value,
            # 输出报告 profile 和 section，便于确认可视化内容完整。
            "visualization_profile": report.profile,
            "visualization_sections": [
                section.section_id for section in report.sections
            ],
            # 明确本例没有访问网络、云端或真实硬件。
            "hardware_execution": False,
            "cloud_execution": False,
            "network_accessed": False,
            "credentials_loaded": False,
        }
    )


if __name__ == "__main__":
    # 直接运行文件时执行完整 QAOA MIS 流程。
    main()
