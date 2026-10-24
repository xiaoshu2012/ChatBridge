# M0：文档、导航与 GitHub 交付

[返回主规划](../2026-10-24-chatbridge-implementation-plan.md) · [架构设计](../../specs/2026-10-24-chatbridge-design.md) · [下一阶段 M1](M1-capability-validation.md)

状态：完成（[PR #1](https://github.com/xiaoshu2012/ChatBridge/pull/1) 待合并）。依赖：无。预计：0.5 个工作日。此阶段只交付文档，不开发产品代码。

## 目标与产物

让用户能从 GitHub README 进入主规划，逐一打开 M0～M7，并返回上级。每阶段写清开发任务、接口、测试、验收和交接。以后所有正式计划及修订也必须上传 GitHub。

产物是架构设计、主规划、本目录八份阶段计划、README 导航和根目录 AGENTS.md。后续开发接口以架构设计为单一来源。

## 开发步骤

### M0.1：建立文档与规则

- [x] 保存已确认的架构设计，区分设计目标与已验证事实。
- [x] 编写主规划，包含阶段依赖、估时、状态和全部子文件入口。
- [x] 创建 M0～M7，各文件使用统一章节和任务编号。
- [x] 在 AGENTS.md 记录“正式计划必须提交和推送 GitHub”，并要求后续维护双向链接。

### M0.2：建立 GitHub 导航

- [x] README 添加设计、主规划和各阶段入口。
- [x] 主规划用 `2026-10-24-chatbridge/Mx-*.md` 链接分文件。
- [x] 分文件用 `../2026-10-24-chatbridge-implementation-plan.md` 返回上级，并提供前后阶段和设计链接。
- [x] 检查所有相对文件路径和 Markdown 锚点，无断链、无本机绝对路径。

### M0.3：提交与发布

- [x] 执行 `git diff --check`，审阅 diff，确认只包含文档和导航。
- [x] 提交至 `docs/chatbridge-plan`，推送到 origin，不覆盖已有分支提交。
- [x] 创建目标为默认分支的文档 PR，说明文件组织和检查结果。
- [x] 核验远端提交以及 PR 文件清单；在执行记录中写入 PR 链接。
- [x] 同步本文件与主规划状态，推送最终修订，返回真实 GitHub 链接。

## 检查与验收

路径检查覆盖 README、AGENTS、设计、主规划和八个分文件：提取相对链接，按链接所在目录解析，确认目标文件存在；带 `#` 的链接校验标题锚点；忽略 HTTPS 外链的本地路径解析。

```bash
git diff --check
git diff --stat
git ls-remote --heads origin docs/chatbridge-plan
```

预期：空白检查通过；只修改文档；远端分支 SHA 等于本机最终 HEAD。GitHub 页面可从 README → 主规划 → 任意阶段 → 主规划完成跳转。

## 失败处理与交接

认证失败时先使用已经可用的 GitHub 连接或 Git 凭据，不读取/打印密钥；若所有写入途径均失败，保留本机提交并明确说明未上传，不能报告已完成。分支已存在时读取其头提交再继续，不 force 覆盖。

PR 未合并前，文档位于文档分支；交接必须给出该分支的文件链接，不能把仍为空的 main 当作交付入口。不自动合并。

M1 从已提交的设计与阶段计划开始，在真实 Windows 环境建立证据。

## 执行记录

| 日期 | 动作 | 结果/证据 |
| --- | --- | --- |
| 2026-10-24 | 检查仓库 | 原仓库只有 README、LICENSE、.gitignore |
| 2026-10-24 | 建立文档分支与文档 | 已编写 12 份 Markdown（含 README/AGENTS），其中 8 份阶段计划 |
| 2026-10-24 | 本机文档检查 | 56 个相对文件/锚点链接、阶段完整性、代码围栏和 staged diff 空白检查通过；独立只读审阅无重要问题 |
| 2026-10-24 | 推送并核验远端 | 文档提交 `062c003` 已在 origin/docs/chatbridge-plan，12 个文档文件；后续状态修订随同一 PR 提交 |
| 2026-10-24 | 创建文档 PR | [PR #1](https://github.com/xiaoshu2012/ChatBridge/pull/1)，目标 main，尚未合并 |
