# M1 能力验证工具

这些是独立探针，不是 ChatBridge 常驻程序。默认只检查前置条件；`--protocol-only` 仅执行无模型协议检查。任何探针返回 0 都只表示该 scope 通过，不表示 M1 全部通过；JSON 的 `windows_acceptance` 始终为 false，完整验收另按[Windows 验收记录](../../docs/validation/windows-capabilities.md)逐项完成。

[兼容矩阵](../../docs/validation/compatibility-matrix.md) · [M1 阶段记录](../../docs/superpowers/plans/2026-10-24-chatbridge/M1-capability-validation.md)

## Windows 本机运行

在 Python 3.12 和 PowerShell 7 环境中，从本仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tools/probes/requirements-candidate.lock
.\.venv\Scripts\python.exe -m pytest tests/probes -q
pwsh -NoProfile -File tools/probes/run-windows.ps1 -PythonPath .\.venv\Scripts\python.exe
```

安装清单明确选择已发布的 DSH `0.2.1rc2` 候选版；这是探针依赖快照，还不是产品兼容基线。只需要离线测试时，可以仅安装 `tools/probes/requirements.txt`，DSH 未安装会返回 blocked。

脚本创建中文且带空格名称的临时 Git 项目；Codex 使用新的临时 CODEX_HOME，DSH 使用新的临时 dsh_home 和标准 `sdk` profile，不访问桌面会话，不调用模型。生成的报告位于 `%LOCALAPPDATA%\ChatBridge\M1\<UTC时间-随机标识>\`，每次创建新目录；也可传 `-OutputDir` 指定报告根目录。原有配置、登录和会话不被修改。

如果 npm 的 Codex Windows 安装目录未被自动识别，设置 `CHATBRIDGE_CODEX_BIN` 为官方原生 `codex.exe` 的完整路径；不将 `.cmd`/`.bat` 包装器作为原生服务运行，不拼接 shell 命令。

```powershell
$env:CHATBRIDGE_CODEX_BIN = "C:\实际安装目录\codex.exe"
```

运行入口的退出码 2 表示有缺失前置条件或真实验收项。当前版本还没有双 Agent 模型任务、原生问题、权限边界和取消的完整自动化验收；入口会明确保留这些 blocked 项，不能把一次脚本运行当成完成 M1。

## 独立探针

```powershell
.\.venv\Scripts\python.exe tools/probes/agents.py --agent codex --workspace "C:\Temp\ChatBridge 验证" --protocol-only
.\.venv\Scripts\python.exe tools/probes/agents.py --agent dsh --workspace "C:\Temp\ChatBridge 验证" --protocol-only
.\.venv\Scripts\python.exe tools/probes/qqbot.py
```

工作区必须已经存在。省略 `--protocol-only` 的 Agent 探针只报告前置条件，并返回 2。`dsh_smoke.py` 由父探针在清理 QQ 环境变量后的独立 worker 中调用；SDK 的原始诊断只在内存中，报告只保留类型/错误代码，不转存原始 stdout/stderr。

## QQ 实际收发（显式启用）

先在本机安全配置以下环境变量，不要在聊天中发送值，不要把真实值写入 Git：

| 变量 | 用途 |
| --- | --- |
| `CHATBRIDGE_QQ_APP_ID` / `CHATBRIDGE_QQ_APP_SECRET` | 官方应用鉴权 |
| `CHATBRIDGE_QQ_C2C_OPENID` | 本人单聊身份 |
| `CHATBRIDGE_QQ_GROUP_OPENID` | 允许的测试群 |
| `CHATBRIDGE_QQ_GROUP_MEMBER_OPENID` | 本人在该群的身份，与单聊身份分别配置 |

```powershell
pwsh -NoProfile -File tools/probes/run-windows.ps1 -PythonPath .\.venv\Scripts\python.exe -QQLive
```

或者单独运行 `python tools/probes/qqbot.py --live --seconds 120`。探针先获取 token 和网关，验证 READY 后主动断开一次，用相同 session/seq 发 RESUME，并等待 RESUMED 和心跳 ACK。在测试窗口内本人分别单聊机器人、在允许群 @机器人；每种会话最多发送一次固定回复 `ChatBridge M1 probe OK`。重复消息、非本人、非允许群和没有 @事件的群消息不会触发回复。发送结果 uncertain 时不重试，不执行 Agent。

此 smoke 不验证 token 长时间更新、平台回复窗口/次数、主动消息或媒体权限，也不自动恢复 RESUME 失败后的业务连接；这些仍须真实应用测试。缺少配置不会发网络请求。需要官方 QQ API 和网关访问权限，不能用模拟 HTTP 作为平台通过证据。

## 检查与退出码

- 0：当前 scope 的检查通过。
- 1：检查失败、协议错误或超时。
- 2：缺少前置条件，或尚有必须真实验证的能力。

`tests/probes/` 中的消息均为人工构造的协议 fixture，HTTP 和子进程边界分别通过可控传输和真实子进程测试；它们不是平台或模型实测录制。检查报告只保留代码、版本和操作状态；报告应脱敏复核后才能提交。[版本备份规则](../../docs/versioning.md)仍适用。
