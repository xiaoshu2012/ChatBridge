# M1：Windows 与官方接口能力验证

[返回主规划](../2026-10-24-chatbridge-implementation-plan.md) · [架构设计](../../specs/2026-10-24-chatbridge-design.md) · [上一阶段 M0](M0-docs-and-github.md) · [下一阶段 M2](M2-python-core.md)

状态：阻塞（探针及 Linux 原生生命周期验证已交付；真实 Windows/模型/QQ、DSH 问答和完整模型入站权限验收未通过）。依赖：M0，已收尾。预计：前置条件就绪后 1—2 个工作日。

当前产物：[探针使用](../../../../tools/probes/README.md) · [Windows 验收记录](../../../validation/windows-capabilities.md) · [兼容矩阵](../../../validation/compatibility-matrix.md) · [DSH 原生验证](../../../validation/dsh-native-lifecycle.md)。最后更新：2026-11-07。最新原生审计标签 `v0.0.0-m1.4` 不表示 M1 已验收，旧标签保留。

## 目标与前置条件

在开发公共业务前证明官方接口能支撑设计，锁定实际可用的发布版本。Windows 11 x64、Python 3.12、PowerShell 7、已登录的 Codex、DSH SDK 凭据和具备私聊/群聊权限的 QQ 应用须就绪。测试只使用临时项目、临时数据和本人测试会话。

输出 `docs/validation/windows-capabilities.md`、`docs/validation/compatibility-matrix.md` 和可复现的 `tools/probes/` 探针。矩阵记录 OS、CPU、Python、Agent/SDK 版本、官方来源、日期、测试命令及脱敏结果。

## 输入与输出接口

输入是架构设计中的行为契约；输出是能否实现该契约的证据，而不是生产适配器。探针按 `--agent codex|dsh --workspace <临时目录>` 选择执行器；QQ 探针只读取本机环境变量/本机配置中的凭据，不接受命令行明文密钥。

M2/M3 消费明确锁定的版本和协议 fixture；SDK 版本不支持的能力标 blocked，不使用另一个项目的同名 `dsh` 程序代替 DeepSeek Harness。

## 开发步骤

### M1.1：建立环境与 fixture 基线

- [x] 记录当前执行器的工具路径和版本，不输出完整环境变量或配置密钥；Windows 工具版本仍待本机运行报告。
- [ ] 验证 Windows 原生执行；建立中文及带空格路径的临时 Git 项目。
- [x] 给每个探针设置明确退出码：0 当前 scope 通过，1 失败，2 缺少前置条件/仍须真实验收；不能把 skip 当成功。
- [x] 为协议解析先写人工 fixture 测试，覆盖未知通知、不完整帧、stdout/stderr 分离和错误响应；不冒充真实 SDK/平台录制。

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
- [x] 补充 Linux 无模型原生生命周期探针：官方本地 bundle、`agent/created`、原生策略函数、历史空会话 full-access 降级及主动拒绝恢复均实测；不勾选上方完整模型/Windows 验收。
- [ ] 验证 runtime 关闭可停止活动、落盘并释放 writer 锁；若 SDK 无 per-task cancel，记录进程关闭策略。

### M1.5：冻结结论

- [x] 按 agent/新建/恢复/事件/问答/权限/取消逐项填矩阵；每项附命令和证据，未满足项明确标 blocked。
- [ ] 锁定测试通过的发布版本和依赖范围，将样例录制为脱敏 fixture。
- [x] 检查人工 fixture 和已保存的报告不包含真实 token、openid、用户项目路径、消息正文或思维；真实平台录制尚未产生。

## 验证命令与验收

以下工具已创建。默认 Agent/QQ 命令只做前置检查，未满足真实验收会返回 2；协议探针需加 `--protocol-only`，真实 QQ smoke 需显式 `--live`，均不代表 M1 全部完成：

```powershell
python -m pytest tests/probes -q
python tools/probes/agents.py --agent codex --workspace "C:\Temp\ChatBridge 验证"
python tools/probes/agents.py --agent dsh --workspace "C:\Temp\ChatBridge 验证"
python tools/probes/qqbot.py
pwsh -NoProfile -File tools/probes/run-windows.ps1 -PythonPath .\.venv\Scripts\python.exe
```

验收必须包含真实 Windows 下两个 Agent 的新建、恢复、改文件、问答、拒绝越权和停止，以及 QQ 私聊/群聊回传。只通过 fixture 不足以完成 M1。

## 失败处理与交接

缺少 Windows、登录、应用权限或凭据时记录 blocked 和缺失项。守卫不能阻止历史权限继承属于关键阻塞，不能改用 full-access 完成探针。依赖与当前设计冲突时修订设计和受影响阶段，推送 GitHub 后再推进。

提交建议：`test: add Windows agent and QQ capability probes`，随后 `docs: record verified compatibility baseline`。

## 执行记录

| 日期 | 动作 | 结果与后续 |
| --- | --- | --- |
| 2026-10-24 | M0 收尾后启动 M1；用户确认使用正在操作的 Windows 电脑 | 当前聊天只有云端 Linux shell，未附加本机终端；不等于用户缺少 Windows |
| 2026-11-05 | 环境重建后从 Git 恢复 M0、恢复探针并及时推送 | `792a758`，30 项测试通过；后续 Windows 入口和 worker 回收提交 `2c5af1d`，36 项通过 |
| 2026-11-05 | 新增 Windows 原生 Codex 定位、版本矩阵、依赖锁定快照与本机操作说明 | [探针使用](../../../../tools/probes/README.md)；README 保持项目介绍与实际交付状态，不列规划 |
| 2026-11-05 | Linux 真 SDK/服务无模型检查 | Codex 初始化/新建空 thread/拒绝不存在会话通过；DSH 标准 sdk 空会话跨 runtime 同 ID 恢复通过；保留首次超时证据 |
| 2026-11-05 | 验证发布候选与 master 接口差异 | `0.2.1rc2` 有 resume，但高层配置无 `on_user_question`；未验证历史权限守卫，不冻结产品基线 |
| 2026-11-05 | 创建独立验证工具草稿 PR | [PR #2](https://github.com/xiaoshu2012/ChatBridge/pull/2)，分支 `feat/m1-capability-validation`，目标 `docs/chatbridge-plan`，依赖 PR #1；M1 继续保持阻塞 |
| 2026-11-06 | 完成独立审阅后的修复和回归 | QQ 心跳确认按连接隔离并拒绝无待确认心跳的 ACK；Codex 版本写入探针报告；新增回归先失败再通过，完整 44 项测试与 Ruff 检查通过；真实验收仍阻塞 |
| 2026-11-06 | 修复用户报告的恢复期间补发消息丢弃 | 补发消息通过白名单后有界暂存，RESUMED 后统一回复并去重；恢复未确认/被拒绝均不发送；旧 ACK 修复 `3740147` 保留并回归验证；新增 7 项完整循环测试，完整 51 项通过，快照 `v0.0.0-m1.2` |
| 2026-11-07 | 继续推进已发布 DSH 原生接口验证 | Linux 生命周期策略降级与拒绝恢复通过；程序化问题 NO_PROVIDER；新增隔离 worker 防止 SDK 重新继承 QQ 环境变量，64 项测试通过；快照 `v0.0.0-m1.4` |

决定：沿用用户确认的架构，不以 Linux 结果替代 Windows；M1 保持阻塞，未验收任务不勾选。恢复条件及剩余逐项验收见 [Windows 验收记录](../../../validation/windows-capabilities.md)。
