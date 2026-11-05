# M1 兼容矩阵

[Windows 验收记录](windows-capabilities.md) · [M1 阶段](../superpowers/plans/2026-10-24-chatbridge/M1-capability-validation.md) · [探针使用](../../tools/probes/README.md)

最后复核：2026-11-05。M1 状态：阻塞。以下 Linux 实测不代替 Windows 11 x64；尚未冻结 M2/M3 的产品依赖基线。

## 版本与官方来源

| 对象 | 已观察的版本/来源 | 证据与结论 |
| --- | --- | --- |
| 当前执行器 | Linux x86_64，Python 3.12.14 | [环境和 SDK 参数](evidence/2026-11-05/sdk-contract.json)；不是用户的 Windows 终端 |
| Codex CLI | 0.163.0 | 实际二进制 `/opt/codex/bin/codex`；无模型协议检查通过，Windows 兼容待验收 |
| DSH Python SDK / runtime | 同版本 `0.2.1rc2`（发布候选） | [PyPI 元数据与 wheel SHA-256](evidence/2026-11-05/pypi-candidates.json)；包含 win_amd64 wheel，存在文件不代表真机通过 |
| DSH 源码文档 | [固定提交 fcc0ad4](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/python/sdk/README.md) | 描述 `on_user_question`；发布候选实际配置类未包含该参数，不能把 master 文档当作已发布能力 |
| QQ 官方事件 | [事件/鉴权/心跳/RESUME/Intents](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html) | 文档校核加人工 fixture；实际应用鉴权和收发未运行 |
| QQ 消息规则 | [消息规则](https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/overview.html) | 回复窗口、次数、主动消息和文件能力需应用实测；设计中的默认值尚未冻结 |
| Codex 官方接口 | [App Server](https://developers.openai.com/codex/app-server/) | 以已安装 0.163.0 的真实握手及返回为协议证据 |

## 能力逐项状态

| 能力 | Codex | DSH | QQ / Windows 证据边界 |
| --- | --- | --- | --- |
| 初始化 | Linux 真实服务通过 | Linux 真实 SDK 标准 sdk profile 通过 | Windows 未运行 |
| 新建 | Linux 空临时 thread 通过，无模型 | Linux 创建空持久会话/读取 cwd 通过 | 不证明执行任务 |
| 同 ID 恢复 | 仅验证不存在 ID 被拒绝；已有会话恢复待验收 | 空会话关闭后，同 ID 跨 runtime 恢复通过 | 含模型历史、占用锁、损坏历史仍待验收 |
| 协议事件 | 未知通知、分片、错误响应等离线测试通过 | SDK 原生事件/终态的模型运行待验收 | fixture 是人工构造，并非真实平台日志 |
| 原生问答 | 待真实模型/Windows 验收 | 候选配置缺少 `on_user_question`，blocked | 需升级到包含契约的发布版本，或验证官方低层替代路径后修订计划 |
| 权限与工作区写入 | 握手显式 workspace-write / never；未执行文件写入 | 没有验证历史 full-access 降级守卫 | 必须证明项目内写入、项目外写入拒绝；配置声明不算执行证据 |
| 取消与关闭 | 无模型进程关闭/异常回收已测；活动任务取消未测 | 空运行时正常 close 已观察；活动任务取消/锁释放未测 | Windows 原生停止和进程树行为待验收 |
| QQ 身份过滤 | 不适用 | 不适用 | 私聊/群身份分离、群 @门控离线通过；实际身份和应用权限待验收 |
| QQ 鉴权/心跳/恢复 | 不适用 | 不适用 | 有显式 live smoke；当前未配置测试应用，未发送消息 |
| QQ 配额/媒体 | 不适用 | 不适用 | 回复窗口/次数、token 更新、主动发送、上传未验收 |

## 可复现结果

- [Codex 无模型协议报告](evidence/2026-11-05/codex-protocol.json)：退出码 0，仅对应 protocol-only scope。
- [DSH 首次初始化超时记录](evidence/2026-11-05/dsh-protocol-initial-timeout.json)：退出码 1，保留失败证据。
- [DSH 复核报告](evidence/2026-11-05/dsh-protocol.json)：恢复官方默认 30 秒初始化上限后，无模型初始化、空会话新建、同 ID 恢复及不存在会话拒绝通过；因为问答与权限守卫尚未满足，整体退出码 2。
- [Windows 前置检查](evidence/2026-11-05/windows-entry.json)、[QQ 前置检查](evidence/2026-11-05/qq-preflight.json)：退出码 2。
- [探针依赖锁定快照](../../tools/probes/requirements-candidate.lock)：只用于重复上述探针环境，不是 Windows 产品验收结论。

真实验收通过后再更新本矩阵和产品依赖范围；不能提前把某版本写为 Windows 已支持。
