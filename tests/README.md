# 资产保护测试

从仓库根目录运行 `python tests/check_delivery.py`。核心校验不需第三方包；完整契约测试另需 tests/requirements.txt 中的 jsonschema。

测试复制项目文件到 runtime/test_runs 下的独立目录，修改副本验证保护行为，保留副本便于检查，不改原模型。runtime 已忽略，不提交测试副本。
