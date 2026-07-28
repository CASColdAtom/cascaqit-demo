"""对照本地 ResultIR、结果视图、可视化和结构化诊断。

派生视图只读取 metadata：不会读取外部 artifact 字节，不会重跑模拟器，也不会
取代 ResultIR 成为原始结果存储。
"""

from __future__ import annotations

from cascaqit import (
    AHSProgram,
    AtomRegister,
    LocalAhsSimulator,
    MockNeutralAtomTarget,
    ProgramValidationError,
    Waveform,
    build_counts_histogram,
    build_result_view,
)


def main() -> None:
    """运行 Analog 程序，并打印结果、诊断和可视化元数据。"""
    # 创建本地模拟目标，程序校验和执行都使用同一组目标约束。
    target = MockNeutralAtomTarget.v0_1()
    # 创建两个间距为 5.0 的线性原子位点。
    register = AtomRegister.line(count=2, spacing=5.0)

    # 用阵列创建 AHS 程序，并设置稳定 program_id。
    program = AHSProgram(
        register,
        program_id="program.user.result_diagnostics_visualization",
    )
    # 添加包含 Rabi、detuning 和 phase 的全局驱动。
    program.drive(
        # Rabi 在 1.0 时长内从 0 线性增加到 2.0。
        rabi=Waveform.linear(0.0, 2.0, duration=1.0, waveform_id="rabi"),
        # Detuning 通过三个采样点从 -4.0 扫到 4.0。
        detuning=Waveform.piecewise_linear(
            times=[0.0, 0.5, 1.0],
            values=[-4.0, 0.0, 4.0],
            waveform_id="detuning",
        ),
        # 本例使用固定全局相位 0.0。
        phase=0.0,
    )
    # 在程序末尾添加测量，确保运行结果包含 bitstring counts。
    program.measure()

    # 使用固定种子的本地 AHS 模拟器运行 16 shots。
    result = LocalAhsSimulator(target=target, seed=2029).run(program, shots=16)
    # 从 ResultIR 构建只读结果视图，不触发第二次执行。
    result_view = build_result_view(result)
    # 从同一个 ResultIR 派生 counts 直方图规范。
    histogram = build_counts_histogram(result)
    # 构造一条示例校验错误，并转换为标准 ErrorIR。
    error = _example_validation_error().to_error_ir()

    # 输出原始结果、派生视图和结构化错误之间的对应关系。
    print(
        {
            "workflow": "result_diagnostics_visualization",
            "steps": ["simulate", "view", "diagnose", "visualize"],
            "result_id": result_view.result_id,
            "view_metadata_only": result_view.metadata_only,
            "diagnostic_codes": [
                diagnostic.code for diagnostic in result.diagnostics
            ],
            "structured_error_code": error.code,
            "structured_error_category": error.category,
            "histogram_kind": histogram.spec.visualization_kind,
            "artifact_bytes_read": result_view.artifact_bytes_read,
            "backend_called": result_view.backend_called,
            "derived_view_authoritative": False,
            "network_accessed": False,
            "credentials_loaded": False,
        }
    )


def _example_validation_error() -> ProgramValidationError:
    """创建一条有完整定位和修复建议的执行前目标校验错误。"""
    # ProgramValidationError 同时保留人类可读消息和机器可读字段。
    return ProgramValidationError(
        # message 可直接提供给开发者或使用者阅读。
        "Atom spacing is below target minimum.",
        # code 是稳定的程序化错误标识。
        code="ATOM_SPACING_TOO_SMALL",
        # object_path 指向发生问题的第二个原子位点。
        object_path="register.sites[1]",
        # suggestion 给出下一步可执行的修改方向。
        suggestion="Increase atom spacing before validation or compilation.",
        # metadata 保存更细的错误分类信息。
        metadata={"reason_category": "target_constraint"},
    )


if __name__ == "__main__":
    # 直接运行脚本时执行结果与诊断示例。
    main()
