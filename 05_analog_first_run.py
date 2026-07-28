"""校验、离散化并在本地模拟一个双原子位点 AHS 程序。

输出集中展示第一次 Analog 运行最需要检查的内容：校验状态、counts、平均激发、
诊断以及本地执行范围。
"""

from __future__ import annotations

from cascaqit import (
    AHSProgram,
    AtomRegister,
    LocalAhsSimulator,
    MockNeutralAtomTarget,
    Waveform,
)


def main() -> None:
    """按目标、阵列、波形、校验、离散化、运行的顺序执行最小 Analog 流程。"""
    # 创建 SDK 自带的中性原子模拟目标，后续校验和离散化都以它为准。
    target = MockNeutralAtomTarget.v0_1()
    # 创建两个等间距原子位点；spacing 使用 SDK 约定的物理单位。
    register = AtomRegister.line(count=2, spacing=5.0)

    # 用原子阵列创建 AHS 程序，并设置可追踪的 program_id。
    program = AHSProgram(register, program_id="program.learning.analog")
    # 添加一段全局驱动，明确给出 Rabi、detuning 和 phase 三个控制量。
    program.drive(
        # Rabi 在 1.0 时间内从 0 线性增加到 2.0。
        rabi=Waveform.linear(0.0, 2.0, duration=1.0, waveform_id="rabi"),
        # Detuning 经过起点、中点和终点三个采样位置。
        detuning=Waveform.piecewise_linear(
            # 三个时间点覆盖完整的 1.0 时长。
            times=[0.0, 0.5, 1.0],
            # 对应数值从 -4.0 经过 0.0 变化到 4.0。
            values=[-4.0, 0.0, 4.0],
            # waveform_id 便于在报告和诊断中定位这条波形。
            waveform_id="detuning",
        ),
        # 本例使用固定的全局相位 0.0。
        phase=0.0,
    )
    # 在程序末尾添加测量；没有测量就不会产生最终 bitstring counts。
    program.measure()

    # 先按目标限制和 32 shots 要求校验程序，保留完整 DiagnosticsIR。
    validated = program.validate(target, shots=32)
    # 把连续波形映射到目标支持的离散网格；nearest 表示取最近合法值。
    discretized, _report = validated.discretize(target, policy="nearest")
    # 使用固定随机种子的本地 AHS 模拟器执行离散化程序并采样 16 次。
    result = LocalAhsSimulator(target=target, seed=3101).run(discretized, shots=16)

    # 只打印培训中需要立即核对的字段，完整对象仍保留在 result 中。
    print(
        {
            # 示例名称便于从多段培训日志中识别这次输出。
            "example": "learning_analog_first_run",
            # 从离散化后的 ProgramIR 读取真实程序类型。
            "program_type": discretized.program_ir.program_type,
            # 只收集 error 级别校验诊断；空列表表示本次校验通过。
            "validation_errors": [
                diagnostic.code
                for diagnostic in validated.diagnostics
                if diagnostic.severity == "error"
            ],
            # counts 总和应与本次运行的 16 shots 一致。
            "counts_total": sum(result.counts.values()),
            # 输出运行阶段产生的全部诊断代码，便于定位模拟状态或警告。
            "diagnostic_codes": [
                diagnostic.code for diagnostic in result.diagnostics
            ],
            # 平均激发保留六位小数，方便演示时稳定比较。
            "mean_excitation": round(result.observables["mean_excitation"], 6),
            # 以下字段明确本例只做本地模拟，不代表硬件执行。
            "hardware_execution": False,
            "cloud_execution": False,
            "network_accessed": False,
            "credentials_loaded": False,
        }
    )


if __name__ == "__main__":
    # 直接运行文件时执行最小 Analog 示例。
    main()
