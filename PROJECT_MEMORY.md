# 项目记忆 · 2026-09-05

项目：HH520 Football AI System。仓库：`ltaln/Code_Management`。用户要求工作模式持续推进，并尽量减少 Codex 余额消耗；优先复用现有资产、离线测试和一次性验收。

冻结条件：模型 HH520 V2.1-Test；Prompt HH520-PROMPT-V2.1；Upgrade Package 1 = PARKED；不得修改核心逻辑、权重、公式或参数。GPT 负责定性分析，服务器负责事实采集和持久任务，GitHub 保存资产和代码。

最新 0.4.2：已直接读取并核验原 ChatGPT 对话，恢复最终执行顺序、DCS、风险/冲突规则和 Prediction Archive First。私人 GPT **HH520 Football AI** 已创建为“只有我”，Actions 8/8 解析通过，Bearer 认证已保存，“检查连接”端到端返回 COMPLETED 且明确不是预测。网页搜索和图片生成已关闭，避免绕过唯一数据包。

数据侧已验证真实整日采集：78 页、0 失败、14/14 场、98 个文件 Hash 通过。预测侧实现逐场有界输入、T-30 门禁、13 模块顺序验证、逐场不可变保存和服务器 Prediction Commit。17 项本地测试通过，服务器镜像测试通过，27 个冻结文件锁通过，运行就绪检查为 true。

仍需真实证据：首个未来日期完整 Prediction Commit；历史 T-30 重建与回测评价服务；可选 GitHub Prediction Commit 镜像。过去/当天预测和无档案回测必须继续阻塞，不能用赛后网页补造预测。

服务器凭据只保存在服务器私有配置和 ChatGPT Action 密钥存储，不得写入仓库、日志或回复。用户没有备份，不再要求用户上传旧文件。
