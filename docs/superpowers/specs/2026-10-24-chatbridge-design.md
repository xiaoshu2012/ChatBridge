# ChatBridge 架构设计

[返回主规划](../plans/2026-10-24-chatbridge-implementation-plan.md) · [仓库首页](../../../README.md)

日期：2026-10-24。状态：设计已确认，产品能力尚待实现和真实验收。

## 目标、使用者与交付形态

个人在自己的电脑运行 Python 常驻服务，通过官方 QQBot 的私聊或群聊调用 Codex 和 DeepSeek Harness（DSH），在原聊天会话接收任务结果。先完成 Windows 原生版，再验证 macOS，之后接入飞书。

交付 Python 包、CLI、配置样例、启动脚本、配套 Skill 和测试。首版不制作桌面 GUI 或独立 exe，不部署云端 Agent，不强行控制已经运行的桌面任务。

## 方案选择

| 选择 | 采用方案与原因 | 其他方案及取舍 |
| --- | --- | --- |
| QQ 接入 | 官方 QQBot，优先 WebSocket，适合本机常驻 | OneBot/NapCat 依赖非官方网关；Webhook 需要公网回调入口，首版不实现 |
| Agent 接入 | Codex App Server + DSH Python SDK，支持状态与原生问答 | CLI headless 更简单，但执行中交互和生命周期控制较弱 |
| 调度与存储 | asyncio + SQLite，全局单任务执行 | 首版不需要 Redis、分布式 worker 或多人服务 |
| 跨平台 | 一套 Python 核心，平台层处理路径和进程树 | 不分别重写两个完整应用 |

QQ 以当前官网及实际应用能力为准，旧 GitHub 文档曾包含过时的 WebSocket/主动消息说明。M1 必须保存验证时的来源、版本与日期。

## 模块边界

`聊天事件 → 身份/群白名单 → 命令和会话路由 → SQLite 队列 → Agent → 结果存储 → outbox → 原会话`

业务模块位于 `src/chatbridge/`：`core/` 管理路由和调度，`storage/` 管理持久化，`platforms/` 管理聊天协议，`agents/` 管理原生执行器，`os/` 管理本机进程和路径，`cli.py` 提供运维入口。

聊天适配器不解释项目任务，Agent 适配器不直接发送 QQ 消息；原始协议标识留在适配器和存储中，不作为用户可执行命令。

## 公共接口与数据类型

Pydantic v2 模型作为业务契约，所有时间保存为 UTC，用户显示时使用配置时区，默认 `Asia/Shanghai`。

| 类型 | 必要字段与约定 |
| --- | --- |
| `InboundMessage` | platform、bot_id、conversation_id、sender_id、message_id、text、received_at、is_group、mentioned、reply_context |
| `OutboundMessage` | delivery_id、target（平台/机器人/会话）、text、artifacts、reply_context；delivery_id 在重试时保持不变 |
| `DeliveryReceipt` | delivery_id、status（sent/blocked/uncertain/retryable）、native_message_id、error_code |
| `SessionSpec` | scope、project_alias、workspace、agent、source_alias、native_id（可空）；路径来自本机配置 |
| `SessionHandle` | bridge_session_id、native_id、agent、workspace、runtime_id |
| `TaskRequest` | task_id、session_id、prompt、source_message_id；提交时固定路由，不随之后的切换而改变 |
| `AgentEvent` | task_id、kind（progress/text/question/artifact/terminal）、payload；不发布 reasoning/thought |
| `QuestionRef` | task_id、runtime_id、native_request_id、question_id；只在当前存活运行时有效 |
| `UserAnswer` | 原问题 ID 对应的选项或自定义文字；多问题必须逐一回答，不生成默认同意 |
| `TaskResult` | task_id、status、text、artifacts、error_code；部分结果也可持久化 |
| `TaskRef` | task_id、session_id、runtime_id；避免迟到取消误伤后续进程 |

```python
class ChatAdapter(Protocol):
    async def start(self) -> None: ...
    def events(self) -> AsyncIterator[InboundMessage]: ...
    async def send(self, message: OutboundMessage) -> DeliveryReceipt: ...
    async def close(self) -> None: ...

class AgentAdapter(Protocol):
    async def open(self, spec: SessionSpec) -> SessionHandle: ...
    def run(self, session: SessionHandle, task: TaskRequest
            ) -> AsyncIterator[AgentEvent]: ...
    async def answer(self, question: QuestionRef, answer: UserAnswer) -> None: ...
    async def cancel(self, task: TaskRef) -> None: ...
    async def close(self, session: SessionHandle) -> None: ...
```

这些是待实现的业务签名，不代表官方 SDK 使用相同签名。适配器声明 capabilities，不能假设两个 SDK 具备完全一致的取消和问答行为。

