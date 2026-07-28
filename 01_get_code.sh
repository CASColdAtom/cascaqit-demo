#!/usr/bin/env bash
# 任一命令失败、使用未定义变量或管道中间失败时立即退出。
set -euo pipefail

# 第一个参数必须是仓库地址；缺失时直接打印用法并退出。
repo_url="${1:?usage: 01_get_code.sh <gitlab-repo-url> <training-ref> [destination]}"
# 第二个参数必须是要检出的分支、标签或提交号。
training_ref="${2:?usage: 01_get_code.sh <gitlab-repo-url> <training-ref> [destination]}"
# 第三个参数可选；未提供时把仓库克隆到 CASCAQit 目录。
destination="${3:-CASCAQit}"

# 从内网 GitLab 克隆 CASCAQit 仓库到目标目录。
git clone "$repo_url" "$destination"
# 后续版本切换和 commit 查询都在新克隆的仓库中执行。
cd "$destination"
# 优先按分支切换；若不是分支，再按标签或提交号检出。
git switch "$training_ref" 2>/dev/null || git checkout "$training_ref"
# 打印最终检出的短 commit，便于确认当前代码版本。
git rev-parse --short HEAD
