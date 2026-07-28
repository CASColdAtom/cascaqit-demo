# CASCAQit AI Coding Skill Demo

## 准备

从接收 Skill 的项目目录安装：

```bash
npx skills add ../CASCAQit-Skills --skill cascaqit-programming -a codex
```

检查 Skill 自带的确定性工具：

```bash
../cascaqit-demo/18_ai_skill_helpers.sh
```

## Demo 1：从需求到可运行代码

向已安装 Skill 的 Agent 输入：

```text
请用 CASCAQit 公开 API 创建并运行一个两量子比特 Bell 线路：
32 shots，seed=7；保存为 examples/training_bell.py，实际执行它，
然后说明 counts 总数、bit_order、measurement_keys 和当前执行边界。
```

验收时必须看到：源码路径、完整运行命令、退出状态、counts 总数为 32、比特顺序说明，以及未访问云端和真实硬件的边界说明。

## Demo 2：按结构化诊断修复

向已安装 Skill 的 Agent 输入：

```text
构造一个原子间距不合法的两位点 Analog 程序，保留原始结构化诊断，
根据 diagnostic code、object_path 和 suggestion 修复源码，再运行同一校验。
不要静默修复，也不要把本地校验描述成硬件验证。
```

验收时必须看到：修复前诊断、诊断对应的源码改动、修复后的校验结果，以及本地模拟边界。
