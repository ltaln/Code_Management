# 版本管理

stable 指向项目指定稳定模型 HH520 V2.1-Test；名称中 Test 不改变其被指定为稳定基线的事实。development/test/archive 当前为空，不创建虚假历史版本。

asset_release 0.1.0 仅标识本次迁移包。asset_lock.json 覆盖模型、提示词、规则、校准入口、流程和来源。SHA-256 保障文件一致性，不能证明模型正确性；同一人同时改正文和锁仍需 Git 基准差异审阅。
