"""演示 Hybrid 参数的声明、绑定、投影和扫描，不执行数值模拟内核。"""

from __future__ import annotations

import json

from cascaqit.hybrid import HybridProgram
from cascaqit.parameters import (
    Parameter,
    ParameterManager,
    ParameterScan,
    ParameterTargetIR,
)
from cascaqit.parameters.projection import project_parameter_bindings
from cascaqit.syntax import (
    ParameterSpec,
    analog_block,
    analyze,
    digital_block,
    measurement_block,
    program_syntax,
)


@digital_block(
    # 声明本区块使用一个名为 q0 的逻辑量子比特。
    qubits=("q0",),
    # theta 是以弧度为单位的区块输入参数。
    parameters={"theta": ParameterSpec(unit="rad")},
    # 分析阶段要求目标支持 RX 门能力。
    capabilities=("gate.rx",),
)
def prepare(theta: float) -> None:
    """声明接收 theta 的 Digital 准备区块。"""


@analog_block(
    # Analog 区块使用同一个 q0 逻辑资源。
    atoms=("q0",),
    # 这里也声明 theta，后面会映射到同一个全局参数。
    parameters={"theta": ParameterSpec(unit="rad")},
    # 分析阶段要求目标支持 AHS 全局驱动。
    capabilities=("ahs.global_drive",),
)
def evolve(theta: float) -> None:
    """声明接收 theta 的 Analog 演化区块。"""


# 测量区块在最后读取 q0，并声明它对应 qubit 资源。
@measurement_block(logical_ids=("q0",), resource_kind="qubit")
def readout() -> None:
    """声明 Hybrid 程序末尾的测量区块。"""


# 用三个声明式区块构造程序语法树。
syntax = program_syntax(
    # 稳定标识用于诊断、哈希和后续 HIR 追踪。
    "hybrid.parameters.demo",
    # blocks 注册可在程序中调用的全部区块定义。
    blocks=(prepare, evolve, readout),
    # invocations 决定实际执行顺序和逻辑资源映射。
    invocations=(
        # Digital 准备区块把 q0 映射到 logical.0。
        prepare(0.0, mapping={"q0": "logical.0"}),
        # Analog 演化沿用相同映射，保持状态连续。
        evolve(0.0, mapping={"q0": "logical.0"}),
        # 最后测量同一个 logical.0。
        readout(mapping={"q0": "logical.0"}),
    ),
)
# 分析语法树，并明确告诉分析器当前可用的两项能力。
analysis = analyze(
    syntax,
    available_capabilities=("gate.rx", "ahs.global_drive"),
)
# HIR 为空说明分析未通过，此时必须保留并抛出结构化诊断。
if analysis.hir is None:
    raise RuntimeError([item.to_dict() for item in analysis.diagnostics])
# 从已通过分析的 HIR 创建可进行参数投影的 HybridProgram。
program = HybridProgram.from_hir(analysis.hir)


def parameter_manager(*, recompile: bool = False) -> ParameterManager:
    """创建参数管理器，并把共享参数显式映射到两个区块。"""
    # 连续调用 declare，集中声明基础参数、默认值和派生表达式。
    manager = (
        # 从一个空的 ParameterManager 开始。
        ParameterManager()
        # 声明跨 Digital 和 Analog 共用的 theta。
        .declare(
            Parameter(
                # 参数名必须与后面的 bind 字典和 target 映射一致。
                "theta",
                # 本例只接受浮点值。
                "float",
                # theta 的物理单位是弧度。
                unit="rad",
                # recompile=True 时演示参数变化会触发重新编译。
                compile_impact="recompile" if recompile else "bind_only",
            )
        )
        # duration 提供默认值，因此调用 bind 时可以不显式传入。
        .declare(Parameter("duration", "float", unit="us", default=1.0))
        # theta_twice 由 theta 自动计算，不需要调用方单独绑定。
        .declare(
            Parameter(
                "theta_twice",
                "float",
                unit="rad",
                expression=Parameter("theta", unit="rad") * 2,
            )
        )
    )
    # 前两个区块分别是 Digital prepare 和 Analog evolve。
    for block in program.blocks[:2]:
        # 为当前区块补充 theta 的显式投影目标。
        manager = manager.map_target(
            ParameterTargetIR(
                # target_id 同时包含区块类型，方便诊断时定位。
                target_id=f"target.{block.block_kind}.theta",
                # 这个目标读取全局参数 theta。
                parameter_name="theta",
                # block_id 指向实际需要接收参数的程序区块。
                block_id=block.block_id,
                # argument_name 对应区块函数的 theta 形参。
                argument_name="theta",
                # dtype 和 unit 必须与参数声明保持一致。
                dtype="float",
                unit="rad",
            )
        )
    # 返回已经包含参数声明和跨区块映射的管理器。
    return manager


