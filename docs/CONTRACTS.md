# 机器可读契约

task_manager/task.schema.json：任务；example.task.json：未执行示例。
data_engine/package.schema.json：采集快照；prediction/record.schema.json：提交前预测内容；prediction/receipt.schema.json：提交回执。

JSON Schema 为 Draft 2020-12 契约，datetime 和 date 需要启用 format 验证。资产校验器检查这些 JSON 的语法与必需文件，不声称已实现全部业务验证。示例可用标准 Draft 2020-12 验证器检查。

业务校验包括：身份、数据 Hash、本任务最新快照、禁止预测复用、模型完整顺序、概率归一化、市场结算和提交条件写入。宽松 output/results 保留原 GPT 输出空间，不能仅凭 schema valid 判定预测有效。

prediction/ports.py 为 Python Protocol 交接骨架，方法没有运行实现。不得调用空方法并把 None 当作预测结果。

0.2.0 命令 API 使用 integrations/gpt-actions.openapi.json；它的请求是 command/request_id，返回实际服务状态，尚不等同完整预测任务 schema 的运行实现。
