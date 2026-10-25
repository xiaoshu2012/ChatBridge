# M2：Python 核心、SQLite 与调度

[返回主规划](../2026-10-24-chatbridge-implementation-plan.md) · [架构设计](../../specs/2026-10-24-chatbridge-design.md) · [上一阶段 M1](M1-capability-validation.md) · [下一阶段 M3](M3-agent-adapters.md)

状态：未开始。依赖：M1 通过并产出版本基线。预计：2—3 个工作日。

## 目标与开发位置

不连接真实 QQ 和模型，先用假适配器证明从收消息、排队到保存/投递结果的业务闭环。

创建 `pyproject.toml`、`src/chatbridge/core/{models,protocols,config,router,scheduler,questions}.py`、`storage/{database,repository}.py`、`cli.py`、`service.py` 和 `tests/core/`、`tests/storage/`、`tests/integration/`。依赖限定 Python 3.12，采用 Pydantic v2、aiosqlite、Typer，测试用 pytest/pytest-asyncio。

## 接口与持久数据

- 复用设计中的 `ChatAdapter`、`AgentAdapter` 和公共模型，不另造一套相近但不兼容的事件类型。
- `Router.handle(message: InboundMessage) -> None` 负责授权、命令或提交；`Scheduler.submit(task: TaskRequest) -> str` 返回已落库任务 ID。
- `QuestionBroker.answer(scope, question_id, answer)` 验证问题属于当前任务/运行时后回答；未知或迟到引用拒绝。
- `Repository` 提供 inbox 去重、session 查找、task 入队/claim/finish、question 失效、outbox 入队/投递记录；事务与 SQL 只在 storage 内实现。
- SQLite 采用 schema version；inbox 唯一键为平台/机器人/消息 ID，任务 claim 为事务；scope 选择与提交时的任务路由分开保存。
- 表包含 inbox、scope_selections、sessions、tasks、questions、outbox；结果存在 tasks，outbox 保存序号/重试状态和目标。外键开启，状态变更受业务约束。

## 开发步骤

### M2.1：包、配置和模型

- [ ] 写 `test_unknown_project_rejected`、`test_secret_not_serialized`、`test_task_route_is_immutable`，先观察失败。
- [ ] 实现本机配置：项目别名→绝对目录、Agent/source 别名、本人身份/群白名单、默认项目/Agent、时区与数据目录。
- [ ] 创建 `chatbridge init` 和 `chatbridge run --config <path>` 入口；缺少配置或项目无效时明确退出，不静默选全盘路径。
- [ ] 定义公共类型、协议和状态枚举；日志默认不包含任务正文、凭据与原始协议全文。

### M2.2：存储与故障恢复

- [ ] 写 `test_duplicate_message_has_one_task`、`test_atomic_claim`、`test_outbox_failure_does_not_rerun_task`。
- [ ] 用数据库唯一约束/事务实现幂等入站和单 worker claim；完成结果与 outbox 入队在一个事务提交。
- [ ] 写 `test_restart_interrupts_running_and_invalidates_questions`；启动时中断未结束任务，暂停该会话队列。
- [ ] 明确继续时创建新的用户任务，不重放旧 prompt；失败的数据库写入不得被确认成已接收。

### M2.3：命令、会话和调度

- [ ] 写 `test_scope_isolated_across_groups_and_agents`、`test_waiting_input_holds_execution_slot`、`test_control_command_bypasses_queue`。
- [ ] 实现 `/project`、`/agent`、`/new`、`/sessions`、`/resume`、`/status`、`/cancel`、`/result`、`/answer`；普通文本入 FIFO。
- [ ] 控制命令检查 scope 所有权；切换只影响之后提交的任务；执行中会话拒绝 new/resume。
- [ ] 全局 worker 串行执行；收到 question 时保留执行位；取消有确定终态后才调度下一任务。

### M2.4：假适配器闭环

- [ ] 实现可确定地产生 progress、question、terminal 和异常的假 Agent，以及可模拟失败的假聊天适配器。
- [ ] 测试从普通文本到结果、下一轮连续对话、用户回答、取消和服务重启的完整链路。
- [ ] 对未知 question-id、跨群任务 ID 和重复回答断言无原生副作用。
- [ ] 完成对应代码、运行测试并逐任务提交，更新主规划及执行记录。

## 检查与验收

```bash
python -m pip install -e '.[dev]'
python -m pytest tests/core tests/storage tests/integration/test_fake_bridge.py -q
python -m ruff check src tests
```

预期所有用例通过；重复投递只产生一次执行；不同 scope 不共享上下文；运行中追加普通消息排队；命令仍即时响应；重启不重复修改项目。

## 失败处理与交接

任务异常先持久化终态再尝试回复；投递异常留给 outbox，不重新入执行队列。内存对象不得作为重启后的事实来源。数据库 schema 未来变更走显式版本迁移，不删除用户数据库。

M3 消费已经稳定的协议、模型、调度和 QuestionBroker；M4 消费 Router 与 outbox。提交按配置/模型、存储恢复、路由调度三项功能分开。

## 执行记录

尚未实施；以上测试名、模块与命令均为待创建产物。
