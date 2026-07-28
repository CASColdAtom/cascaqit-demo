# CASCAQit 培训演示代码

这些脚本与 PPT 页码对应。建议将本仓库与 CASCAQit SDK 仓库放在同一目录下。除获取代码和安装脚本外，其余命令均从 CASCAQit 仓库根目录运行；演示结果写入 `../cascaqit-demo/artifacts`。

所有可执行示例都按培训讲解顺序添加了中文注释。关键代码路径中的对象创建、参数设置、编译、运行、结果读取和报告生成均紧贴对应语句说明，讲师可以从任意一步暂停讲解。

## 演示前准备

macOS / Linux：

```bash
../cascaqit-demo/02_install_and_verify.sh "$(pwd)"
```

Windows PowerShell：

```powershell
..\cascaqit-demo\02_install_and_verify.ps1 -RepoRoot (Get-Location).Path
```

## 按页运行

| PPT 页码 | 讲解内容 | 文件 | 运行命令 |
|---:|---|---|---|
| 2-3 | 当前能力与使用入口 | `00_check_environment.py` | `python3 ../cascaqit-demo/00_check_environment.py` |
| 4 | 从内网 GitLab 获取代码 | `01_get_code.sh` | `../cascaqit-demo/01_get_code.sh <仓库地址> <培训版本>` |
| 5 | 安装与验证 | `02_install_and_verify.sh` / `.ps1` | 使用上方对应系统命令 |
| 6 | Digital Bell 线路 | `03_digital_bell.py` | `python3 ../cascaqit-demo/03_digital_bell.py` |
| 7 | 参数化线路与复用 | `04_digital_parameters.py` | `python3 ../cascaqit-demo/04_digital_parameters.py` |
| 8 | Analog 基本运行 | `05_analog_first_run.py` | `python3 ../cascaqit-demo/05_analog_first_run.py` |
| 9 | Hybrid D-A-D 程序 | `06_hybrid_workflow.py` | `python3 ../cascaqit-demo/06_hybrid_workflow.py` |
| 10 | 参数扫描 | `07_parameter_scan.py` | `python3 ../cascaqit-demo/07_parameter_scan.py` |
| 11 | Problem API | `08_problem_api.py` | `python3 ../cascaqit-demo/08_problem_api.py --output-dir ../cascaqit-demo/artifacts/problem_api --shots 16 --language zh` |
| 12 | 3x3 MIS 三条路线 | `09_problem_three_routes.py` | `python3 ../cascaqit-demo/09_problem_three_routes.py --output-dir ../cascaqit-demo/artifacts/problem_routes --shots 16 --language zh` |
| 13 | QAOA 优化 | `10_qaoa_mis.py` | `python3 ../cascaqit-demo/10_qaoa_mis.py` |
| 14 | VQE 有限采样 | `11_vqe_sampled_energy.py` | `python3 ../cascaqit-demo/11_vqe_sampled_energy.py --output-dir ../cascaqit-demo/artifacts/vqe` |
| 15 | 本地模拟方法 | `12_simulation_methods.py` | `python3 ../cascaqit-demo/12_simulation_methods.py` |
| 16 | 结果与诊断 | `13_result_diagnostics.py` | `python3 ../cascaqit-demo/13_result_diagnostics.py` |
| 17 | 阵列与寻址 | `14_site_addressing.py` | `python3 ../cascaqit-demo/14_site_addressing.py --output ../cascaqit-demo/artifacts/site_addressing.html` |
| 17 | 控制与阵列生命周期 | `15_control_register.py` | `python3 ../cascaqit-demo/15_control_register.py --output ../cascaqit-demo/artifacts/control_register.html` |
| 17 | 完整 Hybrid 实验 | `16_complete_hybrid.py` | `python3 ../cascaqit-demo/16_complete_hybrid.py --output ../cascaqit-demo/artifacts/complete_hybrid.html` |
| 18 | 3x3 MIS 完整应用 | `17_3x3_mis.py` | `python3 ../cascaqit-demo/17_3x3_mis.py --output-dir ../cascaqit-demo/artifacts/3x3_mis --language zh` |
| AI Skill 章节 | 助手工具与提示词 Demo | `18_ai_skill_helpers.sh` / `18_ai_skill_demo_prompt.md` | `../cascaqit-demo/18_ai_skill_helpers.sh` |
| Jupyter 章节 | Program、Result、Diagnostics 与 Visualization 渲染 | `19_jupyter_read_only_renderers.ipynb` | 在 JupyterLab 4 或 Notebook 7 中打开并运行全部单元格 |

## 现场演示建议

先运行 `00_check_environment.py`、`03_digital_bell.py` 和 `05_analog_first_run.py`，确认环境稳定。第 17、18 页的完整示例会生成 HTML 报告，建议培训前预运行一次并保留产物，现场再选择其中一个脚本完整执行。

所有脚本默认使用本地执行路径和固定随机种子，不需要访问云端或真实硬件。AI Skill 演示的普通 Python 执行属于受信工作区执行，不是安全沙箱；Jupyter 演示使用只读 MIME renderer，不会从展示数据修改 ProgramIR 或 ResultIR。
