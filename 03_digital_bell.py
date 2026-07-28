"""创建、测量并在本地采样一个 Bell 线路。

输出同时保留 counts、probabilities、measurement key 和 bit order。解释任意
bitstring 前，都应先读取这些排序信息。
"""

from __future__ import annotations

from cascaqit import Circuit


def main() -> None:
    """运行两比特 Bell 线路，并打印最常检查的结果字段。"""
    # 创建包含两个量子比特的 Digital 线路，并设置稳定的程序标识。
    circuit = Circuit(
        # 线路需要 q0 和 q1 两个量子比特。
        2,
        # program_id 会进入 ProgramIR，便于报告和日志追踪来源。
        program_id="program.learning.digital",
    )
    # q0 先经过 H 门，再用 CX 与 q1 建立纠缠，最后测量全部量子比特。
    circuit.h(0).cx(0, 1).measure_all()
    # 转成 ProgramIR，后面从中读取程序类型和 measurement key。
    program = circuit.to_program()

    # 在本地模拟器中执行线路，并返回采样次数和概率分布。
    result = circuit.run(
        # 16 shots 足够用于培训演示，同时运行速度很快。
        shots=16,
        # 固定随机种子，使每次培训得到相同采样结果。
        seed=3102,
        # 同时计算 probabilities，便于对照 counts 和理论分布。
        return_probabilities=True,
    )

    # 汇总程序和结果中的关键字段，避免现场打印完整 IR 造成信息过载。
    print(
        {
            # 给这次输出一个稳定名称，便于日志中识别示例。
            "example": "learning_digital_first_run",
            # 从 ProgramIR 读取程序类型，而不是在输出中手写。
            "program_type": program.program_type,
            # 所有 bitstring 的计数之和应等于 shots。
            "counts_total": sum(result.counts.values()),
            # 排序后的概率键可以快速确认本次出现了哪些 bitstring。
            "probability_keys": sorted((result.probabilities or {}).keys()),
            # bit_order 决定 bitstring 中每一位对应哪个量子比特。
            "bit_order": result.metadata["bitstring_ordering"]["qubit_order"],
            # measurement key 来自 ProgramIR 中的测量声明。
            "measurement_keys": [
                measurement.key for measurement in program.circuit.measurements
            ],
            # 以下字段明确这次演示只使用本地模拟路径。
            "hardware_execution": False,
            "cloud_execution": False,
            "network_accessed": False,
            "credentials_loaded": False,
        }
    )


if __name__ == "__main__":
    # 直接运行脚本时开始 Bell 演示。
    main()
