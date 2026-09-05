# HH520 Football AI System

工程版本 0.4.19。私人 GPT、HTTPS 任务网关、自建 Firecrawl、全量紧凑 GPT 交接和不可变 Prediction Commit 已接通。每个预测命令强制重新采集，只读取该任务最新一次快照；服务器只保留最近一次预测采集，旧采集仅供回测。手机可打开 **HH520 Football AI**，发送 `预测 YYYY-MM-DD 所有比赛`。T-30 模块已取消；其余 HH520 V2.1-Test 分析逻辑不变，Upgrade Package 1 保持 PARKED。

当前已验证：原始对话恢复、持久任务、真实整日采集、14 个 ChatGPT Actions、Bearer 认证，以及全新会话仅发一条命令后自动完成 2026-09-07 的 9/9 场真实 Prediction Commit。回测执行服务仍待建设。

## 使用入口

私人 GPT：<https://chatgpt.com/g/g-6a9b59f4ba4c8191ae091b40ae095160-hh520-football-ai>

可用命令：

- `检查连接`
- `采集 YYYY-MM-DD 所有比赛`
- `预测 YYYY-MM-DD 所有比赛`
- `回测 YYYY-MM-DD 所有比赛`（可以读取已有 Prediction Commit 或服务器旧采集数据）

每次预测都重新采集，不能读取旧任务快照。任务和中间进度保存在服务器；新的预测采集成功后会删除更早的预测采集目录，只保留最新一次。旧采集读取权限只属于回测。

## 验证

```text
python scripts/verify_assets.py
python scripts/verify_assets.py --require-ready
python -m unittest discover -s tests -v
```

`--require-ready` 当前应返回成功。它证明资产和运行接线完整，不代表某一天的预测已经完成。

## 架构

```mermaid
flowchart TD
    U[手机 ChatGPT 命令] --> G[HH520 私人 GPT]
    G --> T[HTTPS 任务网关]
    T --> W[持久 Worker]
    W --> F[自建 Firecrawl]
    F --> S[唯一赛前快照与逐场包]
    S --> G
    G --> P[冻结模块完整分析]
    P --> C[服务器不可变 Prediction Commit]
    C --> U
    C --> B[独立回测与评价]
```

GitHub 保存模型资产、Prompt、工程代码和版本；服务器保存任务、采集快照和运行时 Prediction Commit。模型核心、权重、公式和参数没有因工程化而修改。

## 仓库地图

|目录|用途|
|---|---|
|models/HH520_V2.1-Test|冻结模型说明、流程、指标、模块与状态清单|
|prompts / rules / calibration|原始 Prompt、规则和校准入口|
|config / workflows|运行配置与最终冻结执行顺序|
|task_manager|持久任务、恢复、取消、GPT 交接与归档 API|
|data_engine|Firecrawl 新鲜采集、身份绑定、最新快照筛选和有界 GPT 输入|
|prediction|Prediction Commit、记录契约和报告模板|
|backtest / evaluation|Prediction Archive First 与评价契约|
|versions|资产锁与版本指针|
|docs|Phase 1–6、来源、部署、验收和剩余缺口|

接管顺序：先读 [项目记忆](PROJECT_MEMORY.md)、[唤醒文件](WAKE_CODE.md)、[实际状态](docs/STATUS.md)，再读 [部署](docs/DEPLOYMENT.md) 和 [缺口](docs/GAPS.md)。
