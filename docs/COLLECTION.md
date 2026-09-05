# 持久采集任务

版本 0.3.0 支持 `采集 YYYY-MM-DD 所有比赛`。通过现有任务入口提交后，后台独立完成 Firecrawl 采集、逐场关联和带 SHA-256 的归档回执。

状态：CREATED → STARTUP_CHECK → COLLECTING → COMPLETED / PARTIAL / FAILED。
COMPLETED 仅代表采集范围内全部页面成功、逐场身份与资料齐全；报告明确标记不是预测。
发现失败页面、截断、身份不明或未归属数据时返回 PARTIAL，不冒充“所有比赛已齐全”。零场也不冒充已验证无比赛。

采集只访问既有 Firecrawl 服务；不调用 OpenAI，不消耗模型推理额度。默认最多 150 页、30 分钟；最多可配 500 页、60 分钟。中断恢复最多三次，旧尝试的原始文件保留。

服务端配置 `FIRECRAWL_ENDPOINT` 与 `FIRECRAWL_API_KEY`。凭据仅从环境传入子进程，任务报告不输出凭据或原始错误日志。
采集目录位于持久数据卷 `collections/<task_id>/<attempt_id>/`，包含原始页、identity-v1 逐场包和 receipt.json。

预测任务只读取本任务重新采集的最新包；新的预测采集成功后，服务器删除此前预测采集目录。独立采集保存的数据只允许回测读取。T-30 模块已取消。

这是服务器任务能力；ChatGPT 原对话自动回传仍未接通。
