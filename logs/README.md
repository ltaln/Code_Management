# 日志契约

每个事件追加 event_id、task_id、match_id（可空）、timestamp、state_from、state_to、module_id、attempt、asset_lock_hash、snapshot_hash、evidence_refs、error_code。Execution Log 记录 Model Version、Prompt Version、Data Package ID、完成模块、Warnings 和 Prediction Commit 回执。

进度依据已验证模块与场次计数生成；重复查询不产生完成事件。日志不得写密钥、授权头或整份私人对话。运行日志放在外部存储或 gitignore 的 runtime/，公开仓库只保留格式。
