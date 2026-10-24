# M7：飞书应用机器人适配

[返回主规划](../2026-10-24-chatbridge-implementation-plan.md) · [架构设计](../../specs/2026-10-24-chatbridge-design.md) · [上一阶段 M6](M6-macos-support.md)

状态：未开始。依赖：M6；QQ 及公共 ChatAdapter 已稳定。预计：2—3 个工作日，包含应用准备后的开发与验证。

## 目标与前置条件

通过飞书官方应用机器人接收私聊和群 @，复用现有 Codex/DSH、会话、权限守卫、队列、问答和 outbox。使用官方 Python SDK 长连接事件能力，不把只能发送的自定义群 Webhook 当成双向机器人。

需要用户创建应用、启用机器人和事件长连接，授予接收消息、发送/回复消息及所需文件权限，配置可见范围与测试用户。M7 开始时核实当时官方权限和 SDK 版本，记录到兼容矩阵。

创建 `src/chatbridge/platforms/feishu/{adapter,client,events,delivery,media}.py`、`tests/platforms/feishu/`、`docs/user/feishu.md`、`docs/validation/feishu-acceptance.md`。依赖 `lark-oapi` 在本阶段验证后锁定为可选平台依赖。

## 接口与数据映射

- `FeishuAdapter` 实现 ChatAdapter，事件回调线程通过线程安全队列接入 asyncio，不在回调中等待 Agent。
- `im.message.receive_v1` 映射为 InboundMessage，使用 app_id、chat_id、sender.open_id、message_id 和 mentions，保留原消息回复上下文。
- 机器人 AppID 是 bot_id；scope 的 platform 固定为 `feishu`，不与 QQ 身份或会话混用。
- 使用官方发送/回复消息及上传接口，保存返回 message_id；token 刷新/缓存按 SDK 支持方式执行，不绕开权限检查。
- ChatAdapter 输出仍是 DeliveryReceipt；不修改 AgentAdapter，不复制一套 Scheduler。

## 开发步骤

### M7.1：应用与事件接入

- [ ] 创建最小验证探针，核对应用权限、SDK 版本、长连接启动和接收事件样例。
- [ ] 写私聊/群聊/非文本/未知事件 fixture 测试，再实现消息文本和 mentions 解析。
- [ ] 处理机器人自身消息、重投事件、连接恢复和 token 失效；入站复用现有 SQLite 幂等约束。
- [ ] 使用飞书本人 open_id 与群白名单，群聊仅 @时执行；不把 QQ 身份列表直接用于飞书。

### M7.2：命令、问答与投递

- [ ] 将普通文本及全部桥接命令接到现有 Router；使用文本问题与 `/answer`，首版不新增交互卡片协议。
- [ ] 写 `test_feishu_and_qq_scopes_are_separate`、`test_feishu_duplicate_event_runs_once`、`test_group_requires_owner_and_mention`。
- [ ] 实现文字回复、长度分段、请求限流、明确错误/不确定发送结果分类，复用 outbox 重试策略。
- [ ] 文件经公共产物边界校验后上传，保存 file_key 并发送；权限不足或上传失败保留结果并说明。
- [ ] 测试飞书 token、app secret 不进入 Codex/DSH 子进程环境。

### M7.3：多平台装配与验收

- [ ] 服务配置允许启用 QQ、飞书或两者；唯一全局 worker 串行执行全部任务，不各自偷偷建立独立队列。
- [ ] 平台连接失败只影响该平台；不中断另一个平台的运行任务，任务终态仍先持久化。
- [ ] 用两种 Agent 验证飞书私聊和群聊任务、提问、连续对话、恢复及取消。
- [ ] 同时从 QQ/飞书提交任务，验证全局串行、scope 隔离、跨平台 `/result` 不可读取他处任务。
- [ ] 更新 Skill、配置样例、README 与兼容矩阵，提交完整正式计划和验收证据至 GitHub。

## 检查与完成标准

```bash
python -m pytest tests/platforms/feishu tests/integration/test_multi_platform.py -q
python -m pytest -m 'not live' -q
python -m pytest tests/live/test_feishu_acceptance.py -m live -v
```

新适配器遵守与 QQ 相同的 Agent/调度契约；QQ 回归通过；飞书私聊和群聊的 Codex/DSH 任务闭环有真实证据。Windows/macOS 的飞书启动方式都需记录，不仅在一个平台宣称双平台通过。

## 失败处理与交接

应用未发布或可见范围/权限不满足时提示具体配置步骤并标 blocked，不能改用单向 Webhook 假装接收成功。所有投递故障复用 outbox；任务不因平台 token 更新重新执行。

分接入、投递/文件、多平台验收三项提交；交付 GitHub 发布产物与真实文档链接。进一步卡片交互、多用户授权或新增平台分别另开正式计划，不混入本阶段。

## 执行记录

尚未实施，当前没有飞书应用权限或真实测试通过声明。
