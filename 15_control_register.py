"""在本地检查阵列生命周期、控制约束和按位点设置的相位。"""

from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from cascaqit import (
    AHSProgram,
    AtomRegister,
    Circuit,
    LocalBackend,
    MockNeutralAtomTarget,
    SimulationOptions,
    SitePattern,
    Waveform,
    visualize,
)
from cascaqit.analog import SitePhasePattern
from cascaqit.hybrid import HybridProgram
from cascaqit.native_ir import RegisterLifecycleIR

# 每次实验采样 32 次。
SHOTS = 32
# 固定本地后端和模拟器随机种子。
SEED = 43
# 绑定到局域 phase pattern 的共享相位偏移量。
PHASE_OFFSET = 0.3
# 未指定 --output 时使用的默认报告位置。
DEFAULT_REPORT = (
    Path("examples/user/assets") / "experiment_control_register_report.html"
)


def build_register_lifecycle() -> RegisterLifecycleIR:
    """创建 3x3 阵列，并保存装载和制备过程中的不可变快照。"""
    # planned 是包含九个计划位点的初始 3x3 阵列。
    planned = AtomRegister.square(side=3, spacing=8.0)
    # 第一份新快照把 q6 标记为空位，原 planned 对象保持不变。
    loaded = planned.with_site_status(
        "q6",
        status="vacant",
        lifecycle_stage="loaded",
        snapshot_id="register.loaded.vacancy",
    )
    # 第二份新快照把 q7 标记为缺陷位点，并保留原因 metadata。
    inspected = loaded.with_site_status(
        "q7",
        status="defect",
        lifecycle_stage="loaded",
        snapshot_id="register.loaded.inspected",
        metadata={
            "contains_atom": True,
            "reason": "local_mock_exclusion",
        },
    )
    # 第三份新快照把 q8 标记为装载失败，并进入 prepared 阶段。
    prepared = inspected.with_site_status(
        "q8",
        status="loading_failed",
        lifecycle_stage="prepared",
        snapshot_id="register.prepared",
    )
    # 按时间顺序保存四份快照，形成可验证的哈希链。
    return RegisterLifecycleIR(
        lifecycle_id="register.demo.experiment_control",
        snapshots=(
            planned.to_ir(),
            loaded.to_ir(),
            inspected.to_ir(),
            prepared.to_ir(),
        ),
    )


def build_program() -> tuple[HybridProgram, RegisterLifecycleIR]:
    """基于 prepared 快照创建参数化 D-A-D 实验。"""
    # 先生成完整阵列生命周期。
    lifecycle = build_register_lifecycle()
    # 使用最后一份 prepared 快照重建实际参与 Analog 程序的 AtomRegister。
    prepared = AtomRegister(
        # sites 保留每个位点的 occupied、vacant、defect 等状态。
        sites=lifecycle.snapshots[-1].sites,
        # 以下三个字段维持快照身份和前后哈希关系。
        snapshot_id=lifecycle.snapshots[-1].snapshot_id,
        lifecycle_stage=lifecycle.snapshots[-1].lifecycle_stage,
        previous_snapshot_hash=lifecycle.snapshots[-1].previous_snapshot_hash,
    )
    # 用 prepared 阵列创建 Analog 演化区块。
    analog = AHSProgram(
        prepared,
        program_id="demo.experiment_control.evolve",
    )
    # 声明 site_phase 参数，后面映射到多个位点的正负相位偏移。
    site_phase = analog.parameter(
        "site_phase",
        unit="rad",
        lower_bound=-1.0,
        upper_bound=1.0,
    )
    # 先添加全局驱动，再链式追加局域 detuning 和局域 Rabi。
    analog.drive(
        rabi=Waveform.linear(0.15, 0.55, duration=0.4),
        detuning=Waveform.linear(-0.25, 0.2, duration=0.4),
        phase=Waveform.constant(0.1, duration=0.4, value_unit="rad"),
    ).local_detuning(
        # 局域 detuning 的强度随 SitePattern 权重缩放。
        waveform=Waveform.constant(0.2, duration=0.4),
        # 只有 q1、q3 具有非零 detuning 权重。
        pattern=SitePattern.from_mapping(
            {"q0": 0.0, "q1": 1.0, "q2": 0.0, "q3": 0.5, "q4": 0.0, "q5": 0.0}
        ),
    ).local_rabi(
        # 局域 Rabi 在 0.4 时长内从 0.1 增加到 0.35。
        rabi=Waveform.linear(0.1, 0.35, duration=0.4),
        # 所有局域 Rabi 位点共享基础相位 0.05。
        phase=0.05,
        # q0、q2、q4、q5 使用不同幅度权重。
        pattern=SitePattern.from_mapping(
            {
                "q0": 1.0,
                "q1": 0.0,
                "q2": 0.75,
                "q3": 0.0,
                "q4": 0.5,
                "q5": 0.25,
            }
        ),
        # The canonical parameter changes the local drive phase, not report metadata.
        # 把同一个 site_phase 参数以正、负和半幅映射到不同位点。
        phase_pattern=SitePhasePattern.from_mapping(
            {
                "q0": site_phase,
                "q1": 0.0,
                "q2": site_phase * -1.0,
                "q3": 0.0,
                "q4": site_phase * 0.5,
                "q5": 0.0,
            }
        ),
    )

    # 准备区块只包含六个可用逻辑位点，排除三类异常位点。
    prepare = Circuit(6, program_id="demo.experiment_control.prepare")
    # 在 q0 上制备叠加态，并与 q4 建立纠缠。
    prepare.h(0).cx(0, 4)
    # 创建末段读出旋转区块。
    readout = Circuit(6, program_id="demo.experiment_control.readout")
    # 在 q1 和 q5 上施加末段旋转。
    readout.ry(0.15, 1).rz(-0.1, 5)
    # 组合准备、演化、读出和统一测量四个步骤。
    program = (
        HybridProgram("demo.experiment_control")
        .digital("prepare", prepare)
        .analog("evolve", analog)
        .digital("readout", readout)
        .measure_all(key="readout")
    )
    # 同时返回程序和生命周期，运行后要核对报告中的快照哈希链。
    return program, lifecycle