## 会话、命令与任务

- scope = 平台 + 机器人 + 聊天会话 + 发送者；scope 下按项目和 Agent 分别保存当前会话。
- QQ 只允许本机配置中的本人平台身份；群聊同时要求群白名单和 @机器人。私聊 openid 与群内身份可能不同，不能直接假定相同。
- 普通文本直接提交任务。`/project`、`/agent codex|dsh`、`/new`、`/sessions`、`/resume`、`/status`、`/cancel`、`/result`、`/answer` 为桥接命令，不发送给模型执行。
- 全局一次执行一个任务；等待用户回答仍占执行位。普通追加任务 FIFO 排队，命令和问题回复不排队。
- 切换 Agent 保留各自上下文，不跨 Agent 自动搬运历史。对执行中的会话拒绝 `/new` 和 `/resume`，提示先取消或等待。
- 历史会话经本机 `chatbridge session register` 注册来源、原生 ID、项目和别名；QQ 只展示已登记和桥接创建的会话。
- 恢复原生空闲持久会话，拒绝占用、缺失、不兼容、目录不符或不能约束权限的会话。不改原生日志、不删锁、不创建替代会话。

任务状态：`queued → running ↔ waiting_input → succeeded / failed / cancelled / interrupted`。重启将未结束任务标记 interrupted，撤销旧问题引用，暂停同会话后续任务；用户发送明确的继续任务后才恢复，不自动重放旧任务。

## Agent、权限与本机进程

- Codex：stdio App Server，初始化后使用 thread/start/resume、turn/start/interrupt；最终状态以原生完成事件为准，不以进程 stdout 暂时为空判断完成。
- DSH：官方 Python SDK + 标准 sdk profile，阻塞调用在工作线程中运行，回调线程通过线程安全队列送入 asyncio；不使用默认完全权限的 sdk-minimal。
- 新建/恢复均落实 workspace-write，拒绝额外权限。允许读取系统和依赖、正常联网，写入限制在项目与必要临时目录；这不是对所有本机数据的读隔离。
- DSH 历史权限优先于启动默认值。附带小型权限守卫扩展，在首个模型请求前应用并核验工作区/审批策略；失败中止，不靠提示词约束。确切扩展点和证据由 M1 验证后锁定。
- 每个桥接会话使用自有运行时。Codex 优先原生中断，DSH SDK 无任务取消接口时关闭该运行时；关闭前排空结果，释放后下次 resume。取消不回滚已经发生的修改。
- Windows 用 Job Objects 托管子进程树，macOS 用进程组；优雅退出最多等待 10 秒，再终止、等待退出。无法建立托管时拒绝执行。
- QQ 密钥不进入 Agent 子进程环境；沿用本机 Codex 登录，DSH 凭据按来源配置，数据库和密钥不放项目工作区。

## 结果、投递与持久化

SQLite 保存 inbox、scope 选择、会话、任务、问题元数据、结果和 outbox。运行时句柄不持久化为可恢复对象。任务成功和消息发送成功分开记录，outbox 重试不调用 Agent。

发送确认、必要阶段提示和最终回复，预留终态额度。默认 QQ 单聊回复窗口 60 分钟/4 次、群聊 5 分钟/5 次，M1 对照当时官网和实际权限校验后通过配置固定。过期时仅尝试获准的主动发送，拒绝则保留结果；`/result` 使用新的入站消息上下文领取。对发送结果不确定的非幂等请求不盲重试。

产物仅来自明确清单；发送前解析真实路径，拒绝 `..`、符号链接逃逸和项目外文件。按平台官方能力上传，不开放本机 HTTP 文件服务。不能发送时说明限制并保留本机文件。日志不含密钥或模型思维。

## 验收、兼容与发布

先协议 fixture，再假适配器集成，最后真实 Windows/QQ/Agent 验收；macOS 单独真实验收。首轮目标 Windows 11 x64；macOS 14+ Apple Silicon。Python 3.12。

产品发布前必须证明：私聊和群聊任务闭环、历史恢复和权限约束、取消清理、重启不重复执行、回传失败可领取。未具备环境或凭据的检查标 blocked，不能以 Linux 测试替代。

## 官方参考

- [QQ 事件与连接](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html)
- [QQ 消息规则](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/overview.html)
- [腾讯 QQBot SDK 参考实现](https://github.com/tencent-connect/qqbot-nodejs)
- [Codex App Server](https://developers.openai.com/codex/app-server/)
- [DSH Python SDK](https://github.com/deepseek-ai/deepseek-harness/blob/master/python/sdk/README.md)
- [DSH 协议与取消限制](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/sdk/protocol/README.md)
- [DSH 权限策略](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/sandbox/sandbox-policy/README.md)
