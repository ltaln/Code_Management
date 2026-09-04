# 数据接口设计

服务器提供事实，不运行 HH520 推理。旧数据仓库 ltaln/firecrawl-gpt-predictor 仅作为已知来源，本次不改其现有流程，也不假设 README 的旧架构等同本项目目标。

POST /v1/collections 接收 task_id、date、date_basis、timezone、scope、mode、as_of。202 返回 collection_id。GET /v1/collections/{id} 返回 COLLECTING/COMPLETE/FAILED 与不可变 snapshot_id。GET /v1/snapshots/{id} 返回数据包及 SHA-256。以上是待实现契约，当前没有服务地址。

快照清单记录每个 section 的来源 URL、source_match_id、observed_at、collected_at、内容 Hash。身份以赛事、场次、主客队和日期共同验证；赛程日期与真实 kickoff_at 分开，防止跨午夜错配。不得用 HTTP 成功或 complete 字段替代内容一致性审计。

市场数据应保留 line、主客方向、赔率制式与时间；10017、10013、10016、10015、mixed 等来源 section 只作为原材料中的已知标识，不能据此认定内容真实或齐全。SoccerSTATS HT/FT 单独记录。

实时预测：每次新请求创建新快照；恢复当前任务不能换用移动的 latest 指针。回测重建：observed_at 不晚于 as_of，后续抓取仅允许可验证的赛前历史归档；赛后页面不能充当历史输入。

字节 Hash 校验与比赛事实审计分开。错配字段保留证据并排除于可用输入；缺失/冲突按冻结规则降级，不删除模块或编造数值。缺失包、日期范围错误、快照混杂退回采集修复。

S07 补充：Firecrawl 是正式预测与缺档重建的首阶段硬门槛，普通搜索只在主采集成功后补缺。历史 as_of 固定 kickoff_at 减 30 分钟。xi_id 必须来自真实链接；10012/10013、bfplsj/10017、10015/10016 按模块去重，xi 直接模型权重为 0。
