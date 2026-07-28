"""通过同一个 Backend.run 入口执行 Hybrid 单点任务和参数扫描。"""

from __future__ import annotations

import json

from cascaqit import AHSProgram, AtomRegister, Circuit, Waveform
from cascaqit.hybrid import HybridProgram
from cascaqit.parameters import ParameterScan
from cascaqit.simulators import LocalBackend

# 创建 Hybrid 第一段 Digital 准备线路，只使用一个量子比特。
prepare = Circuit(1, program_id="local.backend.prepare")
# 声明共享参数 theta，并限制允许绑定的角度范围。
theta = prepare.parameter("theta", lower_bound=-1.0, upper_bound=1.0)
# 先用 H 门制备叠加态，再让 RZ 门读取 theta 参数。
prepare.h(0).rz(theta, 0)
# 创建 Hybrid 中间的 Analog 演化区块。
evolve = (
    # 单位点阵列与 Digital 的单量子比特逻辑规模保持一致。
    AHSProgram(AtomRegister.line(count=1, spacing=5.0))
    # 添加持续 0.2 的常量全局驱动。
    .drive(
        # Rabi 强度固定为 0.8。
        rabi=Waveform.constant(0.8, duration=0.2),
        # Detuning 固定为 0.1，并与 Rabi 使用相同时长。
        detuning=Waveform.constant(0.1, duration=0.2),
        # 全局相位固定为 0.0。
        phase=0.0,
    )
)
# 按 Digital → Analog → Digital 的顺序组装完整 HybridProgram。
program = (
    # 稳定的程序标识会进入结果 metadata 和哈希记录。
    HybridProgram("local.backend.workflow")
    # 第一段 prepare 负责准备初态并应用参数化旋转。
    .digital("prepare", prepare)
    # 第二段 evolve 负责模拟相互作用演化。
    .analog("evolve", evolve)
    # 第三段 correct 使用固定角度进行末段修正。
    .digital("correct", Circuit(1).rz(0.3, 0))
    # 在全部区块之后统一测量，并把结果写入 readout key。
    .measure_all(key="readout")
)

# 创建固定随机种子的本地后端，保证单点和扫描结果可重复。
backend = LocalBackend(seed=7)
# 提交单点任务：theta 绑定为 0.3，总共采样 32 次。
job = backend.run(program, params={"theta": 0.3}, shots=32)
# 在读取结果前记录任务状态，用于展示 Job 的状态流转。
queued_state = job.status().state
# result() 等待本地任务完成并返回 ResultIR。
result = job.result()
# 提取各区块之间的状态交接记录，检查 Hybrid 状态是否连续。
transitions = result.state_transitions()
# references 包含 bundle hash 和最终状态 hash 等可追踪信息。
references = result.metadata["references"]

# 定义两个显式参数点，演示同一个程序如何复用为扫描任务。
scan = ParameterScan.explicit(
    # scan_id 用于在扫描结果和报告中唯一标识本次扫描。
    scan_id="scan.local.backend.workflow",
    # 每个字典对应一次独立的 theta 参数绑定。
    points=({"theta": 0.1}, {"theta": 0.4}),
)
# 同一个 backend.run 通过 sweep 参数接收 ParameterScan。
scan_job = backend.run(program, sweep=scan, shots=32)
# 在读取扫描结果前记录任务的排队状态。
scan_queued_state = scan_job.status().state
# 获取聚合后的扫描结果，其中每个 item 对应一个参数点。
scan_result = scan_job.result()

# 输出单点任务和扫描任务的关键状态、哈希、counts 与执行范围。
print(
    # JSON 结构便于学员逐层查看顶层任务和 scan 子结果。
    json.dumps(
        {
            # 顶层字段描述单点 Hybrid 任务。
            "example": "local_backend_workflow",
            "queued_state": queued_state,
            "completed_state": job.status().state,
            "counts": result.counts,
            "transition_count": len(transitions),
            "backend_id": result.metadata["backend_id"],
            "program_hash": result.program_hash,
            "bundle_hash": references["bundle_hash"],
            "final_state_hash": references["final_state_hash"],
            "full_daqc_state_handoff": (
                backend.capability.hybrid_state_handoff_supported
            ),
            "backend_called": result.metadata["backend_called"],
            "network_accessed": result.metadata["network_accessed"],
            "credentials_loaded": False,
            "hardware_execution": False,
            "cloud_execution": False,
            "execution_package_created": result.metadata[
                "execution_package_created"
            ],
            # scan 子字典描述两个参数点的聚合执行结果。
            "scan": {
                "queued_state": scan_queued_state,
                "completed_state": scan_job.status().state,
                "item_states": [item.state for item in scan_result.items],
                "theta_values": [
                    item.bind_set.values["theta"] for item in scan_result.items
                ],
                "counts": list(scan_result.counts),
                "bundle_hashes": [
                    item.measurement_result.bundle_hash
                    for item in scan_result.successful_items
                    if item.measurement_result is not None
                ],
                "backend_id": scan_result.metadata["backend_id"],
                "backend_called": scan_result.metadata["backend_called"],
                "network_accessed": scan_result.metadata["network_accessed"],
                "execution_package_created": scan_result.metadata[
                    "execution_package_created"
                ],
            },
        },
        # 固定输出键顺序，方便多次运行和自动检查比较。
        sort_keys=True,
    )
)
