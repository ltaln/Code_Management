# 回测 · Prediction Archive First

先加载重要注意事项与完整对应 Prompt。按日期、场次、模型和预测时点查找 Prediction Commit、Prediction Data Package、Prediction Result、Execution Log。查询有三态：FOUND、NOT_FOUND、UNAVAILABLE。

FOUND：校验身份、Hash、赛前时间和原记录完整性，固定引用原预测；随后获取真实结果并评价。禁止重新预测、改写原预测或调参。

NOT_FOUND：仅在所有指定存储及历史索引成功查询且不存在时成立。新采集当时可用的历史数据，使用原模型与 Prompt 完整预测，生成新预测档案后再取赛果；标记 reconstructed_historical，不能冒充真实赛前发布记录。

UNAVAILABLE：访问失败、查询未完成、记录损坏或部分缺失都进入 BLOCKED，保留已有证据，不直接走 NOT_FOUND。批次混合有档案/无档案时按场次分支。

结果数据必须和预测 worker 隔离；预测输入仅可见 as_of 之前可用信息。缺少可靠历史快照时标记不可回测，不抓当前页面伪装历史。

评价输出固定先比分、再半全场、再其他市场。新评价记录链接原 prediction_id 和 commit，不产生第二份伪造的原预测。当前缺独立回测 Prompt 和执行服务，只有设计。

S07 补充：历史重建以 kickoff_at 前 30 分钟为信息截止；原真实赛前档案保留其记录的预测 cutoff 并单独报告，不倒改历史时点。
