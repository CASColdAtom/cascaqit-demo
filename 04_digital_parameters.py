"""演示 Digital 线路的参数声明、组合、求逆、重复、绑定和受控变换。"""

from __future__ import annotations

import json

from cascaqit import Circuit


def main() -> None:
    """执行参数化线路和受控线路，并输出可重复检查的结果。"""
    # 创建一个只有 data 量子比特的可复用旋转线路。
    rotation = Circuit(("data",), program_id="program.user.rotation")
    # 声明 theta 参数，并限制它只能在 [-1, 1] 区间内绑定。
    theta = rotation.parameter(
        # 参数名会用于 bind 字典和 ProgramIR。
        "theta",
        # 下界用于参数校验。
        lower_bound=-1.0,
        # 上界用于参数校验。
        upper_bound=1.0,
    )
    # 把符号参数 theta 作为 RX 门角度添加到 data 上。
    rotation.rx(theta, "data")

    # 创建承载组合结果的新线路，避免直接修改原始 rotation 模板。
    declaration = Circuit(("data",), program_id="program.user.ergonomics")
    # 先组合 rotation，再组合其逆线路；理想情况下两段相互抵消。
    declaration.compose(rotation).compose(rotation.inverse())
    # 把整段线路重复两次，并把 theta 绑定为确定值 0.3。
    bound = declaration.repeat(2).bind({"theta": 0.3})
    # shots=0 使用精确概率路径，检查往返线路是否回到 |0>。
    round_trip = bound.run(shots=0, return_probabilities=True)

    # 先创建 X 门，再把它提升为由 control 控制的受控 X 线路。
    controlled_x = Circuit(("target",)).x("target").controlled("control")
    # 创建包含 control 和 target 的准备线路，并沿用受控线路的量子比特顺序。
    prepared = Circuit(controlled_x.qubits, program_id="program.user.controlled")
    # 把 control 准备为 |1> 后组合受控 X，此时 target 也应翻转为 |1>。
    prepared.x("control").compose(controlled_x)
    # 使用精确概率执行，验证最终状态 |11> 的概率。
    controlled_result = prepared.run(shots=0, return_probabilities=True)

    # 输出绑定后的门参数、受控线路结构和两次执行的检查结果。
    print(
        # JSON 输出便于自动测试逐字段比较。
        json.dumps(
            {
                # 示例名称用于区分培训日志中的不同脚本。
                "example": "digital_circuit_ergonomics",
                # 绑定完成后参数列表应为空或只保留已解析参数信息。
                "parameter_names": [item.name for item in bound.parameters],
                # 检查组合、求逆和重复后保留下来的门顺序。
                "bound_gate_names": [gate.name for gate in bound.gates],
                # 从每个参数门中读取实际绑定的 theta 数值。
                "bound_angles": [
                    gate.parameters["theta"] for gate in bound.gates
                ],
                # 旋转与逆旋转往返后，|0> 概率应保持为 1。
                "round_trip_probability_0": (round_trip.probabilities or {})["0"],
                # 输出受控线路采用的逻辑量子比特顺序。
                "controlled_qubits": list(controlled_x.qubits),
                # 输出受控变换展开后的门名称。
                "controlled_gate_names": [gate.name for gate in controlled_x.gates],
                # control 为 |1> 时执行受控 X，最终 |11> 概率应为 1。
                "controlled_probability_11": (
                    controlled_result.probabilities or {}
                )["11"],
                # 明确所有计算都发生在本地，没有访问云端或真实硬件。
                "hardware_execution": False,
                "cloud_execution": False,
                "network_accessed": False,
                "credentials_loaded": False,
            },
            # 固定键顺序，便于培训材料和测试比较输出。
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    # 直接运行脚本时执行参数化和受控线路示例。
    main()
