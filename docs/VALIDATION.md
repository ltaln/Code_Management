# 实际验证记录 · 2026-09-05

## 0.4.2 ChatGPT Actions

- 私人 GPT **HH520 Football AI** 创建成功，范围为“只有我”。
- OpenAPI 0.4.2 从公网 HTTPS 导入；8/8 操作均可用，无参数、响应或重复字段解析错误。
- Bearer 认证由 ChatGPT 密钥存储保存；仓库和文档不含密钥。
- “检查连接”由 GPT 实际调用服务器：任务持久化、后台检查、报告返回，状态 COMPLETED，模式 connection_check，`is_prediction=false`。
- 网页搜索和图片生成关闭，防止绕过唯一服务器数据包。

## 自动测试

17 项本地测试通过：任务持久化、租约、取消、网络门禁、真实 HTTP、公开 schema/私有任务接口、外部 GPT 交接、有界数据与不可变 Prediction Commit。服务器 0.4.2 镜像测试通过；公网 schema 为 0.4.2、8 个路径。`scripts/verify_assets.py --require-ready` 返回 PASS：102 个工程文件、27 个锁定文件、7 份来源、25 个本地链接，`runtime_ready=true`，无 blocker。

## 真实数据证据

2026-09-04 整日采集：78 页成功、0 失败、14/14 场、98 个归档文件 Hash 全部通过。快照 `20260904T154140Z`，任务 `596a658fff42451faff3a96b4dcd5bf0`。该数据已赛后，仅用于采集和压缩器验收，没有被冒充为赛前预测。

## 尚未覆盖

尚未执行未来日期的首个真实完整预测；没有模型准确率结论。历史 T-30 重建和回测评价运行未完成。
