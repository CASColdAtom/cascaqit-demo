"""在五条本地执行路径中计算同一类强类型 Observable 批次。"""

from __future__ import annotations

from typing import Any

from cascaqit import (
    AHSProgram,
    AtomRegister,
    Circuit,
    HybridProgram,
    LocalBackend,
    ObservableSet,
    PauliProduct,
    PauliX,
    PauliZ,
    PauliZZ,
    Waveform,
)
from cascaqit.observables import ObservableBatchResultIR
from cascaqit.parameters import ParameterScan
from cascaqit.simulators import NoiseChannel, NoiseModel, SimulationOptions


def _idle_analog(site_count: int, *, measure: bool) -> AHSProgram:
    """创建保持逻辑位点顺序不变的短时零驱动 Analog 程序。"""
    # 创建指定数量的线性原子位点，并给程序设置包含规模的 ID。
    program = AHSProgram(
        AtomRegister.line(count=site_count, spacing=5.0),
        program_id=f"example.observables.analog.{site_count}",
    ).drive(
        # Rabi 为 0，表示这段时间不施加横向驱动。
        rabi=Waveform.constant(0.0, duration=0.02),
        # Detuning 同样为 0，使程序只承担状态交接作用。
        detuning=Waveform.constant(0.0, duration=0.02),
        # 全局相位固定为 0。
        phase=0.0,
    )
    # 独立 Analog 示例需要测量；嵌入 Hybrid 时由末尾统一测量。
    return program.measure() if measure else program


def _hybrid_program() -> HybridProgram:
    """创建状态连续的 Digital-Analog-Digital 程序。"""
    # 三段操作作用在同一个双量子比特状态上。
    return (
        # 创建 Hybrid 容器并设置稳定程序 ID。
        HybridProgram("example.observables.hybrid")
        # 第一段在 q0 上应用 H 门制备叠加态。
        .digital("prepare", Circuit(2).h(0))
        # 中间段插入不测量的零驱动 Analog 区块。
        .analog("idle", _idle_analog(2, measure=False))
        # 最后一段再次应用 H 门，检查跨区块状态交接。
        .digital("unprepare", Circuit(2).h(0))
        # 在整条 Hybrid 链结束后测量全部量子比特。
        .measure_all()
    )


def _parameterized_hybrid() -> HybridProgram:
    """创建 Digital 与 Analog 共用 theta 的参数扫描程序。"""
    # 创建包含两个量子比特的参数化 Digital 区块。
    circuit = Circuit(2, program_id="example.observables.sweep.digital")
    # theta 限定在 [-1, 1]，供 RX 角度和 Analog phase 共用。
    theta = circuit.parameter("theta", lower_bound=-1.0, upper_bound=1.0)
    # q0 使用参数化 RX，q1 使用固定 H 门。
    circuit.rx(theta, 0).h(1)

    # 创建与 Digital 区块规模相同的双位点 Analog 程序。
    analog = AHSProgram(
        AtomRegister.line(count=2, spacing=5.0),
        program_id="example.observables.sweep.analog",
    )
    # 在 Analog 区块中声明同名 theta 参数，并明确单位为弧度。
    phase = analog.parameter(
        "theta",
        unit="rad",
        lower_bound=-1.0,
        upper_bound=1.0,
    )
    # Analog 全局驱动把共享 theta 用作相位。
    analog.drive(
        rabi=Waveform.constant(0.2, duration=0.02),
        detuning=Waveform.constant(0.0, duration=0.02),
        phase=phase,
    )
    # 组合参数化 Digital 和 Analog 区块，并在末尾统一测量。
    return (
        HybridProgram("example.observables.sweep")
        .digital("prepare", circuit)
        .analog("evolve", analog)
        .measure_all()
    )


def _batch_summary(batch: ObservableBatchResultIR) -> dict[str, Any]:
    """把 ObservableBatchResultIR 压缩成适合终端演示的摘要。"""
    # 保留来源哈希和每个 observable 的统计量。
    return {
        "source_kind": batch.source_kind.value,
        "source_hash": batch.source_hash,
        "observables": [
            {
                "name": item.name,
                "expectation": round(item.expectation, 8),
                "variance": round(item.variance, 8),
                "standard_error": round(item.standard_error, 8),
                "sample_count": item.sample_count,
                "estimator_kind": item.estimator_kind.value,
            }
            for item in batch.items
        ],
    }


def _require_batch(batch: ObservableBatchResultIR | None) -> ObservableBatchResultIR:
    """确保后端返回了请求的 observable batch。"""
    # None 表示请求的 observable 结果在执行链中丢失，必须立即报错。
    if batch is None:
        raise RuntimeError(
            "LocalBackend did not return the requested observable batch."
        )
    # 类型收窄后把有效 batch 返回给摘要函数。
    return batch


