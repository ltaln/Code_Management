# 实际验证记录 · 2026-09-04

本次资产包通过 11 项检查。验证范围为文件完整性、冻结保护、接口契约和唤醒行为；未运行真实预测或回测。

|检查|结果|
|---|---|
|原始资产、27 个锁定文件、7 份来源 Hash|PASS|
|Prompt 与来源代码块逐字比较|PASS；包含在原始资产检查|
|修改 Prompt 的副本|检测到 PROMPT_NOT_VERBATIM|
|移走模型文件的副本|检测到 MISSING_ASSET|
|新增未锁模型文件的副本|检测到 UNLOCKED_ASSET|
|无效配置 JSON 的副本|检测到 INVALID_JSON|
|文档失效链接的副本|检测到 BROKEN_LINK|
|提前打开预测开关的副本|检测到 RUNTIME_SWITCH_INVALID_FOR_ASSET_RELEASE|
|缺少 Phase 6 文件的副本|检测到 MISSING|
|运行就绪检查|正确返回退出码 2，列出阻塞|
|唤醒脚本|通过资产校验后显示冻结状态及缺口|
|五份 JSON Schema 与任务示例|Draft 2020-12 校验通过；错误日期被拒绝|

校验报告中的运行就绪为 false，这是如实反映未连接执行器和来源缺口。不能把本报告当作模型准确率、采集成功或自动运行证据。

旧冻结快照来自 `ltaln/firecrawl-gpt-predictor` 的提交 `cb20b37e96b047007e21d6de436107d34287972e`，从 Git blob 原样读取。旧仓库仅只读访问，本次未推送修改。

本地重现：`python scripts/verify_assets.py`；`python scripts/wake.py`；`python scripts/verify_assets.py --require-ready`。完整负向测试见 tests/check_delivery.py，额外验证依赖在 tests/requirements.txt。
