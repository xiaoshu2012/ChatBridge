# ChatBridge Implementation Plan — 主规划

> 面向执行 Agent：使用 `superpowers:executing-plans` 按阶段实施；任务用复选框跟踪。先读取设计和对应阶段文件，不重复实现已完成任务。

**Goal：**用 QQ 私聊/群聊控制本机 Codex 和 DeepSeek Harness，并收取结果。

**Architecture：**Python 常驻服务管理聊天事件、会话、SQLite 队列与 outbox；官方 Agent 服务执行任务。一套核心按平台封装路径和进程管理，Skill 提供入口与工作规范。

**Tech Stack：**Python 3.12、asyncio、Pydantic v2、httpx、websockets、aiosqlite、Codex App Server、DSH Python SDK；DSH 权限守卫为小型扩展。

**Spec：**[架构设计](../specs/2026-10-24-chatbridge-design.md) · [仓库首页](../../../README.md) · [长期约定](../../../AGENTS.md)

## 总体状态

最后更新：2026-10-24。M0 文档已上传 GitHub，[PR #1](https://github.com/xiaoshu2012/ChatBridge/pull/1) 待合并；M1～M7 尚未实施。仓库当前不提供可运行产品。

| 阶段与详细计划 | 状态 | 依赖 | 单人估算 | 可独立检查的产物 |
| --- | --- | --- | --- | --- |
| [M0 文档、导航与 GitHub](2026-10-24-chatbridge/M0-docs-and-github.md) | 完成（PR 待合并） | 无 | 0.5 天 | 设计、主规划、8 份阶段计划、GitHub PR |
| [M1 Windows/官方接口能力验证](2026-10-24-chatbridge/M1-capability-validation.md) | 未开始 | M0 | 1—2 天 | 可复现探针、兼容矩阵、版本记录 |
| [M2 Python 核心与调度](2026-10-24-chatbridge/M2-python-core.md) | 未开始 | M1 | 2—3 天 | 统一类型、配置、SQLite、假适配器闭环 |
| [M3 双 Agent 与恢复](2026-10-24-chatbridge/M3-agent-adapters.md) | 未开始 | M2 | 3—4 天 | 原生适配器、权限守卫、历史恢复、进程托管 |
| [M4 QQBot 完整交互](2026-10-24-chatbridge/M4-qqbot-integration.md) | 未开始 | M3 | 2—3 天 | 私聊/群聊任务、问答、结果与产物投递 |
| [M5 Windows 首版](2026-10-24-chatbridge/M5-windows-release.md) | 未开始 | M4 | 1—2 天 | Skill、安装启动、诊断、真实验收、发布包 |
| [M6 macOS](2026-10-24-chatbridge/M6-macos-support.md) | 未开始 | M5 | 2—3 天 | 进程组/路径适配、macOS 真实验收 |
| [M7 飞书](2026-10-24-chatbridge/M7-feishu-integration.md) | 未开始 | M6 | 2—3 天 | 官方应用机器人适配和双平台隔离验收 |

Windows 首版总估算约 10—15 个工作日；以依赖和真实环境就绪为前提，不是固定交付日期。执行顺序为 M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7。

## Global Constraints — 全局约束

- 所有正式计划和修订都提交并推送 GitHub；主规划与分文件互链。首次文档分支为 `docs/chatbridge-plan`，通过 PR 交付，不自动合并。
- 每个版本的全部项目文件都提交并推送 GitHub，使用独立版本提交及附注标签保存完整快照；交付前核验远端分支和标签。文件范围、敏感数据与发布包处理遵循[版本备份规则](../../versioning.md)。
- Python 3.12；Windows 11 x64 优先，之后 macOS 14+ Apple Silicon。以 M1 实测版本为产品依赖基线，不能用滚动 master 代替发布版本验证。
- 首版是个人使用：本人身份白名单、群白名单和 @门控。普通文本执行，控制命令单独路由；首版全局单任务。
- 工作区内自动写入，拒绝权限升级；历史会话恢复前重新落实权限。允许系统/依赖读取及正常联网。
- 不重写 Agent loop、不改原生会话日志、不抢占活跃会话、不删锁、不默默替换损坏会话。
- 任务状态与投递状态分开；发送失败不重跑 Agent；重启不重放原 running 任务。
- 不转发思维内容；不提交密钥、真实消息或未脱敏日志；QQ 密钥不传入 Agent。
- 每阶段完成设计中的检查并记录证据，再进入下一阶段；缺少真机/凭据时标 blocked。

## 模块和契约索引

具体字段及 Python Protocol 以[设计中的公共接口](../specs/2026-10-24-chatbridge-design.md#公共接口与数据类型)为准。

| 责任 | 计划中的位置 | 所属阶段 |
| --- | --- | --- |
| 类型、配置、路由、调度、问答 | `src/chatbridge/core/` | M2 |
| SQLite、schema 版本、inbox/outbox | `src/chatbridge/storage/` | M2 |
| Codex、DSH、协议收发与映射 | `src/chatbridge/agents/` | M3 |
| DSH 权限守卫 | `extensions/dsh-chatbridge-guard/` | M3，M1 先验证扩展点 |
| Windows Job Objects、macOS 进程组 | `src/chatbridge/os/` | M3/M6 |
| QQ、飞书平台适配 | `src/chatbridge/platforms/` | M4/M7 |
| CLI 与服务装配 | `src/chatbridge/cli.py`、`service.py` | M2～M5 |
| Skill、启动脚本、用户指南 | `skills/chatbridge/`、`scripts/`、`docs/user/` | M5/M6 |

## Review Focus — 跨阶段检查点

| 容易遗漏的输入或故障 | 期望行为 | 覆盖阶段 |
| --- | --- | --- |
| 相同自然人在私聊与群中的不同身份 ID | 分别授权，不用消息文本里的 QQ 号证明身份 | M1/M4 |
| 恢复曾为 full-access 的 DSH 会话 | 首个模型请求前限制权限，无法落实则拒绝 | M1/M3 |
| 发送超时但平台可能已收件 | 不盲目重复推送，不重跑任务，记录 uncertain | M2/M4 |
| 等待问题时进程退出，旧回答稍后到达 | 旧引用失效，不能回答下一任务或授予权限 | M2/M3 |
| 产物路径经链接或替换逃出工作区 | 上传前检查真实路径，拒绝项目外文件 | M4/M5 |

## 阶段完成规则

1. 先读取当前阶段的接口与前置条件，完成有判别力的失败测试，再实现功能并验证。
2. 协议 fixture 和假适配器测试无需真实模型；真实 SDK、QQ、Windows/macOS 证据单独记录。
3. 每阶段保留任务 ID、命令、结果、脱敏证据、commit 和 PR 链接；主规划状态与分文件同时更新。
4. 状态仅使用未开始、进行中、阻塞、完成；未满足真机验收不能完成。
5. 功能或计划变更通过独立提交说明，不把未完成的代码与文档完成状态混为一谈。
6. 每个交付版本按[版本备份规则](../../versioning.md)提交全部项目文件并推送分支与版本标签；只有核验远端 SHA 后才能报告已备份，执行记录保留版本标签和 PR 入口。

## 本轮交付范围与执行记录

本轮先完成 M0：实际保存并上传全部计划、设计和导航。产品代码与 M1 真机验证由后续阶段交付。

| 日期 | 记录 | 证据 |
| --- | --- | --- |
| 2026-10-24 | 已确认官方 QQBot、双 Agent、SDK/服务接入、Windows 优先、私聊/群聊、历史恢复和工作区写入边界 | 见架构设计 |
| 2026-10-24 | 已检查当前执行环境为 Linux/Python 3.12，不能据此认定 Windows 能力通过 | M1 尚未验收 |
| 2026-10-24 | M0 文档及 GitHub 导航已交付，56 个相对链接检查通过 | [PR #1](https://github.com/xiaoshu2012/ChatBridge/pull/1) · [M0 执行记录](2026-10-24-chatbridge/M0-docs-and-github.md#执行记录) |
| 2026-10-24 | 补充每版全部项目文件的 Git 备份约定；复核 13 份 Markdown、65 个相对链接及全部 15 个项目文件，独立审阅无问题 | [版本备份规则](../../versioning.md) · 交付标签 `v0.0.0-m0.1`，沿用 PR #1 |
