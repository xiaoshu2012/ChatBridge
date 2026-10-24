# ChatBridge

以 Python 为核心，将聊天平台与本机 Agent、工具及自动化工作流连接起来。

目标是在官方 QQBot 私聊或群聊中发送任务，由 Codex 或 DeepSeek Harness 执行，并在原会话接收进度、回答问题和领取结果。

**当前为计划文档交付阶段；尚未交付可运行的桥接程序，Windows/macOS 和真实 QQ 验收均未完成。**

## 设计与主规划

- [架构设计：目标、接口与行为边界](docs/superpowers/specs/2026-10-24-chatbridge-design.md)
- [主规划：阶段进度、依赖与开发安排](docs/superpowers/plans/2026-10-24-chatbridge-implementation-plan.md)
- [协作约定：后续所有正式计划都提交至 GitHub](AGENTS.md)
- [版本备份：每版完整文件、Git 提交与版本标签](docs/versioning.md)

## 分阶段开发计划

| 阶段 | 具体开发说明 |
| --- | --- |
| M0 | [文档、导航与 GitHub 交付](docs/superpowers/plans/2026-10-24-chatbridge/M0-docs-and-github.md) |
| M1 | [Windows 与官方接口能力验证](docs/superpowers/plans/2026-10-24-chatbridge/M1-capability-validation.md) |
| M2 | [Python 核心、SQLite 与调度](docs/superpowers/plans/2026-10-24-chatbridge/M2-python-core.md) |
| M3 | [Codex、DSH、权限与会话恢复](docs/superpowers/plans/2026-10-24-chatbridge/M3-agent-adapters.md) |
| M4 | [QQBot 私聊、群聊及结果回传](docs/superpowers/plans/2026-10-24-chatbridge/M4-qqbot-integration.md) |
| M5 | [Windows 安装、Skill 与首版验收](docs/superpowers/plans/2026-10-24-chatbridge/M5-windows-release.md) |
| M6 | [macOS 适配与验收](docs/superpowers/plans/2026-10-24-chatbridge/M6-macos-support.md) |
| M7 | [飞书应用机器人适配](docs/superpowers/plans/2026-10-24-chatbridge/M7-feishu-integration.md) |

所有链接均为仓库相对链接，可在 GitHub 中逐级浏览；分文件顶部可以返回主规划。
