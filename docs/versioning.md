# ChatBridge 版本备份规则

[仓库首页](../README.md) · [协作约定](../AGENTS.md) · [主规划](superpowers/plans/2026-10-24-chatbridge-implementation-plan.md)

每个交付版本的全部项目文件必须在 GitHub 留下可恢复的快照。Git 提交的文件树保存整个版本；每版推送对应分支和独立附注标签，不能只保留本机提交。

## 文件范围

- 纳入该版本的全部源码、测试、设计、主规划与阶段计划、配置样例、依赖声明与锁文件、脚本、Skill、用户指南和脱敏验收记录。不存在的后续阶段文件不需提前创建。
- 提交前检查未跟踪文件及被忽略文件，核对 `.gitignore` 没有误排除项目文件；不得用忽略规则遗漏恢复该版本所需的文件。
- 密钥、登录信息、真实用户消息、运行数据库和未脱敏日志不提交。配置提交占位样例，记录配置及数据库的备份/恢复方法；实际敏感数据另行安全备份。虚拟环境、依赖缓存和可重建的临时文件不属于交付文件。
- wheel、sdist 等正式发布包按发布阶段要求上传对应 GitHub Release，并保存文件清单和 SHA-256；Git 标签保留构建它们的完整项目文件。M0 仅交付文档，无构建包。

## 提交、标签与远端核验

1. 完成该阶段检查，同步主规划和阶段状态，审阅全部项目文件并显式暂存交付文件。运行 `git diff --cached --check` 和 `git diff --cached --stat`。
2. 创建版本提交。可由多个任务提交组成一个版本，最终提交必须包含完整文件树；不得把只有部分任务的快照称为完整交付。
3. 创建唯一的附注标签：文档 M0 首次备份为 `v0.0.0-m0.1`，修订依次为 `v0.0.0-m0.2`；后续阶段使用对应阶段及修订号，正式产品版采用 `vMAJOR.MINOR.PATCH`。不同版本不得复用、删除或移动已发布标签。
4. 显式推送分支及该标签，不使用 force。若远端分支有新提交，先读取并正常整合，不覆盖他人工作；若标签重名，使用新的修订号。
5. 用 `git ls-remote` 核对远端分支 SHA 与本机 HEAD 一致；附注标签的 `^{}` 解引用 SHA 必须与该版本提交一致。任何一项失败，都记录未备份并恢复处理。
6. 交接提供 GitHub 版本标签、提交和 PR 链接，记录检查结果；PR 按仓库约定审批，不自动合并。PR 待合并不影响版本已在文档分支备份。

以下命令用于 M0 的 `docs/chatbridge-plan` 分支；提交及检查完成后再运行，后续版本替换标签和分支名：

```bash
git status --short --untracked-files=all
git ls-files --others --ignored --exclude-standard
git ls-tree -r --name-only HEAD
git tag -a v0.0.0-m0.1 -m 'ChatBridge M0: complete documentation snapshot'
git push origin HEAD:refs/heads/docs/chatbridge-plan
git push origin refs/tags/v0.0.0-m0.1
git rev-parse HEAD 'v0.0.0-m0.1^{}'
git ls-remote origin refs/heads/docs/chatbridge-plan refs/tags/v0.0.0-m0.1 'refs/tags/v0.0.0-m0.1^{}'
```

## 恢复与交付记录

从仓库克隆后执行 `git switch --detach <版本标签>` 即可恢复该版全部已跟踪文件；需要修订时从标签创建新分支。构建与配置按该标签下的指南执行，敏感数据使用另行保存的备份。

M0 版本标签为 `v0.0.0-m0.1`，包含 README、AGENTS、版本规则、架构设计、主规划、M0～M7 阶段计划、LICENSE 和 `.gitignore`。真实检查与交付证据记录在 [M0 执行记录](superpowers/plans/2026-10-24-chatbridge/M0-docs-and-github.md#执行记录)。

M0 README 精简后的收尾版本为 `v0.0.0-m0.2`，保留相同的完整项目文件范围；规划导航维护在 docs 内，不再列入 README。首次标签保持不变。
