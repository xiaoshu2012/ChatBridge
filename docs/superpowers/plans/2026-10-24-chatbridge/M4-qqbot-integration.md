# M4：QQBot 私聊、群聊与结果回传

[返回主规划](../2026-10-24-chatbridge-implementation-plan.md) · [架构设计](../../specs/2026-10-24-chatbridge-design.md) · [上一阶段 M3](M3-agent-adapters.md) · [下一阶段 M5](M5-windows-release.md)

状态：未开始。依赖：M3；QQ 权限和连接方式以 M1 实测为准。预计：2—3 个工作日。

## 目标与位置

实现 Python 官方 QQBot 适配器，完整连接 Router/调度与 outbox。创建 `src/chatbridge/platforms/qq/{adapter,gateway,api,auth,delivery,media}.py`、`core/delivery.py` 和 `tests/platforms/qq/`。首版不用非官方账号网关，不增加 Webhook 服务。

## 输入与输出接口

`QQAdapter` 实现 ChatAdapter；`gateway` 只发标准 InboundMessage；`api` 处理 token 和原生 HTTP；`delivery` 持久化被动回复序号及策略。Pydantic 接收平台原始载荷，忽略未知字段但拒绝缺少路由身份的事件。

发送消费者从 outbox 获取已固定的 `delivery_id`，调用 `ChatAdapter.send` 并保存 DeliveryReceipt；发送代码不能访问 `Scheduler.submit`。

## 开发步骤

### M4.1：鉴权、连接与去重

- [ ] 用 M1 样例先写 token 过期、心跳 ACK 丢失、RESUME 成功/失败、重复推送的测试。
- [ ] 实现 AppID/AppSecret 换 token、提前刷新与并发刷新锁；重试不打印 token。
- [ ] WebSocket 读取循环与业务任务分离，处理 HELLO、Identify、心跳、session/seq 和 RESUME；不可恢复状态明确停止并诊断。
- [ ] 对 transient 错误采用有上限的指数退避和抖动；身份/封禁/应用配置错误不无限忙重试。
- [ ] 入站落库和去重成功后才派发业务，不能因为重连创建重复任务。

### M4.2：身份与命令路由

- [ ] 写 `test_c2c_and_group_identity_not_assumed_equal`、`test_unmentioned_group_message_does_not_run`、`test_foreign_task_id_not_visible`。
- [ ] 将 C2C 和群事件转换为隔离 scope；本人身份和群均按配置校验，未授权消息不调用 Agent。
- [ ] 去除平台 @标记后路由文本；命令参数用业务解析器处理，不执行成 shell。
- [ ] 实现所有计划命令和必要帮助文本；未知命令给出帮助，不作为普通任务执行。
- [ ] `/answer` 保留原问题 ID/选项对应关系；审批类请求仍拒绝，不混入普通问答通道。

### M4.3：可靠投递

- [ ] 写 `test_passive_reply_budget_reserves_terminal`、`test_expired_reply_becomes_active_or_blocked`、`test_uncertain_send_never_reexecutes_agent`。
- [ ] 保存原消息 ID、接收时间、msg_seq 和投递键；同一被动回复重试复用相同序号，已接受后才使用下一序号。
- [ ] 发送接收确认、必要阶段提示和终态，限制频率并预留最终回复额度；不要逐 token 发 QQ 消息。
- [ ] 对文本按平台长度和可用额度分段；超出额度时发送摘要，将完整内容保存到 `/result`。
- [ ] 过期后只尝试获准主动消息；权限拒绝/额度耗尽记 blocked，超时无法确定是否成功记 uncertain，停止盲目重试。
- [ ] `/result` 验证任务属于当前 scope，使用新消息上下文领取，不启动 Agent。

### M4.4：文件产物

- [ ] 实现明确产物清单的解析和校验；没有显式登记时不扫描整个项目上传。
- [ ] 写路径越界、符号链接逃逸、上传前文件替换及源文件消失测试。
- [ ] 上传前再次验证并读取受限文件快照，避免验证后换成项目外文件；限制文件大小与类型为应用实际支持范围。
- [ ] 走官方媒体/文件接口获取有效 file_info，再发送；上传失败不得标成结果送达。
- [ ] 平台不支持或拒绝时发文字说明、本机保留产物，不暴露本机文件服务器。

## 检查与验收

```bash
python -m pytest tests/platforms/qq tests/integration/test_qq_bridge.py -q
python -m pytest tests/live/test_qq_windows.py -m live -v
```

在本人私聊和测试群，分别用 Codex/DSH 执行任务、回答问题、收结果、连续追问和取消。测试断线及关闭主动消息后，最终结果仍能通过 `/result` 取得。真实测试须有应用权限，不以模拟 HTTP 代替。

## 失败处理与交接

网络层失败只影响连接或 outbox；已提交任务不重跑。投递错误记录脱敏代码和可恢复动作。发送接口超时配置遵循 M1 验证值，不能把所有超时当明确失败。

分别提交连接鉴权、授权路由、结果投递、媒体支持。M5 使用真实适配器进行 Windows 产品验收。

## 执行记录

尚未实施；QQ 限额与 API 域名由 M1 验证后写入正式配置，不从过时样例硬编码。
