#!/usr/bin/env bash
# 任一安装或验证步骤失败时立即停止，避免在错误环境中继续演示。
set -euo pipefail

# 允许显式传入 CASCAQit 仓库根目录；默认使用当前目录。
repo_root="${1:-$(pwd)}"
# 解析本脚本所在目录，保证从任意位置运行都能找到演示文件。
demo_dir="$(cd "$(dirname "$0")" && pwd)"

# 进入 CASCAQit 仓库，后续 editable install 才能找到 pyproject.toml。
cd "$repo_root"
# 创建项目级虚拟环境，避免污染系统 Python。
python3 -m venv .venv
# 激活虚拟环境，使后续 python3 和 pip 都指向 .venv。
source .venv/bin/activate
# 以 editable 方式安装 SDK 和开发依赖，代码修改后无需重复安装。
python3 -m pip install -e ".[dev]"
# 先检查版本和公开入口，确认安装位置正确。
python3 "$demo_dir/00_check_environment.py"
# 再运行最短 Digital 示例，确认线路执行与结果读取正常。
python3 "$demo_dir/03_digital_bell.py"
# 最后运行最短 Analog 示例，确认校验、离散化和本地模拟正常。
python3 "$demo_dir/05_analog_first_run.py"
