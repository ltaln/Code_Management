# 任务管理中心设计

目标输入：预测 2026-09-10 全部比赛。解析到日期、日期口径、时区、范围、模式后，以唯一 task_id 持久保存；同一次请求重试使用同一 request_id。新预测请求必须新快照，中断恢复锁定原快照。

目标状态：CREATED → STARTUP_CHECK → COLLECTING → DATA_READY → AUDITING → ANALYZING → CALIBRATING → COMMITTING → COMPLETED → ARCHIVED。所有非终态可到 FAILED、BLOCKED 或 CANCELLED。后台进程未部署，本文件不自动创建任务。

执行设计：单机初期用 SQLite 事务保存任务、每场模块检查点与事件 outbox；worker 持有有期限的 lease 并续租，重启仅接管过期 lease。多 worker 时使用 compare-and-set 的 revision 防重复推进。详细分析内容存档，数据库只保存引用和 Hash。

幂等：提交键绑定 task_id、match_id、snapshot_hash、asset_lock_hash。外部写入超时先查回执，不能重跑已提交预测。仅对网络/限流失败有限重试，退避参考 config/task.json；业务规则或 Hash 错误进入 BLOCKED。

取消：记 cancel_requested，模块边界停止，已完成结果保留；已提交结果不删除。批次有场次失败标记 PARTIAL_FAILED，不能返回全部完成。用户关闭手机不取消任务，完成后由已接通的任务查询/回调返回结果。

接口草案：POST /v1/tasks 创建（202，返回 task_id）；GET /v1/tasks/{id} 读取；POST /v1/tasks/{id}/cancel 请求取消。访问需鉴权，request_id 支持重试，不在日志记凭据。

0.2.0 已实现上述状态机的前段：CREATED → STARTUP_CHECK → BLOCKED/FAILED/CANCELLED；检查连接可到 COMPLETED。SQLite、请求去重、租约恢复和报告读取已有代码，采集/分析/校准/提交阶段未实现。部署见 docs/MOBILE_GATEWAY.md。
