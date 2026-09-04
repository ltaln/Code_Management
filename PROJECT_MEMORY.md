# 项目记忆 · 2026-09-04

最新 0.3.0：服务代码 5bdad72915b6445bd337080b59d7af329209aef2 已上线。自建 Firecrawl 持久采集真实验收通过：78 页、0 失败、14/14 场、98 文件 Hash 通过；14 项服务测试通过，27 个冻结文件未改。用户没有备份，必须自行恢复原对话；Chrome 运行正常但缺少浏览器扩展和原生连接组件，需通过 Browser 插件安装流程修复后读取。不得重复要求用户上传备份。历史预测记录只能用于溯源，不能反推或补造模型参数。

项目：HH520 Football AI System。目标仓库：ltaln/Code_Management。当前执行方式已由用户改为工作模式，旧材料中的“不使用 Codex”不再是本次要求。

模型：HH520 V2.1-Test；Prompt：HH520-PROMPT-V2.1；Upgrade Package 1：PARKED。保持 GPT 负责分析、GitHub 保存资产、服务器提供数据、Task Manager 负责持续调度。不得因工程化改写模型。

已实际落地：模型原文与分类资产、Prompt 逐字迁移、README、唤醒体系、Phase 1–6 文档、接口契约、资产校验工具。最终验证和远端提交证据见 docs/VALIDATION.md、docs/DELIVERY.json（交付时生成）。

未完成：数值规则与流程顺序核对、独立回测 Prompt、数据服务与 GPT 执行器接入、手机端联调、真实端到端验收。不能宣称完整系统已运行。

原对话的 30% 等数字没有可复核工时或验收分母，本次不沿用。状态只由实际产物和验收证据更新，查询不会增加进度。

下一步：处理 docs/GAPS.md；保存来源、差异与验证证据后才能打开运行开关。不要拿近期预测的比分或置信分数反推参数。不要修改旧数据仓库的现有预测系统。

新增实际来源：S07 为旧仓库已保存的冻结模型快照，硬规则与独立市场均已保留。Master/Prediction/Backtest v1.1 与后期 Prompt V2.1 的映射未明确，加入 BASELINE_REVISION_CONFLICT。

工程进展 0.2.0：实际实现 task_manager/service.py，SQLite 持久任务、worker、取消和报告 API；连接检查不产生预测。支持候选 Actions schema 与 Docker 部署草案。缺服务器部署入口，未作手机端验收。用户要求尽量节省 Codex 额度：复用资产、先离线测试、一次一场联调、不反复采集。

部署更新：已使用用户提供的服务器完成 /opt/hh520 部署，HTTPS 地址与验收见 docs/DEPLOYMENT.md。原 Firecrawl 未重启、冻结模型未改。私有任务令牌仅在服务器 /etc/hh520/gateway.env，不是 SSH 密码。手机 ChatGPT 编辑器读取超时，账户侧连接未建立；不能宣称全自动预测可用。
