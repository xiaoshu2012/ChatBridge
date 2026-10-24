# M6：macOS 适配与真实验收

[返回主规划](../2026-10-24-chatbridge-implementation-plan.md) · [架构设计](../../specs/2026-10-24-chatbridge-design.md) · [上一阶段 M5](M5-windows-release.md) · [下一阶段 M7](M7-feishu-integration.md)

状态：未开始。依赖：Windows 首版 M5 通过。预计：2—3 个工作日。

## 目标、边界与位置

在 macOS 14+ Apple Silicon 上运行同一个 Python 包，保持 QQ、Codex、DSH、队列和权限契约。首轮不承诺 Intel/旧 macOS 支持，不制作 GUI，也不把 Windows ACL 模拟为 macOS 沙箱。

创建 `src/chatbridge/os/macos.py`、`scripts/macos/{install,start,stop}.sh`、`docs/user/macos.md`、`docs/validation/macos-acceptance.md` 及 macOS CI；公共行为仍使用设计中的接口。

## 开发步骤

### M6.1：路径与安装

- [ ] 用平台路径注入写测试，再实现 `~/Library/Application Support/ChatBridge` 数据目录和配置发现。
- [ ] 安装脚本检查 Python 3.12、目标架构和 M1/M5 兼容的 SDK/runtime 产物；不使用 sudo，不覆盖已有配置。
- [ ] 使用绝对工具路径或明确的 PATH 查找，测试从终端与不同工作目录启动、中文/空格/非 ASCII 文件名。
- [ ] 校验 SDK 原生产物支持当前系统；未知架构明确拒绝，不错误套用 Windows 依赖。

### M6.2：进程组与权限

- [ ] 实现与 Windows 相同的 ProcessSupervisor 接口，以独立进程组启动自有 Agent。
- [ ] 写 `test_cancel_stops_owned_process_group`、`test_cancel_does_not_kill_other_agent_instance`、`test_stop_is_idempotent`。
- [ ] 优雅退出最多 10 秒，再回收整个自有进程组并 wait；任一任务处于 waiting_input 时仍支持取消。
- [ ] 真实验证两个 Agent 的 macOS 工作区写入和 DSH 历史权限守卫；不能只检查路径字符串而声称沙箱已生效。
- [ ] 验证 symlink、大小写路径、文件消失和已有会话 cwd 的物理目录身份；重用公共产物校验逻辑。

### M6.3：回归、指南与发布

- [ ] macOS CI 运行公共核心、平台和假适配器套件；Windows CI 保持通过。
- [ ] 编写安装、工具登录、配置、启动/停止和 doctor 指南；复用现有 Skill，补充平台差异。
- [ ] 真实 macOS 分别验证 Codex/DSH 私聊、群聊、问答、取消、历史恢复和结果领取。
- [ ] 记录进程退出、重启不重复执行、网络中断恢复和产物发送证据。
- [ ] 构建/安装发布候选，在真实验收后更新兼容矩阵、README 和 GitHub 产物。

## 检查命令与验收

```bash
python -m pytest -m 'not live' -q
python -m pytest tests/os/test_macos.py -q
chatbridge doctor --config "$HOME/Library/Application Support/ChatBridge/config.toml"
python -m pytest tests/live/test_macos_acceptance.py -m live -v
```

完成条件与 Windows 相同，但必须有 macOS 真实证据；Linux 上相同的进程组测试不能代替。两平台包使用同一业务 API 和 SQLite schema，新增差异限于平台适配。

## 失败处理与交接

沙箱、运行时产物或进程组托管不可用时明确 blocked，不使用 full-access 回退。停止只作用于当前实例，不通过进程名批量 kill 系统中的 Codex/DSH。

提交按路径/脚本、进程管理、验收/指南分开；M7 使用两平台已验证的 ChatAdapter 装配方式。

## 执行记录

尚未实施；当前 Linux 执行环境不构成 macOS 验收。
