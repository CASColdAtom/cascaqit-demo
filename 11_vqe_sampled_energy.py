"""在同一个固定参数点比较 VQE 精确能量和有限采样能量。

哈密顿量包含 X、Y、Z 和双量子比特 Pauli 乘积。CASCAQit 会把各项划分为逐比特
可交换组，添加所需的局域测量基变换，再根据预采样结果分配剩余 shots。最终能量
和标准误差同时使用预采样与第二阶段采样的 counts。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cascaqit import (
    VQE,
    HamiltonianTerm,
    PauliHamiltonian,
    PauliMeasurementConfig,
    PauliProduct,
    PauliX,
    PauliY,
    PauliZ,
    visualize,
)

# 精确求值和有限采样共用固定种子，保证示例可重复。
SEED = 173
# 未传参数时，两份报告写入这个相对目录。
DEFAULT_OUTPUT_DIR = Path("artifacts/vqe_sampled_energy_workflow")


def build_hamiltonian() -> PauliHamiltonian:
    """创建一个需要多个局域测量基的通用 Pauli 哈密顿量。"""
    # logical_order 固定 bit 和 Pauli 算符对应的逻辑量子比特顺序。
    return PauliHamiltonian(
        # 稳定 ID 用于 VQE 结果、测量计划和报告追踪。
        hamiltonian_id="hamiltonian.user.vqe-sampled-energy",
        logical_order=("q0", "q1"),
        # constant 是不需要测量、直接加到总能量上的常数项。
        constant=0.125,
        # 每个 HamiltonianTerm 包含唯一名称、系数和 Pauli 算符。
        terms=(
            # q0 上的单比特 X 项。
            HamiltonianTerm("x.q0", 0.7, PauliX("q0", name="X(q0)")),
            # q0 上的 X 与 q1 上的 Z 构成双比特乘积项。
            HamiltonianTerm(
                "xz.q0.q1",
                -0.2,
                PauliProduct(
                    (("q0", "X"), ("q1", "Z")),
                    name="X(q0) Z(q1)",
                ),
            ),
            # q0 上的单比特 Z 项。
            HamiltonianTerm("z.q0", 0.4, PauliZ("q0", name="Z(q0)")),
            # q1 上的单比特 Y 项。
            HamiltonianTerm("y.q1", -0.3, PauliY("q1", name="Y(q1)")),
        ),
    )


def run_workflow(*, output_dir: Path) -> dict[str, object]:
    """执行精确和有限采样求值，并保存中英文报告。"""
    # 用自定义哈密顿量创建 VQE 对象；参数名称由内置 Ansatz 生成。
    vqe = VQE(build_hamiltonian())
    # 把四个固定角度按 vqe.parameter_names 的实际顺序绑定。
    parameters = {
        name: value
        for name, value in zip(vqe.parameter_names, (0.31, -0.47, 0.22, 0.19))
    }

    # Exact statevector evaluation is the local numerical reference for the same
    # Circuit and parameters. It is not used to alter the sampled result.
    # 使用状态向量在同一参数点计算精确能量，作为纯本地数值参考。
    exact = vqe.evaluate(parameters, seed=SEED)
    # 使用有限 shots 估计同一参数点的能量和标准误差。
    sampled = vqe.evaluate_sampled(
        # 传入与精确求值完全相同的参数绑定。
        parameters,
        # The first 512 shots in each group estimate its realized energy
        # variance. The remaining shots then favor the group that contributes
        # more sampling uncertainty, without changing the 8192-shot budget.
        measurement=PauliMeasurementConfig(
            # 每个可交换组最终总预算为 4096 shots。
            shots_per_group=4096,
            # pilot_variance 根据预采样方差分配第二阶段 shots。
            allocation="pilot_variance",
            # 每个组先使用 512 shots 估计方差。
            pilot_shots_per_group=512,
        ),
        # 固定采样随机种子。
        seed=SEED,
        # 稳定运行 ID 会写入 ResultIR 和报告来源信息。
        algorithm_run_id="algorithm.user.vqe-sampled-energy",
    )
    # 读取实际保存的自适应分配详情。
    adaptive = sampled.adaptive_allocation
    # pilot_variance 应始终返回分配详情，缺失时直接失败。
    if adaptive is None:
        raise RuntimeError("pilot_variance evaluation did not retain its allocation.")

    # 创建报告目录。
    output_dir.mkdir(parents=True, exist_ok=True)
    # 为英文和中文报告准备不同文件名。
    english_report = output_dir / "vqe-sampled-energy.en.html"
    chinese_report = output_dir / "vqe-sampled-energy.zh.html"
    # 两份报告都从同一个 sampled 结果生成，不会重复执行 VQE。
    visualize(sampled, output=english_report, language="en")
    visualize(sampled, output=chinese_report, language="zh")

    # 返回测量分组、shots 分配、能量误差和报告路径。
    return {
        "example": "vqe_sampled_energy_workflow",
        "hamiltonian_terms": len(vqe.hamiltonian.terms),
        "qwc_groups": len(sampled.plan.groups),
        "shot_allocation": sampled.plan.config.allocation,
        "shots_per_group": sampled.plan.config.shots_per_group,
        "pilot_shots_by_group": list(sampled.plan.shots_by_group),
        "additional_shots_by_group": list(adaptive.additional_shots_by_group),
        "shots_by_group": list(sampled.final_shots_by_group),
        "allocation_fallback": adaptive.fallback,
        "total_shots": sampled.total_shots,
        "backend_jobs": sampled.backend_execution_count,
        "exact_energy": exact.energy,
        "sampled_energy": sampled.energy,
        "energy_standard_error": sampled.energy_standard_error,
        "exact_difference": sampled.energy - exact.energy,
        "english_report": str(english_report),
        "chinese_report": str(chinese_report),
        "offline_deterministic": True,
        "hardware_execution": False,
        "cloud_execution": False,
        "network_accessed": False,
        "credentials_loaded": False,
    }


def parse_args() -> argparse.Namespace:
    """解析中英文报告的输出目录。"""
    # 创建命令行解析器。
    parser = argparse.ArgumentParser(
        description="Compare exact and finite-shot VQE energy evaluation."
    )
    # --output-dir 控制两份 HTML 报告的保存位置。
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the English and Chinese HTML reports.",
    )
    # 返回解析后的参数对象。
    return parser.parse_args()


def main() -> None:
    """执行 VQE 对照流程并打印结构化摘要。"""
    # 读取命令行参数。
    args = parse_args()
    # 运行精确和有限采样求值，并打印返回字典。
    print(run_workflow(output_dir=args.output_dir))


if __name__ == "__main__":
    # 直接运行脚本时进入命令行流程。
    main()
