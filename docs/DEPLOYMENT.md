# 已验证部署 · 2026-09-05

任务入口：<https://hh520.156.225.23.17.sslip.io>

私人 GPT：<https://chatgpt.com/g/g-6a9b59f4ba4c8191ae091b40ae095160-hh520-football-ai>

运行镜像：`hh520-gateway:0.4.7`。

## 部署结构

- 项目位于 `/opt/hh520`，Docker Compose 项目名 `hh520`。
- `hh520-gateway-1` 提供 API，`hh520-worker-1` 执行持久任务和 Firecrawl 采集。
- 共享卷 `hh520_hh520_state` 保存 SQLite、快照和 Prediction Commit；两容器均为 `unless-stopped`。
- Caddy 提供公网 TLS；宿主服务端口只绑定 `127.0.0.1:8765`。
- OpenAPI schema 可公开读取以供 ChatGPT 导入；所有任务接口仍要求 Bearer。
- 认证值保存在 `/etc/hh520/gateway.env` 和 ChatGPT Action 密钥存储，未写入 GitHub、报告或本文。

## 验收

|检查|结果|
|---|---|
|公网 TLS|通过，未跳过证书验证|
|未认证任务接口|401 UNAUTHORIZED|
|OpenAPI|0.4.7，12 个路径、13 个操作，ChatGPT 解析无错误|
|私人 GPT|“只有我”；Actions Bearer 已保存|
|GPT“检查连接”|COMPLETED；任务、后台检查、报告返回成功；明确不是预测|
|真实整日采集|78 页、0 失败、14/14 场、98 文件 Hash 通过|
|运行就绪|资产 PASS；runtime_ready=true；无 blocker|
|服务器镜像测试|20 项通过|
|真实未来预测|2026-09-07，9/9 场，Commit `HH520-20260907-030e9c69b9c36273`，归档 Hash 一致|

## 运维

覆盖配置：`/etc/hh520/compose.override.json`。服务查询：

```text
docker compose -p hh520 --env-file /etc/hh520/gateway.env -f /opt/hh520/deploy/compose.yaml -f /etc/hh520/compose.override.json ps
```

不可删除任务持久卷。更新前先保留现有任务数据；Caddy 变更先验证再重载。全新日期的单命令无续令验收和 Phase 6 回测仍按 [缺口](GAPS.md) 执行。
