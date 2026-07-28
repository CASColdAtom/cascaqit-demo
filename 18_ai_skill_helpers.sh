#!/usr/bin/env bash
# 任一 helper 执行失败、变量未定义或管道失败时立即退出。
set -euo pipefail

# 解析当前脚本的绝对目录，避免调用方工作目录影响相对路径。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 默认使用同级 coding-skills 仓库中的 cascaqit-programming Skill。
DEFAULT_SKILL_DIR="${SCRIPT_DIR}/../../coding-skills/CASCAQit-Skills/skills/cascaqit-programming"
# 默认使用 CASCAQit-Jupyter 已验收环境中的 Python，确保 SDK 版本一致。
DEFAULT_PYTHON="${SCRIPT_DIR}/../../coding-skills/CASCAQit-Jupyter/artifacts/install-env/bin/python"

# 第一个可选参数允许讲师覆盖 Skill 目录。
SKILL_DIR="${1:-${DEFAULT_SKILL_DIR}}"
# 第二个可选参数允许讲师覆盖 Python 解释器。
PYTHON_BIN="${2:-${DEFAULT_PYTHON}}"

# 第一步说明即将检查 Python、SDK 版本和兼容范围。
echo "[1/3] Check Python and CASCAQit compatibility"
# doctor.py 只读取环境 metadata，不运行量子程序。
"${PYTHON_BIN}" "${SKILL_DIR}/scripts/doctor.py"

# 输出空行，把三组 JSON 结果在终端中分隔开。
echo
# 第二步说明即将查询 Digital 入口的公开能力和限制。
echo "[2/3] Inspect the supported Digital execution boundary"
# capabilities.py 返回 Digital 的入口类、执行模式和已知限制。
"${PYTHON_BIN}" "${SKILL_DIR}/scripts/capabilities.py" --domain digital

# 再输出一个空行，分隔能力查询和模板查询。
echo
# 第三步说明即将定位 Skill 内置的 Bell 示例模板。
echo "[3/3] Locate the bundled Bell program template"
# search_examples.py 按 bell 关键词和 digital 域查找可复用模板。
"${PYTHON_BIN}" "${SKILL_DIR}/scripts/search_examples.py" bell --domain digital