# 创建只需绑定、不触发重编译的默认参数管理器。
manager = parameter_manager()
# 把 theta 绑定为 0.5；duration 使用默认值，theta_twice 由表达式计算。
binding = manager.bind({"theta": 0.5}, bind_id="bind.shared")
# bind_set 为空表示参数类型、范围或表达式求值失败。
if binding.bind_set is None:
    raise RuntimeError([item.to_dict() for item in binding.diagnostics])
# 把同一个 bind_set 投影到 Digital 和 Analog 两个区块。
projection = project_parameter_bindings(manager, program, binding.bind_set)
# 程序或计划为空表示投影失败，不能继续读取绑定结果。
if projection.program is None or projection.plan is None:
    raise RuntimeError([item.to_dict() for item in projection.diagnostics])

# 创建两个明确列出的 theta 参数点，并由 manager 补齐默认和派生参数。
explicit = ParameterScan.explicit(
    scan_id="scan.explicit",
    points=({"theta": 0.25}, {"theta": 0.75}),
).expand(manager)
# 保存每个参数点的投影结果，用于比较计划决策。
explicit_projections = []
# previous 记录上一个投影，让规划器判断当前点是否可复用已有编译结果。
previous = None
# 依次处理展开后的两个绑定集合。
for bind_set in explicit.bind_sets:
    # 投影当前参数点，并把上一个结果作为增量规划参考。
    current = project_parameter_bindings(
        manager,
        program,
        bind_set,
        previous=previous,
    )
    # 保存当前点的程序和计划。
    explicit_projections.append(current)
    # 下一轮用当前点判断参数变化是否需要重新编译。
    previous = current

# 创建把 theta 标记为 recompile 的第二个参数管理器。
recompile_manager = parameter_manager(recompile=True)
# 对 theta 和 duration 做笛卡尔积，共得到四个参数组合。
grid = ParameterScan.cartesian(
    scan_id="scan.grid",
    grid={"theta": [0.1, 0.2], "duration": [1.0, 2.0]},
).expand(recompile_manager)
# 独立投影每个网格点，收集规划器给出的重编译决策。
grid_projections = [
    project_parameter_bindings(recompile_manager, program, bind_set)
    for bind_set in grid.bind_sets
]

# 输出五个参数场景的绑定值和计划决策，不触发任何 backend 执行。
print(
    json.dumps(
        {
            # shared、default、derived、explicit、cartesian 共五类检查。
            "scenario_count": 5,
            "scenarios": {
                "shared_parameter": {
                    "digital_value": projection.program.blocks[0].arguments[0].value,
                    "analog_value": projection.program.blocks[1].arguments[0].value,
                    "source_symbol": (
                        projection.program.blocks[0].arguments[0].source_symbol
                    ),
                },
                "default_binding": {
                    "duration": binding.bind_set.values["duration"],
                },
                "derived_expression": {
                    "theta_twice": binding.bind_set.values["theta_twice"],
                },
                "explicit_scan": {
                    "bind_count": len(explicit.bind_sets),
                    "theta_values": [
                        item.values["theta"] for item in explicit.bind_sets
                    ],
                    "plan_decisions": [
                        item.decision for item in explicit_projections
                    ],
                },
                "cartesian_recompile": {
                    "bind_count": len(grid.bind_sets),
                    "coordinates": [
                        [item.values["duration"], item.values["theta"]]
                        for item in grid.bind_sets
                    ],
                    "plan_decisions": [item.decision for item in grid_projections],
                },
            },
            "execution_ready": projection.plan.execution_ready,
            "mixed_execution_performed": False,
            "backend_called": False,
            "kernel_called": False,
            "network_accessed": False,
            "credentials_loaded": False,
            "hardware_execution": False,
            "cloud_execution": False,
        },
        # 固定键顺序，便于比较多次运行的输出。
        sort_keys=True,
    )
)
