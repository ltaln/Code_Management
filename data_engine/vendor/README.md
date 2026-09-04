# 既有采集程序

三个 Python 文件逐字节复制自 `ltaln/firecrawl-gpt-predictor` 的
`cb20b37e96b047007e21d6de436107d34287972e`，校验值见 [source.json](source.json)。
它们负责采集及比赛身份关联，不包含预测模型逻辑。

运行器必须通过已有自建 Firecrawl HTTPS 入口采集，不自动切换收费云端。
原始页面保留在私有任务目录。`identity-v1` 是采集包格式，尚不是经过历史时间截断审计的预测输入契约。
