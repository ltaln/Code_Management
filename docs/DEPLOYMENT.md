# 已验证部署 · 2026-09-04

任务入口：https://hh520.156.225.23.17.sslip.io

运行代码提交：03dd2f99370d3fc7db7209de0d6f20354e4f344a。镜像 ID：sha256:b1a12cd5ef94fa2d46f8cc9d9011f4c509dcef6250a41ccdc5f3277c5d166880。

## 实际部署

- 项目位于 /opt/hh520；独立 Docker Compose 项目名 hh520。
- hh520-gateway-1 提供 API；hh520-worker-1 执行持久任务的启动检查。
- 共享卷 hh520_hh520_state 保存 SQLite。两容器均设置 unless-stopped 和 192 MiB 内存限制。
- gateway 加入现有 firecrawl_backend 网络，独立别名 hh520-gateway。宿主端口仅绑定 127.0.0.1:8765。
- 现有 Caddy 新增上述 HTTPS 主机并代理到 hh520-gateway:8765；原 Firecrawl 站点块逐字保留。
- 认证值由服务器随机生成，保存在 /etc/hh520/gateway.env，权限 0600；没有写入代码、报告或 GitHub。SSH 凭据也未保存到项目。
- 服务实测内存约 25 MiB + 12 MiB，不包括原 Firecrawl 服务。

## 验收证据

|检查|结果|
|---|---|
|公网 TLS 证书校验|通过，未跳过证书验证|
|未带认证访问 /health|401 UNAUTHORIZED|
|带认证访问 /health|gateway ready；prediction blocked|
|检查连接任务|COMPLETED，明确标注“不是比赛预测”|
|预测 2026-08-11 所有比赛|BLOCKED，未采集或生成预测|
|重启新建 API 与 worker 后读取原报告|报告逐字一致，持久化通过|
|旧 Firecrawl 服务|仍为原启动实例，未重启|
|27 个冻结资产|服务器校验 PASS|

连接检查 task_id：ca3c20d6acdd4ae7a395db6caa5e329d。完整服务器验收记录位于 /etc/hh520/acceptance.json。

## 运维

部署覆盖配置：/etc/hh520/compose.override.json。执行命令使用：

```text
docker compose -p hh520 --env-file /etc/hh520/gateway.env -f /opt/hh520/deploy/compose.yaml -f /etc/hh520/compose.override.json ps
```

原 Caddy 备份：/etc/firecrawl/Caddyfile.pre-hh520-20260904。发布时先 caddy validate 再 caddy reload；新任务服务维护不需要重启采集器。回滚只移除本次 HH520 主机块并重载，不覆盖后续其他网关修改。不可删除任务持久卷。

## 未完成

ChatGPT 账户中的 Actions 配置尚未创建；内置浏览器打开/读取 GPT 编辑器连续超时。当前服务只支持任务查询，不能主动回写 ChatGPT 原会话。真实采集与 GPT 分析执行器仍未接通，原模型资料差异仍待核对。没有将连接检查或服务器上线计为预测完成。

域名延续现有服务器所用 sslip.io 公共 DNS 方式，未购买新域名或托管服务。本轮没有付费采集或推理调用。
