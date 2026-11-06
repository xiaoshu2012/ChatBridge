# M1 Windows 能力验证与执行记录

[M1 阶段计划](../superpowers/plans/2026-10-24-chatbridge/M1-capability-validation.md) · [兼容矩阵](compatibility-matrix.md) · [探针使用](../../tools/probes/README.md)

最后更新：2026-11-06。状态：阻塞。M0 已收尾并备份为 `v0.0.0-m0.2`；M1 已交付协议探针、离线测试、Windows 本机入口和脱敏证据，尚未完成真实 Windows/模型/QQ 验收。

## 当前已完成与执行边界

用户已明确使用正在操作的 Windows 电脑。当前聊天可执行的 shell 仍位于云端 `/workspace/ChatBridge`，检测为 Linux x86_64，未连接用户 Windows 的本机终端；应用终端查询返回未附加终端。此限制不表示用户没有 Windows 环境，也不能据此声称 Windows 已运行测试。

已检查：协议分帧与未知通知、stdout/stderr 分离、RPC 错误、权限请求拒绝、子进程退出/超时、worker 回收、退出码和报告、QQ 身份门控/握手/心跳/RESUME、请求鉴权及不确定投递不重试。测试消息和 HTTP 返回均为人工构造。

Linux 真实 Codex 0.163.0：使用临时 CODEX_HOME，初始化、新建空会话以及不存在会话拒绝通过。Linux 真实 DSH `0.2.1rc2`：标准 sdk profile，无模型初始化、空会话创建、重开 runtime 后同 ID 恢复、cwd 校验和不存在会话拒绝通过。没有发送模型 prompt，也没有使用真实 QQ 凭据或发送消息。

## 本机执行入口

完整安装和命令见[探针使用](../../tools/probes/README.md#windows-本机运行)。在本机仓库检出 `feat/m1-capability-validation`，用 Python 3.12 的虚拟环境安装探针锁定依赖后运行：

```powershell
pwsh -NoProfile -File tools/probes/run-windows.ps1 -PythonPath .\.venv\Scripts\python.exe
```

这一步产生本机协议报告，不会完成下面的真实模型验收。准备好官方应用和本人/群白名单环境变量后，加 `-QQLive` 验证固定回复收发。报告存放在 `%LOCALAPPDATA%\ChatBridge\M1\<UTC时间-随机标识>\`；复核脱敏后再纳入 Git。

## 仍须真实执行的验收

| ID | 场景 | 通过条件 | 当前状态 |
| --- | --- | --- | --- |
| WIN-01 | Windows 11 x64、Python 3.12、PowerShell 7 | 本机报告含版本，中文和带空格的临时 Git 目录可用 | blocked：当前聊天未附加本机终端；本机执行脚本已提供 |
| QQ-01 | 本人单聊和允许群 @机器人 | 两个上下文分别收到固定回复，原生身份字段分别确认 | blocked：凭据只在本机配置，当前未运行 live |
| QQ-02 | token 更新、心跳与 RESUME | 真实 ACK/RESUMED 和更新证据；错误路径可辨认 | blocked：fixture 通过不足以完成 |
| QQ-03 | 回复次数/窗口、去重、主动消息、上传 | 与现行文档及实际应用权限逐项核对、记录 | blocked：未测，不冻结设计默认限额 |
| CDX-01 | 原生新建、模型任务、终态、恢复上下文 | 原生 ID 不变，保存前一轮上下文 | blocked：Linux 空会话 smoke 不含任务执行 |
| CDX-02 | 原生问题与取消 | 问答往返正确；中断后终态和进程/锁明确 | blocked：未测 |
| CDX-03 | Windows 沙箱与历史占用 | 项目内写成功、项目外拒绝；占用时不接管、不删锁 | blocked：未测 |
| DSH-01 | 标准 sdk、PowerShell、任务与恢复 | 官方发布版在本机完成模型执行和原生历史恢复 | blocked：仅 Linux 无模型检查 |
| DSH-02 | 原生问题 | 原问题逐一回答、取消后旧回答失效 | blocked：候选版高层回调接口缺失 |
| DSH-03 | 历史 full-access 降级守卫 | 首个模型请求前应用并核验权限，失败不接收 prompt | blocked：未实现/验证发布版扩展点与守卫探针 |
| DSH-04 | 活动运行时关闭与 writer 锁 | 停止活动、落盘并释放锁，其他客户端不被终止 | blocked：未测；正常 close 空 runtime 不证明此项 |

## DSH 发布版本差异

[发布候选 API 参数证据](evidence/2026-11-05/sdk-contract.json)来自安装的 wheel，并与[固定源码文档](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/python/sdk/README.md)比较。候选版本有 `resume_session`，但 `DeepSeekHarnessConfig` 没有 `on_user_question`；不能因为构造函数存在 `**kwargs` 就判断支持回调。当前仅证明所选高层 API 不满足计划，未证明官方低层协议无法实现。

恢复条件：选择含所需契约的可安装发布版本，或在正式修订设计后证明官方低层问答路径；并在该版本上验证权限扩展点和 full-access 历史守卫。不得切换 sdk-minimal/full-access，或用提示词代替权限控制。

## 检查和交付记录

| 日期 | 动作 | 证据 |
| --- | --- | --- |
| 2026-10-24 | README 移除规划，M0 收尾版本推送并核验 | `v0.0.0-m0.2` / `e3ea76b`，PR #1 待合并 |
| 2026-10-24 | 初次开发协议探针与测试 | 环境重建前草稿未提交；原测试结果不充当当前文件的验证证据 |
| 2026-11-05 | 从 Git 恢复 M0，并恢复/验证探针 | `792a758` 已推送，30 项测试通过 |
| 2026-11-05 | Windows 入口、退出码与 worker 回收 | `2c5af1d` 已推送，36 项测试通过；Windows 行为仍须本机实测 |
| 2026-11-05 | 发布版复核和 Linux 无模型协议检查 | [兼容矩阵](compatibility-matrix.md)及本目录 evidence；DSH 首次超时与复核结果均保留 |
| 2026-11-06 | 独立审阅后的修复与最终检查 | 修复 QQ 重连沿用旧 ACK 的误判，只接受当前连接待确认心跳的 ACK；Codex 报告直接记录真实二进制版本；新回归测试先失败再通过，完整 44 项通过；[最终检查记录](evidence/2026-11-06/final-checks.txt) |
| 2026-11-06 | 复核真实 Codex 版本及协议 | [0.163.0 协议报告](evidence/2026-11-06/codex-protocol.json)，仅为 Linux 无模型检查；当前聊天仍未附加 Windows 本机终端 |
| 2026-11-06 | 修复恢复期间丢弃补发消息，验证旧连接 ACK 不算通过 | 新增私聊/群聊补发、确认前不发送、恢复失败/超时、重复消息和缺失当前连接 ACK 的完整循环回归，先复现失败再修复；[修订检查记录](evidence/2026-11-06/qq-recovery-regression.txt)；完整 51 项测试通过 |

所有版本保留完整项目文件树；最新 M1 探针修订快照为 `v0.0.0-m1.2`，首次快照 `v0.0.0-m1.1` 保留，均不表示阶段已验收。[草稿 PR #2](https://github.com/xiaoshu2012/ChatBridge/pull/2) 位于 `feat/m1-capability-validation`，依赖 M0 的 PR #1，未经授权不合并。最终提交通过版本标签定位，交接时核验远端分支及标签解引用 SHA。M2/M3 的产品基线不在此时冻结。
