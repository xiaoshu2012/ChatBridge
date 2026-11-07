# M1 DSH 已发布运行时原生扩展验证

日期：2026-11-07。范围：Linux x86_64、Python 3.12.14、官方 SDK/runtime wheel `0.2.1rc2`、标准 `sdk` profile。本记录不代表 Windows、真实模型或文件写入边界验收通过。

[M1 阶段](../superpowers/plans/2026-10-24-chatbridge/M1-capability-validation.md) · [兼容矩阵](compatibility-matrix.md) · [探针使用](../../tools/probes/README.md)

## 已确认的原生入口

| 入口 | 本次实际验证 |
| --- | --- |
| `dsh plugin --profile sdk add file:<本地 bundle>` | 在全新临时 dsh_home 安装本地 bundle 成功；未修改真实用户 profile |
| bundle manifest `dsh.bundle.patch` | 加载独立 `cordis.patch.yml`；新增插件行需使用 `insert` |
| `agent/created` | 发布版事件参数为 `{ agent, source, signal }`；新建观察为 `source: startup`，恢复观察为 `source: resume` |
| `setSandboxMode` | 从官方 `@deepseek-ai/dsh-sandbox-policy` 根入口导入，在恢复回调中写入原生策略 |
| `setApprovalPolicy` | 从官方 `@deepseek-ai/dsh-user-approval` 根入口导入，将恢复会话审批策略设为 `never` |
| `sandboxPolicy.resolve` / `approval.effectivePolicy` | 回读实际策略，不能只凭配置或 SDK 初始化成功就判断生效 |

调查中发现：直接写一个不存在的 patch 目标行可能只产生警告；从 profile 外挂载模块也不能代替正确的 bundle 依赖解析。即使 SDK 初始化成功，守卫模块仍可能未加载。正式探针要求每个阶段都有注册完成后的 `plugin-ready` 标记，缺失时返回失败。

## 四阶段、无模型验证

1. **seed**：通过公开原生函数，在临时空会话写入 `danger-full-access / ask`，关闭运行时使其持久化。此阶段不提交 prompt、不调用模型或工具，不接触用户历史会话。
2. **guard**：新开运行时，按原 ID 恢复该空会话。真实回读先观察到历史 `danger-full-access`，随后由生命周期回调改为 `workspace-write / never`；核对规范化工作区一致。
3. **reject**：再次恢复时让已注册守卫抛出固定测试异常。SDK 返回对应 RPC 错误，确认恢复被拒绝。此项证明生命周期挂钩的主动拒绝路径，不代替所有真实策略故障和模型入站路径验收。
4. **question**：通过官方 SDK 的通用 `request` 发送带 `capabilities.userQuestions: true` 的初始化，在原生服务上程序化发出一条固定问题；SDK `next_request` 仅对匹配的测试题答复，不接受权限审批。发布候选本次返回 `NO_PROVIDER`，未观察到宿主问答往返。

代码不会调用 `run()` 或 `session_prompt()`。原生问题是构造的服务级请求，不是模型生成的用户问题。

## 真实运行结果

最终 worker 版本的[报告](evidence/2026-11-07/dsh-native-worker-report.json)和[脱敏原生事件](evidence/2026-11-07/dsh-native-worker-events.json)均已保存。

| 检查 | 结果 |
| --- | --- |
| 本地 bundle 的生命周期挂钩加载 | pass |
| 历史权限覆盖实际存在并在恢复时回放 | pass |
| 恢复后策略回读为 `workspace-write / never` | pass |
| 守卫抛错导致恢复拒绝 | pass |
| 原生宿主问题往返 | blocked / `NO_PROVIDER` |
| 首个模型请求前的完整入站阻断 | blocked / 未在本次无模型流程中执行 |
| Windows 实际写入边界 | blocked / 未在本次执行 |

整个探针退出码为 **2**。不能把成功安装模块、初始化声明能力或上述四项 pass 当作 M1 完成。

`NO_PROVIDER` 说明本次安装版本和标准 profile 下没有答复该程序化问题的提供者，进一步缩小了问题范围；它不证明所有官方扩展或未来发布版本都无法实现问答。M3 的实际问答 API 仍不能仅依据 master 文档冻结。

## 运行方法

已安装 [候选依赖快照](../../tools/probes/requirements-candidate.lock)、`pnpm` 可用且临时工作区存在时：

```powershell
.\.venv\Scripts\python.exe tools/probes/dsh_native.py --workspace "C:\Temp\ChatBridge 验证"
```

需要保留脱敏原生事件时，加 `--events-file <新 JSON 路径>`；父目录须已存在，已有文件不会覆盖。Linux 本轮使用 `.venv/bin/python` 执行同一工具，模块管理环境为 Node v24.19.0、pnpm 11.25.0；这些不是已验收的 Windows 产品基线。

本工具使用隔离 worker。SDK 会把 `HarnessConfig.env` 叠加到父进程环境上，单纯过滤传入字典不能移除 QQ 凭据；因此父入口以过滤后的环境启动 worker，worker 再清理自身 QQ 前缀变量，然后才启动 SDK。调用终端的环境保持不变。回归测试在官方 SDK 的 `subprocess.Popen` 边界拦截合并结果验证，未启动进程或打印凭据。

## 验证、证据与限制

- [13 项原生审计测试](../../tests/probes/test_dsh_native.py)覆盖缺失挂钩、历史权限证据、双策略回读、工作区不符、拒绝恢复、问答未转发/错误答案、SDK 环境重新合并及缺依赖行为。
- 完整 `.venv/bin/python -m pytest -q`：64 项通过，包括安装的官方 SDK 环境合并回归。
- Ruff 检查、17 个 Python 文件格式检查、Node 模块语法检查及 `git diff --check` 通过。
- 独立审阅发现的环境继承问题已按失败测试修复；已经完成但内容不符的问答结果也改为 fail，不能归为缺少前置条件。
- [初版报告](evidence/2026-11-07/dsh-native-report.json)与[初版事件](evidence/2026-11-07/dsh-native-events.json)保留；当时环境没有配置 QQ 凭据。最终交付以隔离 worker 版本为准。
- 包含 seed 和主动 reject 的 [bundle](../../tools/probes/dsh_native_bundle/index.mjs)仅用于本工具临时 home，不能作为生产权限守卫安装进用户 profile。

## 官方来源

源文件比较固定到 `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`；wheel 与源码分开验证，不假设 master 等于发布候选：

- [Python SDK 文档及本地 bundle 管理](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/python/sdk/README.md)
- [原生沙箱策略函数与回读](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/sandbox/sandbox-policy/src/index.ts)
- [原生审批策略函数](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/interaction/user-approval/src/index.ts)
- [SDK 问答桥接源码](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/sdk/server/src/user-questions.ts)
