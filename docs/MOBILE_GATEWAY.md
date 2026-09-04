# 手机命令接入 · 工程版本 0.2.0

已实现：中文命令解析、持久任务、请求去重、取消、启动检查、报告查询和中断恢复。仅“检查连接”任务可完成；比赛预测/回测会列出真实阻塞，未接入采集或 GPT。没有修改任何冻结模型文件或资产锁。

## 最省成本的接入验证

先在现有服务器旁部署命令服务，使用已有 HTTPS 网关和独立路径/域名。手机入口先只测试“检查连接”：任务创建 → 后台检查 → 查询报告。这个测试不调用 Firecrawl、OpenAI 或预测模型。当前没有部署地址，手机端还不可用。

HTTP 接口：POST /v1/tasks（request_id 与 command）；GET /v1/tasks/{id}；GET /v1/tasks/{id}/report；POST /v1/tasks/{id}/cancel。全部使用 Bearer 认证。相同 request_id 和命令重试返回原任务；相同 ID 改命令返回 409。命令支持“预测 YYYY-MM-DD 所有比赛”“回测 YYYY-MM-DD 所有比赛”“检查连接”。日期使用赛程列表日期，不能将过去日期自动改为今天。

## 本地与部署

本地设置 HH520_GATEWAY_TOKEN 为至少 32 字符随机私有值，运行 `python -m task_manager.service`。服务仅监听 127.0.0.1:8765；标准库 HTTP 服务仅用于本地验证。

Linux 部署草案在 deploy/compose.yaml：API 使用 Gunicorn，worker 为独立进程，SQLite 放在共享持久卷，两服务各 192 MiB 内存限制。设置令牌后运行 `docker compose -f deploy/compose.yaml up -d --build`。需要可访问现有服务器并完成 Docker 构建验证；本次尚未在服务器执行。不要删除持久卷。

现有 Firecrawl 文档提到 4GB 主机和独立 Caddy 容器：部署前核查可用资源及网关容器到服务的路由，不能直接假设容器的 localhost 指向宿主机。保留原采集器和网关配置，不覆盖现有服务。HTTPS 网关还需限制请求体、速率与连接时间；本任务入口是单用户私有服务。

## 手机 ChatGPT 接入边界

integrations/gpt-actions.openapi.json 是候选 Actions 契约。把服务器示例域名替换为实际 HTTPS 域名，在 GPT 编辑器配置 Bearer 密钥；密钥不放在 schema 或 Prompt 内。账户和手机端支持情况仍须实际验证。

Actions 创建任务后立即返回编号，随后调用状态/报告接口。接口不得等候长时间推理。当前实现是查询接口，**没有主动回写 ChatGPT 原会话的能力**；不能以这一步声称“关闭手机也会自动收到分析结果”已实现。推送或会话续接仍须独立验证可用官方通道，未验证前不承诺。

依据：[Actions 认证](https://developers.openai.com/api/docs/actions/authentication)、[45 秒接口超时](https://developers.openai.com/api/docs/actions/production)、[后台回调发送到自有服务器](https://developers.openai.com/api/docs/guides/webhooks)。

## 额度控制

此次不重复抓取比赛、不运行付费分析、不重写采集器、不引入复杂数据库。先验证连接和任务恢复，解决原模型资料差异后再用一场比赛联调，最后扩展到全天。GPT Prompt 未核对前不生成替代版。未来网络重试查询原任务，避免重复付费调用。

## 验收与限制

`python -m unittest discover -s tests -p test_gateway.py` 覆盖命令、去重、持久化、阻塞、连接检查、租约恢复、取消、认证及真实本地 HTTP。60 秒租约仅用于当前短启动检查；未来长时间执行必须加入续租、每模块检查点及外部调用幂等，不能直接复用为长任务完成态。
