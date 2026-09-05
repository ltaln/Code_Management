# 项目记忆 · 2026-09-06

项目：HH520 Football AI System。仓库：`ltaln/Code_Management`。用户要求工作模式持续推进并尽量减少 Codex 余额消耗。

当前工程版本 0.4.19。手机在私人 GPT **HH520 Football AI** 中发送 `预测 YYYY-MM-DD 所有比赛`，服务器创建持久任务并调用 Firecrawl。每个预测命令必须重新采集，只能读取本任务刚生成的最新快照；新预测采集成功后删除此前预测采集目录。独立采集与旧数据只允许回测读取。

用户于 2026-09-06 明确取消 T-30 模块。13 个分析模块、HH520-PROMPT-V2.1 和其他预测逻辑不变；Upgrade Package 1 = PARKED。预测输入中的盘口时间序列只向 GPT 提供最近一次快照。

手机单命令真实验收已完成：全新会话只发送一条预测命令，任务 `9f1be262350f47a89f9386348c7ffebd` 在 71.24 秒内完成 30 页采集、0 失败和 9/9 场预测，Prediction Commit 为 `HH520-20260907-4666535aec397cff`。

尚未完成：Phase 6 回测评价运行服务及可选 GitHub Prediction Commit 镜像。服务器凭据只保存在服务器私有配置和 ChatGPT Action 密钥存储，不得写入仓库、日志或回复。
