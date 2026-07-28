param(
    # 可从命令行传入 CASCAQit 仓库根目录；默认使用当前目录。
    [string]$RepoRoot = (Get-Location).Path
)

# 任一命令报错时立即停止，避免后续验证在不完整环境中继续执行。
$ErrorActionPreference = "Stop"
# 获取本脚本所在目录，以绝对位置调用同目录下的演示脚本。
$DemoDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 进入 CASCAQit 仓库，确保 pip 能读取项目配置。
Set-Location $RepoRoot
# 使用 Python 3 创建项目级虚拟环境。
py -3 -m venv .venv
# 激活虚拟环境，使后续 python 和 pip 使用 .venv。
& .\.venv\Scripts\Activate.ps1
# 以 editable 方式安装 SDK 和开发依赖。
python -m pip install -e ".[dev]"
# 检查 SDK 版本和四类公开入口。
python "$DemoDir\00_check_environment.py"
# 运行最短 Digital 示例，确认线路可以在本地执行。
python "$DemoDir\03_digital_bell.py"
# 运行最短 Analog 示例，确认模拟器路径可以工作。
python "$DemoDir\05_analog_first_run.py"
