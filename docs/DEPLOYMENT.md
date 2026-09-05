# 已验证部署 · 2026-09-06

任务入口：<https://hh520.156.225.23.17.sslip.io>

私人 GPT：<https://chatgpt.com/g/g-6a9b59f4ba4c8191ae091b40ae095160-hh520-football-ai>

运行镜像：`hh520-gateway:0.4.19`。

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
|OpenAPI|0.4.19，13 个路径、14 个操作，已重新导入私人 GPT|
|私人 GPT|“只有我”；Actions Bearer 已保存|
|GPT“检查连接”|COMPLETED；任务、后台检查、报告返回成功；明确不是预测|
|真实整日采集|78 页、0 失败、14/14 场、98 文件 Hash 通过|
|运行就绪|资产 PASS；runtime_ready=true；无 blocker|
|本次运行检查|gateway 与 worker 均运行；按用户要求未运行测试|
|手机单命令预测|全新会话仅发一条命令；71.24 秒，30 页零失败，9/9 场，Commit `HH520-20260907-4666535aec397cff`，归档 Hash 一致|
|预测采集清理|删除 7 个旧预测采集目录；服务器现有 1 个预测目录、5 个独立采集目录|

## 运维

覆盖配置：`/etc/hh520/compose.override.json`。服务查询：

```text
docker compose -p hh520 --env-file /etc/hh520/gateway.env -f /opt/hh520/deploy/compose.yaml -f /etc/hh520/compose.override.json ps
```

不可删除任务持久卷。更新前先保留现有任务数据；Caddy 变更先验证再重载。Phase 6 回测和可选归档镜像仍按 [缺口](GAPS.md) 执行。
