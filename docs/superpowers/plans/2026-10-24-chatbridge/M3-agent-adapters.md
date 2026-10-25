# M3：双 Agent、权限与历史会话

[返回主规划](../2026-10-24-chatbridge-implementation-plan.md) · [架构设计](../../specs/2026-10-24-chatbridge-design.md) · [上一阶段 M2](M2-python-core.md) · [下一阶段 M4](M4-qqbot-integration.md)

状态：未开始。依赖：M1 原生能力与版本已验证，M2 公共契约通过。预计：3—4 个工作日。

## 目标、位置和接口

创建 `src/chatbridge/agents/{codex,dsh,rpc}.py`、`os/{processes,windows,paths}.py`、`extensions/dsh-chatbridge-guard/` 和 `tests/agents/`、`tests/os/`。完整实现设计中的 `AgentAdapter`，输出仅为统一事件；不直接发 QQ 消息。

`ProcessSupervisor` 提供 `spawn(argv, cwd, env)`、`stop(runtime_id, grace_seconds=10)`、`wait(runtime_id)`；运行时 ID 与任务绑定。Windows 写入保护依赖原生沙箱，Job Objects 只负责进程生命周期，不能代替权限隔离。

## 开发步骤

### M3.1：stdio 和进程管理

- [ ] 写请求响应乱序、未知通知、子进程提前退出和 stderr 不污染协议的测试，再实现 JSON 行收发与 pending-request 表。
- [ ] 传 argv 列表而非拼接 shell 字符串；解析显式工具路径，处理中文和空格。
- [ ] Windows 使用 Job Objects，设置关闭时清理进程树；在子进程获得执行机会前完成托管，失败即终止启动。
- [ ] 清理 QQ 密钥及无关敏感环境变量，保留 Agent 所需登录/网络环境。测试 `test_qq_secret_absent_from_agent_env`。
- [ ] 进程关闭先请求优雅退出，最多 10 秒，再终止并等待；关闭完成才清除任务运行引用。

### M3.2：Codex App Server

- [ ] 使用 M1 fixture 写 `test_initialize_before_thread_requests`、`test_resumed_thread_is_same_native_id`、`test_terminal_status_not_inferred_from_text`。
- [ ] 启动 stdio App Server，initialize/initialized 完成后再调用 thread/start 或 thread/resume。
- [ ] 校验恢复的 cwd 匹配配置项目，执行 turn/start 时显式工作区写入与不升级审批策略。
- [ ] 把公开 assistant 输出、工具阶段、问题和 turn/completed 转为统一事件；丢弃思维事件。
- [ ] 将原生用户问题送入 QuestionBroker；所有额外权限请求返回拒绝，区分普通提问和审批。
- [ ] 用 turn/interrupt 取消并等待原生 interrupted；超时才回收自有进程。测试迟到事件不能改变后续任务。

### M3.3：DSH Python SDK

- [ ] 采用 M1 锁定的官方 `deepseek-harness-sdk`，标准 `sdk` profile；显式传入 home、workspace、model 和 patches。
- [ ] SDK 阻塞调用放独立 worker，通知/提问 callback 经线程安全队列接回 asyncio；run 期间持续处理问题与关闭。
- [ ] 写 `test_dsh_resume_uses_resume_session_not_lazy_start`；历史 ID 调用原生恢复 API，不使用创建 lazy handle 代替恢复。
- [ ] 以原生运行区间和终态识别完成，不能把 durable enqueue receipt、单个 idle 通知或子 Agent 输出当最终成功。
- [ ] 测试 `test_child_output_cannot_replace_root_result` 和 `test_question_callback_cancelled_on_shutdown`。

### M3.4：DSH 权限守卫

- [ ] 按 M1 验证的扩展点实现小型扩展；Python 业务逻辑仍位于桥接核心，扩展只负责原生会话权限。
- [ ] 新建/恢复后，首个模型请求前重设工作区写入和拒绝升级策略；校验会话 cwd 与配置根一致。
- [ ] 故意恢复 full-access 历史，先写能证明越权风险的失败用例，再实现守卫并证明项目外写入被拒绝。
- [ ] 守卫加载失败、策略未知或目录不匹配时拒绝 prompt；不回退 sdk-minimal，不用文字提示代替原生执行约束。
- [ ] 固定扩展 API/运行时版本并打包，不能要求用户修改 DSH 原始源码。测试升级版本不匹配时清晰报错。

### M3.5：历史会话与生命周期

- [ ] 实现 `chatbridge session register --agent codex|dsh --native-id <id> --source <alias> --project <alias> --alias <name>`。
- [ ] 注册信息只引用本机配置的来源；QQ 不接受任意 home 路径。恢复校验通过后才绑定 scope。
- [ ] 测试占用、缺失、不兼容、目录不符时明确失败；不删锁、不修改日志、不创建替代会话。
- [ ] DSH SDK 无任务级取消时关闭当前会话独立 runtime；取消完成前不启动下一任务。
- [ ] 任务结束且没有有效排队/问答时关闭运行时并释放 writer，下次恢复原 ID；测试原客户端之后可正常恢复。

## 检查与验收

```bash
python -m pytest tests/agents tests/os tests/integration/test_agent_contract.py -q
python -m pytest tests/live/test_agents_windows.py -m live -v
```

live 测试需要 Windows、两个 Agent 登录和 M1 锁定版本；缺少条件不能当通过。用两种真实 Agent 完成“项目内修改→提问→继续→取消→重启恢复”契约；证明 full-access 历史被约束，关闭后无托管子孙进程残留。

## 失败处理与交接

无终态的断连标 interrupted，不自动重发 prompt；SDK/守卫不支持的会话拒绝恢复。运行时问题只对当前 runtime 有效，断开后立即撤销，不能自动回答或把文本当授权。

分别提交进程托管、Codex、DSH/守卫、历史恢复四项产物。M4 只通过 AgentAdapter 使用能力，不依赖私有 SDK 对象。

## 执行记录

尚未实施。DSH 权限扩展点须由 M1 在实际发布版本上验证，本文件不声称当前已有可用扩展。
