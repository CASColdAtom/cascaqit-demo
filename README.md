# CASCAQit Demo

这些示例覆盖 CASCAQit 的主要使用方式。除获取代码和安装脚本外，其余命令均从 CASCAQit 仓库根目录运行；运行结果默认写入 `../cascaqit-demo/artifacts`。

所有可执行示例都添加了中文注释。对象创建、参数设置、编译、运行、结果读取和报告生成等关键步骤均在对应语句旁说明，便于按需阅读和修改。

## 演示前准备

macOS / Linux：

```bash
../cascaqit-demo/02_install_and_verify.sh "$(pwd)"
```

Windows PowerShell：

```powershell
..\cascaqit-demo\02_install_and_verify.ps1 -RepoRoot (Get-Location).Path
```

## 示例列表

| 序号 | 示例 | 文件 | 运行命令 |
|---:|---|---|---|
| 1 | 当前能力与使用入口 | `00_check_environment.py` | `python3 ../cascaqit-demo/00_check_environment.py` |
| 2 | 从内网 GitLab 获取代码 | `01_get_code.sh` | `../cascaqit-demo/01_get_code.sh <仓库地址> <分支、标签或提交号>` |
| 3 | 安装与验证 | `02_install_and_verify.sh` / `.ps1` | 使用上方对应系统命令 |
| 4 | Digital Bell 线路 | `03_digital_bell.py` | `python3 ../cascaqit-demo/03_digital_bell.py` |
| 5 | 参数化线路与复用 | `04_digital_parameters.py` | `python3 ../cascaqit-demo/04_digital_parameters.py` |
| 6 | Analog 基本运行 | `05_analog_first_run.py` | `python3 ../cascaqit-demo/05_analog_first_run.py` |
| 7 | Hybrid D-A-D 程序 | `06_hybrid_workflow.py` | `python3 ../cascaqit-demo/06_hybrid_workflow.py` |
| 8 | 参数扫描 | `07_parameter_scan.py` | `python3 ../cascaqit-demo/07_parameter_scan.py` |
| 9 | Problem API | `08_problem_api.py` | `python3 ../cascaqit-demo/08_problem_api.py --output-dir ../cascaqit-demo/artifacts/problem_api --shots 16 --language zh` |
| 10 | 3x3 MIS 三条路线 | `09_problem_three_routes.py` | `python3 ../cascaqit-demo/09_problem_three_routes.py --output-dir ../cascaqit-demo/artifacts/problem_routes --shots 16 --language zh` |
| 11 | QAOA 优化 | `10_qaoa_mis.py` | `python3 ../cascaqit-demo/10_qaoa_mis.py` |
| 12 | VQE 有限采样 | `11_vqe_sampled_energy.py` | `python3 ../cascaqit-demo/11_vqe_sampled_energy.py --output-dir ../cascaqit-demo/artifacts/vqe` |
| 13 | 本地模拟方法 | `12_simulation_methods.py` | `python3 ../cascaqit-demo/12_simulation_methods.py` |
| 14 | 结果与诊断 | `13_result_diagnostics.py` | `python3 ../cascaqit-demo/13_result_diagnostics.py` |
| 15 | 阵列与寻址 | `14_site_addressing.py` | `python3 ../cascaqit-demo/14_site_addressing.py --output ../cascaqit-demo/artifacts/site_addressing.html` |
| 16 | 控制与阵列生命周期 | `15_control_register.py` | `python3 ../cascaqit-demo/15_control_register.py --output ../cascaqit-demo/artifacts/control_register.html` |
| 17 | 完整 Hybrid 实验 | `16_complete_hybrid.py` | `python3 ../cascaqit-demo/16_complete_hybrid.py --output ../cascaqit-demo/artifacts/complete_hybrid.html` |
| 18 | 3x3 MIS 完整应用 | `17_3x3_mis.py` | `python3 ../cascaqit-demo/17_3x3_mis.py --output-dir ../cascaqit-demo/artifacts/3x3_mis --language zh` |
| 19 | AI Coding Skill | `18_ai_skill_helpers.sh` / `18_ai_skill_demo_prompt.md` | `../cascaqit-demo/18_ai_skill_helpers.sh` |
| 20 | Jupyter 渲染器 | `19_jupyter_read_only_renderers.ipynb` | 在 JupyterLab 4 或 Notebook 7 中打开并运行全部单元格 |

## 建议运行顺序

先运行 `00_check_environment.py`、`03_digital_bell.py` 和 `05_analog_first_run.py`，确认环境稳定。后面的完整示例会生成 HTML 报告，首次使用时可先运行一次并保留产物，再选择需要的脚本继续查看。

所有脚本默认使用本地执行路径和固定随机种子，不需要访问云端或真实硬件。AI Skill 演示的普通 Python 执行属于受信工作区执行，不是安全沙箱；Jupyter 演示使用只读 MIME renderer，不会从展示数据修改 ProgramIR 或 ResultIR。