def main() -> None:
    """运行 Digital、Analog、Hybrid、噪声轨迹和参数扫描五种路径。"""
    # 所有路径共用一个本地后端；较小时间步数用于控制演示耗时。
    backend = LocalBackend(seed=7, analog_time_steps=2)
    # 定义前三条路径共用的双位点 ObservableSet。
    two_site = ObservableSet(
        (
            # q0 上的 Z 期望值。
            PauliZ("q0"),
            # q1 上的 X 期望值。
            PauliX("q1"),
            # q0 与 q1 的 ZZ 关联。
            PauliZZ("q0", "q1"),
            # 显式 PauliProduct 表达 q0、q1 的 XX 关联。
            PauliProduct((("q0", "X"), ("q1", "X")), name="XX(q0,q1)"),
        )
    )

    # 路径 1：执行 Bell 风格 Digital 线路并计算四个 observable。
    digital = backend.run(
        Circuit(2).h(0).cx(0, 1),
        shots=32,
        observables=two_site,
    ).result()
    # 路径 2：执行带终端测量的零驱动 Analog 程序。
    analog = backend.run(
        _idle_analog(2, measure=True),
        shots=32,
        observables=two_site,
        # Analog 路径显式选择固定步长 Krylov 积分器。
        options=SimulationOptions(
            integrator="fixed_step_krylov",
            max_steps=2,
        ),
    ).result()
    # 路径 3：执行 Digital-Analog-Digital 状态链。
    hybrid = backend.run(
        _hybrid_program(),
        shots=32,
        observables=two_site,
        options=SimulationOptions(
            integrator="fixed_step_krylov",
            max_steps=2,
        ),
    ).result()

    # 噪声路径只测量 q0 上的 Z 和 X，减少轨迹估计开销。
    noisy_set = ObservableSet((PauliZ("q0"), PauliX("q0")))
    # 路径 4：在 Hybrid 程序上加入退相干噪声并使用 trajectory 方法。
    noisy = backend.run(
        _hybrid_program(),
        # NoiseModel 中只配置一个退相干通道。
        noise=NoiseModel(
            "example.observables.trajectory",
            (NoiseChannel.dephasing(0.4),),
        ),
        shots=64,
        seed=11,
        observables=noisy_set,
        # 256 条轨迹用于估计带噪声 observable。
        options=SimulationOptions(
            method="trajectory",
            integrator="fixed_step_krylov",
            trajectories=256,
            max_steps=2,
        ),
    ).result()

    # 路径 5：对共享参数 theta 的三个显式取值执行 Hybrid 扫描。
    sweep = backend.run(
        # 每个扫描点复用同一个参数化 HybridProgram。
        _parameterized_hybrid(),
        # theta 依次取 -0.3、0.0 和 0.3。
        sweep=ParameterScan.explicit(
            scan_id="example.observables.sweep",
            points=({"theta": -0.3}, {"theta": 0.0}, {"theta": 0.3}),
        ),
        shots=32,
        seed=13,
        # 每个扫描点都计算 q0 的 Z 和 q1 的 X。
        observables=ObservableSet((PauliZ("q0"), PauliX("q1"))),
        # workers=2 演示有界并行执行，同时保持结果顺序稳定。
        options=SimulationOptions(
            integrator="fixed_step_krylov",
            max_steps=2,
            workers=2,
        ),
    ).result()

    # 把三个扫描子结果整理为参数、索引和 observable 摘要。
    sweep_points = []
    # sweep.items 按原始扫描顺序返回每个参数点。
    for item in sweep.items:
        # 任一成功项缺少 ResultIR 都说明执行链不完整。
        if item.result is None:
            raise RuntimeError(
                f"Sweep item {item.scan_index} did not produce a result."
            )
        # 保存当前参数点的绑定值和 ObservableBatchResultIR 摘要。
        sweep_points.append(
            {
                "index": item.scan_index,
                "parameters": dict(item.bind_set.values),
                "batch": _batch_summary(_require_batch(item.result.observable_batch)),
            }
        )

    # 把五条路径放进同一个字典，便于横向比较来源和统计量。
    print(
        {
            "example": "observable_batch_workflow",
            "digital": _batch_summary(_require_batch(digital.observable_batch)),
            "analog": _batch_summary(_require_batch(analog.observable_batch)),
            "hybrid": _batch_summary(_require_batch(hybrid.observable_batch)),
            "noisy_trajectory": _batch_summary(
                _require_batch(noisy.observable_batch)
            ),
            "sweep": sweep_points,
            "execution_counts": {
                "digital": 1,
                "analog": 1,
                "hybrid": 1,
                "noisy_trajectory": 1,
                "sweep_children": len(sweep_points),
            },
            "hardware_execution": False,
            "cloud_execution": False,
            "network_accessed": False,
            "credentials_loaded": False,
        }
    )


if __name__ == "__main__":
    # 直接运行脚本时依次执行五种本地模拟路径。
    main()
