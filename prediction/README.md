# GPT 执行与 Prediction Commit 契约

本目录只定义交接边界，不包含数值预测算法。GPT 输入绑定 task_id、asset_git_sha、asset_lock_hash、model_version、prompt_version、prompt_hash、snapshot_id、snapshot_hash、as_of 与范围。

运行前先读取重要注意事项并核验全部冻结资产。实际执行主链在 workflows/prediction.json，当前有来源顺序冲突，因此该文件是参考。DCS、赔率异常、风险、冲突检测必须保留；不能因为最终架构图没展开就省略。

逐模块返回：module_id、status、evidence_refs、结构化输出、异常和可核验依据摘要。原文允许的字段降级仍需执行相关模块并说明缺失，不以虚构 completed 补全。

Prediction Commit：先写不可变预测文件与数据引用，计算文件 Hash，再提交，最后把远端 commit SHA 写入单独 receipt。Commit ID 无法提前写入产生自身 Hash 的文件；回执与内容分离解决自引用。

提交应使用唯一 prediction_id 和条件写入，禁止覆盖原预测；COMMITTING 超时先查询回执。提交回执验证前不能称已完成。批次按场次记录，只有全部完成才返回 COMPLETED。

报告先说明采集、审计、各模块、异常与校准，再按比分、半全场、其他市场列出结果。Confidence 与单一比分概率分别记录，不能互相替代。结果未知用 null 和原因，不用 0 冒充结果。

S07 补充：八个独立市场模型和 DNA 处理不可删减；冲突可保留或输出 PASS，不能强行一致。未核对版本栈前自动执行关闭。报告应支持 S/A/B/C/PASS、DNA Version 与每市场概率。
