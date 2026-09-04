# 已验证部署 · 2026-09-04

任务入口：https://hh520.156.225.23.17.sslip.io

当前运行代码：5bdad72915b6445bd337080b59d7af329209aef2，镜像标签 hh520-gateway:0.3.0。旧版运行提交为 03dd2f99370d3fc7db7209de0d6f20354e4f344a。

## 实际部署

- 项目位于 /opt/hh520；独立 Docker Compose 项目名 hh520。
- hh520-gateway-1 提供 API；hh520-worker-1 执行持久任务的启动检查和 Firecrawl 采集。
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

ChatGPT 账户中的 Actions 配置尚未创建；内置浏览器未能访问已登录会话；Chrome 官方诊断显示扩展与原生连接组件未安装。当前服务提供任务查询，不能主动回写 ChatGPT 原会话。真实采集接口已接通；GPT 分析执行器、历史输入审计和原模型资料差异仍待完成。没有将连接检查或服务器上线计为预测完成。

域名延续现有服务器所用 sslip.io 公共 DNS 方式，未购买新域名或托管服务。0.3.0 验收使用自建 Firecrawl，未调用 OpenAI。

0.3.0 整日采集验收任务：596a658fff42451faff3a96b4dcd5bf0，命令为 `采集 2026-09-04 所有比赛`。调用入口与凭据仅保存在服务器私有配置，不输出到报告。

实测 COMPLETED：78 页成功、0 页失败，14/14 场资料完整且身份通过；无截断、无未归属页面。快照 20260904T154140Z；98 个归档文件逐一 Hash 校验通过，公网认证报告读取通过。详细非敏感回执见 [COLLECTION_ACCEPTANCE.json](COLLECTION_ACCEPTANCE.json)。这次未执行预测，没有将当前抓取的赛后资料当作历史赛前输入。