def run(output: Path = DEFAULT_REPORT) -> dict[str, Any]:
    """绑定参数、执行实验、生成报告并返回关键检查字段。"""
    # 构造参数化 Hybrid 程序和对应阵列生命周期。
    parameterized, lifecycle = build_program()
    # 把 site_phase 绑定为固定偏移量，得到本次实际执行程序。
    program = parameterized.bind({"site_phase": PHASE_OFFSET})
    # 编译绑定后的程序，生成区块图和控制计划。
    compilation = program.compile()
    # 编译失败时保留并抛出全部结构化诊断。
    if compilation.graph is None or compilation.plan is None:
        raise RuntimeError([item.to_dict() for item in compilation.diagnostics])

    # 创建公开的本地中性原子目标。
    target = MockNeutralAtomTarget.local_ahs_v0_1()
    # 创建固定种子、固定 Analog 时间步数的本地后端并立即运行。
    result = LocalBackend(
        target=target,
        seed=SEED,
        analog_time_steps=8,
    ).run(
        # 提交已绑定且已通过编译检查的程序。
        program,
        # 使用固定采样次数。
        shots=SHOTS,
        # 显式设置数值积分器、精度、步数和随机种子。
        options=SimulationOptions(
            integrator="fixed_step_krylov",
            dtype="complex64",
            max_steps=8,
            seed=SEED,
        ),
    ).result()
    # 规范化报告路径并创建父目录。
    resolved_output = output.expanduser().resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    # 从已完成的程序和结果生成独立 HTML 报告。
    report = visualize(
        result,
        program=program,
        output=resolved_output,
        title="Experiment control and register lifecycle",
    )

    # 读取报告中的设计、校验、计划和运行状态四个阶段。
    design = report.section("experiment.design").payload
    validate = report.section("experiment.validate").payload
    plan = report.section("experiment.plan").payload
    state = report.section("experiment.state").payload
    # 定位实验设计中的 Analog 区块。
    analog_design = next(
        block for block in design["blocks"] if block["block_type"] == "analog"
    )
    # 读取编译计划中的第一条控制调度。
    schedule = plan["control_schedules"][0]
    # 读取 ResultIR 中每个区块之间的状态交接记录。
    transitions = result.state_transitions()

    # 返回阵列快照、参数绑定、控制诊断、状态连续性和报告信息。
    return {
        "example": "experiment_control_and_register",
        "register": analog_design["register_snapshot"],
        "lifecycle_snapshot_ids": [
            snapshot.snapshot_id for snapshot in lifecycle.snapshots
        ],
        "lifecycle_hash_chain_valid": all(
            current.previous_snapshot_hash == previous.stable_hash()
            for previous, current in zip(
                lifecycle.snapshots,
                lifecycle.snapshots[1:],
            )
        ),
        "bound_parameters": {"site_phase": PHASE_OFFSET},
        "design_phase_offsets": analog_design["site_phase_patterns"][0][
            "offsets"
        ],
        "runtime_phase_offsets": state["site_phase_pattern_consumers"][0][
            "offsets"
        ],
        "control_operation_kinds": [
            operation["operation_kind"]
            for operation in schedule["schedule"]["operations"]
        ],
        "control_diagnostic_codes": sorted(
            {
                item["code"]
                for item in validate["control_constraint_diagnostics"]
                if item["code"].startswith("CONTROL_")
            }
        ),
        "production_channel_allocation_performed": schedule[
            "production_channel_allocation_performed"
        ],
        "state_chain_continuous": all(
            left.output_state_hash == right.input_state_hash
            for left, right in zip(transitions, transitions[1:])
        ),
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
    """运行实验并打印按键排序的 JSON 摘要。"""
    # run() 负责执行和报告，main() 只负责终端输出。
    print(json.dumps(run(output), sort_keys=True))


def _cli_output_path() -> Path:
    """解析可选 --output 参数，并忽略外层运行器参数。"""
    # 创建本脚本自己的参数解析器。
    parser = ArgumentParser()
    # --output 可覆盖默认 HTML 报告路径。
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    # parse_known_args 允许 Notebook 或测试运行器附加其他参数。
    arguments, _ = parser.parse_known_args()
    # 返回有效 Path；类型异常时回退到默认路径。
    return arguments.output if isinstance(arguments.output, Path) else DEFAULT_REPORT


if __name__ == "__main__":
    # 直接运行脚本时解析报告路径并执行完整示例。
    main(_cli_output_path())
