# 评价定义（工程契约）

保留原规范：Exact Score Hit/Miss、HT/FT Hit/Miss、Market Win/Loss。工程汇总必须说明有效样本数与排除原因，不用未结束比赛充作未命中。

比分：按全场常规时间定义匹配 Top1，另列 Top3 覆盖率，不混合口径。半全场：以主队视角的胜/平/负组合比较半场与全场。赛事若使用不同结算口径，应显式记录并分组。

其他市场：需保留当时盘口、赔率、市场类型和实际结算；亚洲盘允许 win/half_win/push/half_loss/loss/void，未知结算不能强行填 Win/Loss。ROI 只有记录真实投注单位和可用赔率才计算；本项目当前不执行投注。

取消、延期、腰斩、赛果未确认以 pending/void/excluded 表示，单列计数。真实赛前预测与 reconstructed_historical 分组，不汇成一个成功率。评价报告只提供分析，不自动改 HH520 参数。

S07 保留指标：每市场独立评分；比分与 HT/FT 均记 Top1/Top3；在有完整归一化概率分布时报告 Brier Score、Log Loss、Calibration Error、置信分桶准确率。多类 Brier 使用各类别平方误差和的样本均值并标注口径；Log Loss 是实际类别负对数概率的均值，零概率事件为无穷，不静默裁剪。Calibration Error 分桶边界需在比较前固定并记录；缺概率不补造。Error DNA 分类按原文保存，评价不自动改变模型。
