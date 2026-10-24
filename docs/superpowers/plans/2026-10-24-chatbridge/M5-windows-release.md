# M5：Windows 安装、Skill 与首版验收

[返回主规划](../2026-10-24-chatbridge-implementation-plan.md) · [架构设计](../../specs/2026-10-24-chatbridge-design.md) · [上一阶段 M4](M4-qqbot-integration.md) · [下一阶段 M6](M6-macos-support.md)

状态：未开始。依赖：M4 全链路通过。预计：1—2 个工作日。

## 目标与位置

在干净 Windows 11 x64 环境按文档完成安装、配置、启动和真实 QQ 双 Agent 任务，交付可复现的 Python 包。

创建 `skills/chatbridge/SKILL.md`、`scripts/windows/{install,start,stop}.ps1`、`docs/user/{windows,configuration,troubleshooting}.md`、`config/chatbridge.example.toml`、`docs/validation/windows-acceptance.md` 和 Windows CI 工作流。

## 开发步骤

### M5.1：安装、配置和启动

- [ ] 编写 PowerShell 安装脚本，检查 Python 3.12/PowerShell 7，建立 venv 并安装锁定依赖；路径以脚本位置解析，不依赖当前目录。
- [ ] 配置样例使用占位符，说明 QQ AppID/Secret、各上下文身份白名单、群、项目别名、Agent 来源和凭据配置。
- [ ] 数据放 `%LOCALAPPDATA%\ChatBridge`；安装不覆盖已有数据库、配置和 Agent 登录，不自动修改系统服务或全局执行策略。
- [ ] 启动/停止只管理自己的实例；通过实例锁防止两个服务同时消费一个数据库。停止等待当前任务确认终止。
- [ ] 写重复安装、已有配置、中文空格路径、重复启动和非本人进程不受影响的脚本测试。

### M5.2：doctor 诊断

- [ ] 实现 `chatbridge doctor --config <path>`，检查配置、可写数据目录、项目、工具版本、SDK/守卫和 Windows 沙箱准备状态。
- [ ] 默认只做本机检查；`--live` 显式启用网络和真实服务检查，不自动执行项目修改任务或发群消息。
- [ ] 输出每项 pass/fail/blocked 和修复动作，退出码 0/1/2 分别表示通过/失败/前置条件缺失。
- [ ] 测试密钥脱敏、缺工具、路径损坏、依赖版本不匹配，不能只判断可执行文件同名就认定可用。

### M5.3：配套 Skill

- [ ] 写清何时使用、初始化、诊断、启动、停止、注册/恢复会话和常用 QQ 命令。
- [ ] 明确监听与调度由常驻服务负责，Skill 不负责自发后台监听。
- [ ] 定义结果规范：公开摘要、执行状态、明确产物列表；不返回思维和凭据，不自动上传整个工作区。
- [ ] 给出 Codex 和 DSH 的安装位置及验证步骤，引用本机 Python CLI，不在 Skill 中硬编码用户路径。
- [ ] 验证 Skill 所引用的文件、命令和配置与实现一致。

### M5.4：验收与发布

- [ ] Windows CI 运行不需要密钥的单元、集成、脚本和构建测试；发布包中只包含需要的模块、扩展和资源。
- [ ] 干净 Windows 主机按用户指南安装；分别用 Codex 和 DSH 完成私聊、群聊、问答、历史恢复和取消。
- [ ] 断网、token 更新、主动发送关闭、文件失败、服务重启和重复事件场景分别验收。
- [ ] 保存脱敏证据、兼容版本、检查结果和包校验值，未通过项不能勾选。
- [ ] 构建 wheel/sdist，提交发布候选 PR；Windows 验收通过后上传 GitHub Release 产物，不自动发布 PyPI。

## 检查命令与完成标准

```powershell
python -m pytest -m "not live" -q
python -m ruff check src tests
python -m build
chatbridge doctor --config "$env:LOCALAPPDATA\ChatBridge\config.toml"
python -m pytest tests/live/test_windows_acceptance.py -m live -v
```

完成标准：用户从干净环境按指南操作即可跑通完整闭环；两种真实 Agent/私聊/群聊均有证据；停止无残留托管进程，重启不重复执行，结果发送失败仍可领取。

## 失败处理、回退与交接

升级前备份配置和数据库；迁移失败不继续启动，也不删除原数据库。回退使用上一个已验收包和对应备份，不能让旧程序直接写新版未知 schema。

M6 复用公共核心、相同数据库 schema、Skill 和契约测试，只更换平台层及脚本。提交按安装/诊断、Skill/指南、验收/发布记录分开。

## 执行记录

尚未实施；当前没有产品安装命令、发布包或 Windows 通过声明。
