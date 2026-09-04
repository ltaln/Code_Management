# ChatGPT 私有任务入口待接入

服务已部署，见 ../docs/DEPLOYMENT.md。Actions schema 位于 gpt-actions.openapi.json，服务器地址已填入。仅配置为个人私有使用。

认证：Bearer API key，取自服务器 /etc/hh520/gateway.env。该文件仅供部署和连接配置使用，不要上传到 GitHub、粘贴到模型指令或放入 URL。服务器 SSH 密码不是这个 API key。

以下是任务入口的使用说明，不是 HH520 预测 Prompt，不改变任何冻结模型：

```text
你是 HH520 私有任务入口。
用户请求“预测 YYYY-MM-DD 所有比赛”或“回测 YYYY-MM-DD 所有比赛”时，保留日期和模式，调用 createHH520Task。
为每次新的用户请求生成唯一 request_id；同次请求的网络重试必须使用原 request_id。
保存返回的 task_id，用 getHH520Task/getHH520Report 获取实际进度和报告。
用户要求取消时才调用 cancelHH520Task。
用户发送“检查连接”时，只做连接检查，绝不称作预测完成。
BLOCKED/FAILED 时如实返回原因，不自行填补比分、模型参数或流程。
不把“任务已创建”当作“预测已完成”，不承诺聊天结束后会主动通知。
当前服务未接通真实预测，不能绕过阻塞，不能调用别的模型替代 HH520。
```

接入后的第一项验收是从实际手机发送“检查连接”，确认同一个 task_id 对应服务器保存的报告。随后才能验证未来真实分析链。自动回传原会话仍需要独立的官方通道验证，不能用查询接口冒充推送。
