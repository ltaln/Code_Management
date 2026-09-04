# Phase 1–6 路线与附件映射

本次沿用最近会话的分期：Phase 1 模型迁移与基础层，Phase 2 项目管理。附件的 Phase 1 基础层、Phase 2 迁移分别被纳入本路线 Phase 1 和 Phase 2 的管理验收，无内容被跳过。

1. [Phase 1](phases/phase_1_assets.md)：来源盘点、模型和 Prompt 迁移、README/记忆/唤醒；先核对完整性。
2. [Phase 2](phases/phase_2_management.md)：版本、配置、冻结校验、发布与回滚。
3. [Phase 3](phases/phase_3_tasks.md)：任务格式、状态、幂等、恢复与持久服务。
4. [Phase 4](phases/phase_4_data.md)：采集接口、快照、来源及一致性校验。
5. [Phase 5](phases/phase_5_prediction.md)：GPT 交接、模块执行证据、预测提交与输出。
6. [Phase 6](phases/phase_6_backtest.md)：档案优先、赛前信息隔离与评价。

先完成资产核验，再实现调度与数据接口，再预测联调，最后回测。设计可以先落地；执行验收必须按依赖通过。每阶段只有达到列出的退出条件才可标记 COMPLETE。
