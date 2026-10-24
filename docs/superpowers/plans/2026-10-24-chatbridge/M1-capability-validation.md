# M1：Windows 与官方接口能力验证

[返回主规划](../2026-10-24-chatbridge-implementation-plan.md) · [架构设计](../../specs/2026-10-24-chatbridge-design.md) · [上一阶段 M0](M0-docs-and-github.md) · [下一阶段 M2](M2-python-core.md)

状态：未开始。依赖：M0。预计：1—2 个工作日。

## 目标与前置条件

在开发公共业务前证明官方接口能支撑设计，锁定实际可用的发布版本。Windows 11 x64、Python 3.12、PowerShell 7、已登录的 Codex、DSH SDK 凭据和具备私聊/群聊权限的 QQ 应用须就绪。测试只使用临时项目、临时数据和本人测试会话。

输出 `docs/validation/windows-capabilities.md`、`docs/validation/compatibility-matrix.md` 和可复现的 `tools/probes/` 探针。矩阵记录 OS、CPU、Python、Agent/SDK 版本、官方来源、日期、测试命令及脱敏结果。

## 输入与输出接口

输入是架构设计中的行为契约；输出是能否实现该契约的证据，而不是生产适配器。探针按 `--agent codex|dsh --workspace <临时目录>` 选择执行器；QQ 探针只读取本机环境变量/本机配置中的凭据，不接受命令行明文密钥。

M2/M3 消费明确锁定的版本和协议 fixture；SDK 版本不支持的能力标 blocked，不使用另一个项目的同名 `dsh` 程序代替 DeepSeek Harness。

## 开发步骤

### M1.1：建立环境与 fixture 基线

- [ ] 记录工具路径和版本，不输出完整环境变量或配置密钥。
- [ ] 验证 Windows 原生执行；建立中文及带空格路径的临时 Git 项目。
- [ ] 给每个探针设置明确退出码：0 通过，1 失败，2 缺少前置条件；不能把 skip 当成功。
- [ ] 为协议解析先写 fixture 测试，覆盖未知通知、不完整帧、stdout/stderr 分离和错误响应。

### M1.2：验证 QQBot

- [ ] 本人私聊与允许群 @机器人分别收发一次，记录事件类型及身份字段。
- [ ] 对照现行官网验证 WebSocket 鉴权、心跳、重连/RESUME 和 token 更新。
- [ ] 核实私聊/群回复窗口、次数、msg_id/msg_seq 去重、主动消息及文件上传权限。
- [ ] 验证非白名单群、非本人、群中未 @ 消息的过滤依据，脱敏保留样例。

### M1.3：验证 Codex

- [ ] 用 App Server 初始化、新建、执行、接收终态并关闭；按同一原生 ID 恢复上下文。
- [ ] 验证原生用户问题往返与取消；拒绝权限请求后不执行越权操作。
- [ ] 在临时目录验证项目内写入成功、项目外写入失败；确认 Windows 沙箱已就绪。
- [ ] 验证原客户端持有写入锁时不能被桥接恢复，关闭桥接进程后释放所有权。

### M1.4：验证 DSH

- [ ] 使用已发布 Python SDK 和标准 `sdk` profile，新建、执行、恢复、问答和关闭。
- [ ] 验证 profile 的 Windows PowerShell 执行、文件工具和工作区边界。
- [ ] 构造曾为 full-access 的历史会话，验证默认 profile 不足以降级，并找出官方扩展点。
- [ ] 用最小权限守卫探针证明：首个模型请求前重新设置工作区权限，失败则不接收 prompt；记录需使用的原生 API 与扩展打包方式。
- [ ] 验证 runtime 关闭可停止活动、落盘并释放 writer 锁；若 SDK 无 per-task cancel，记录进程关闭策略。

### M1.5：冻结结论

- [ ] 按 agent/新建/恢复/事件/问答/权限/取消逐项填矩阵；每项附命令和证据。
- [ ] 锁定测试通过的发布版本和依赖范围，将样例录制为脱敏 fixture。
- [ ] 检查 fixture 中的 token、openid、项目路径及用户内容已经脱敏。

## 验证命令与验收

以下文件与命令是本阶段要创建的工具，当前文档交付不意味着它们已存在：

```powershell
python -m pytest tests/probes -q
python tools/probes/agents.py --agent codex --workspace "C:\Temp\ChatBridge 验证"
python tools/probes/agents.py --agent dsh --workspace "C:\Temp\ChatBridge 验证"
python tools/probes/qqbot.py
```

验收必须包含真实 Windows 下两个 Agent 的新建、恢复、改文件、问答、拒绝越权和停止，以及 QQ 私聊/群聊回传。只通过 fixture 不足以完成 M1。

## 失败处理与交接

缺少 Windows、登录、应用权限或凭据时记录 blocked 和缺失项。守卫不能阻止历史权限继承属于关键阻塞，不能改用 full-access 完成探针。依赖与当前设计冲突时修订设计和受影响阶段，推送 GitHub 后再推进。

提交建议：`test: add Windows agent and QQ capability probes`，随后 `docs: record verified compatibility baseline`。

## 执行记录

尚未运行。本轮仅确认文档编写环境为 Linux，不构成 Windows 验收。
