"""打印 CASCAQit 版本和四类公开编程入口。"""

from __future__ import annotations

import json

import cascaqit
from cascaqit import AHSProgram, Circuit, GraphProblemIR, LocalBackend
from cascaqit.hybrid import HybridProgram


def main() -> None:
    """收集环境信息，并以便于复制和比对的 JSON 格式输出。"""
    # 把版本号和公开类名放进同一个字典，现场可以一次确认所有入口。
    print(
        # JSON 比普通字典输出更稳定，也方便后续脚本直接读取。
        json.dumps(
            {
                # 确认当前解释器实际导入的 CASCAQit 版本。
                "cascaqit_version": cascaqit.__version__,
                # Digital 程序从 Circuit 类开始创建。
                "digital_entry": Circuit.__name__,
                # Analog 程序从 AHSProgram 类开始创建。
                "analog_entry": AHSProgram.__name__,
                # Hybrid 程序用 HybridProgram 组合 Digital 和 Analog 区块。
                "hybrid_entry": HybridProgram.__name__,
                # Problem API 用 GraphProblemIR 表达图优化问题。
                "problem_entry": GraphProblemIR.__name__,
                # 示例中的所有执行都交给本地 LocalBackend。
                "local_backend": LocalBackend.__name__,
            },
            # 保留中文字符，避免 JSON 输出为 Unicode 转义序列。
            ensure_ascii=False,
            # 使用两空格缩进，让终端输出更容易逐项检查。
            indent=2,
        )
    )


if __name__ == "__main__":
    # 只有直接运行本文件时才执行检查；被其他模块导入时不产生输出。
    main()
