# SAKAKIBARA Portfolio Workflow

把 **需求 → Issue → GitHub Project / Linear → 独立分支 → Draft PR → 审查 → 验证 →
合并 → 发布 / 部署 / 启用 → 真实验收** 变成开发者与 AI 都能执行的工作方式。

本项目包含可运行的 Python 进度协调器、测试、AI 规则、项目接入指南与模板。它适合
同时维护多个仓库、使用 GitHub 和 Linear、希望交付有证据且状态不被误标完成的团队。
只读问答、翻译和单次文档处理无需人为创建工程工单。

**© 2026 NovaHelix Corporation & SAKAKIBARA — 可以免费使用。**
沿用仓库已有 [GPLv3 许可证](LICENSE)（GPL-3.0-only）；权利归属与使用说明见
[COPYRIGHT](COPYRIGHT)。使用、修改和再分发须遵循许可证。

## 从哪里开始

| 你要做什么 | 阅读入口 |
| --- | --- |
| 让 AI 按本模式开发 | [AGENTS.md](AGENTS.md)、[AI 引导与提示词](docs/AI-START.md) |
| 理解日常开发、审核与验收 | [完整工作流](docs/WORKFLOW.md) |
| 第一次接入或增加项目 | [平台与跨项目接入](docs/ONBOARDING.md) |
| 配置 Linear 和 Project 状态 | [状态、字段与证据](docs/STATUS-MAPPING.md) |
| 执行即时回写、定时对账或撤回 | [操作手册](docs/OPERATIONS.md) |
| 准备版本、发布、更新说明和验收 | [发布与验收](docs/RELEASE.md) |
| 检查公开前脱敏范围 | [公开检查](docs/SANITIZATION.md) |
| 理解配置、输入格式和限制 | [配置与数据契约](docs/CONFIGURATION.md) |

## 四个平台对象各做什么

| 对象 | 负责保存 | 不能据此推断 |
| --- | --- | --- |
| GitHub Issue | 任务目标、范围、验收条件、依赖、下一步和源回执 | 有 PR 就已交付 |
| GitHub Project | 多仓库总览、优先级、工作类型、阶段与阻塞 | 原生 Linear 集成会同步所有自定义字段 |
| Pull Request | 实现、代码审查、固定 SHA、CI、风险与交付步骤 | 合并就已部署、已启用或已验收 |
| Linear | 规划、依赖、负责人、跨项目导航及准确的源链接 | 标题相似的任务就是同一个任务 |

GitHub 源 Issue 保存验收事实，PR/CI 保存实现证据；Linear 和 Project 根据这些事实
更新跟踪字段。所有平台更新后回读，聊天里的“完成”不能替代平台上的证据。

## 十分钟离线体验

要求 Python 3.10+、macOS 或 Linux；CLI 使用 POSIX 的 `fcntl` 文件锁。Windows 可在
WSL/Linux 中使用。运行演示无需账号、网络、第三方 Python 包或任何凭据：

```bash
git clone https://github.com/fxxkrlab/sakakibara-portfolio-workflow.git
cd sakakibara-portfolio-workflow
python3 scripts/demo.py
```

演示使用 `example-org`、`ENG-1`、虚构 UUID 和 SHA，生成一份待审核的 Project/Linear
计划并展示部分范围不能推进全工单。它不会连接任何平台。所有示例仅供学习。

## 连接自己的团队

1. 按 [接入指南](docs/ONBOARDING.md) 创建自己的 GitHub Project 和 Linear 项目，
   核验权限、字段、状态、原生镜像是否真正生效。
2. 复制配置，填入本人的真实平台 ID、允许的回执作者、明确接入的仓库和 mirror_mode：

   ```bash
   cp config/registry.example.json config/registry.local.json
   ```

3. 逐项完成配置核验后，把本地配置的 `example_only` 改成 `false`。示例配置默认拒绝
   联网操作；本地配置已忽略，不要提交。状态名称可通过 `phase_mapping` 调整；Project
   字段名称按 [字段表](docs/STATUS-MAPPING.md) 创建。
4. 在本机安装并登录 GitHub CLI `gh`，在 AI 工具内连接自己的 Linear 工作区。使用已有
   安全登录，不把 token 写进配置或聊天，不从连接器提取 token。不要为方便扩大访问。
5. 先只读抓取与离线计划，再检查 attention 和每一项更改，最后执行授权范围内的更新。

```bash
mkdir -p runtime
python3 portfolio_sync.py snapshot --output runtime/github.json
# 按 docs/CONFIGURATION.md 用已连接 Linear 工具取得完整、精确的 runtime/linear.json
python3 portfolio_sync.py plan --snapshot runtime/github.json \
  --linear runtime/linear.json --output runtime/plan.json
# 审查计划、处理 attention，并重新取得 Linear 的新鲜完整数据后：
python3 portfolio_sync.py apply --plan runtime/plan.json \
  --linear runtime/linear-fresh.json --output runtime/result.json
```

`snapshot` 是联网读取，`plan` 是离线计算，`apply` 会写 GitHub Project，`emit` 会写
源 Issue 评论。`apply` 不执行 `linear_operations`；这些是需要 AI/操作者逐项核验并通过
Linear 连接工具执行的计划。详细操作见 [操作手册](docs/OPERATIONS.md)。

## 一次真实任务如何流转

例如：API 仓库修复分页错误，客户端仓库也要同步适配。

1. 建一个协调 Issue，两个仓库各有实施 Issue；写出各自验收和集成阻塞关系。
2. 将它们加入总 Project。先按源 Issue URL 查 Linear 原生镜像；未配置镜像的仓库
   只创建一个带源 attachment 的 linked 任务。
3. 各实施任务使用自己的分支/worktree 和 Draft PR。提交引用本仓库源 Issue；
   PR 包含固定 SHA、Linear 关联、测试证据和仍待完成步骤。
4. 实施、PR、CI、阻塞或下一步改变时即时回写四处状态。Draft PR 留在开发阶段，
   准备好正式审核才改待审核；审核通过后才待合并。
5. 实施测试通过后，协调负责人核验两个准确 SHA 的真实契约与集成证据。任一侧
   未通过，保留父任务阻塞，不能用单侧 CI 通过替代双端验收。
6. 合并、版本发布、部署和启用各自按授权推进并留证。真实用户/客户端逐条验收后，
   原负责人完成源系统；协调器只投影已经发生的完成事实。

## 工具能做什么

- 以精确 GitHub Issue URL attachment 绑定 Linear 标识与 UUID；不靠标题猜测。
- 校验结构化回执：唯一 event_id、正文 SHA256、全 SHA、范围、阶段和证据。
- 根据回执计划 Project 跟踪字段与 Linear 状态；不改原验收正文或依赖。
- 拒绝部分实现推进全 Issue、CI 代替部署/验收、提前完成、歧义镜像和冲突回执。
- 写入前检查源正文/更新时间、Linear 快照与 Project 字段前值；写入后回读。
- 对 emit 按 event_id 去重，对本机 apply/emit 加锁，减少重复写入。

工具不提供持续运行服务、平台 webhook 安装、Linear token 管理、自动部署或自动验收。
PR 元数据、优先级/工作类型以及 Linear 状态由操作者/AI 通过平台工具维护。定时执行
需要使用者自行配置调度器，本项目不会安装定时任务。锁仅约束同一本地运行目录；
多台机器需要一个唯一写入协调者。计划摘要不是签名，输入文件和本地运行目录须受信。

## 验证与 CI

在负责人指定的隔离 Linux CI 环境执行：

```bash
python3 -m unittest -v
python3 scripts/demo.py
python3 scripts/check_publication.py --history
```

`.github/workflows/verify.yml` 仅手动触发，默认禁用。需要先完成专属 Runner、安全隔离、
仓库变量和 `workflow-validation` 环境审批。公开仓库不得让未经审查的 fork/PR 代码
进入有私网或生产权限的 Runner。参见 [CI 引导](docs/CI.md)。

测试结果只证明其覆盖范围。首次接入必须记录实际源码 SHA、CI run/job、环境和清理
结果；不能用另一个仓库的旧绿灯宣称本仓库验证通过。

## 仓库内容

```text
AGENTS.md                    AI 执行入口
portfolio_sync.py            进度投影 CLI（Python 标准库）
test_portfolio_sync.py       回执、冲突、幂等与验收门禁测试
test_public_toolkit.py       通用配置与公开边界回归测试
config/registry.example.json 虚构、默认禁止联网的配置
examples/                    虚构回执与 Linear 数据
scripts/                     离线演示、公开检查
templates/                   给其他仓库复制的 AGENTS 与任务模板
docs/                        接入、操作、状态、发布、AI 和脱敏指南
.github/                     本仓库 Issue / PR 模板与手动 CI
```

## 贡献与后续更新

先读 [CONTRIBUTING.md](CONTRIBUTING.md)。对本项目的改进也使用 Issue、独立分支、Draft
PR 和按范围验收。先把组织相关差异做成本地配置，再考虑通用功能；不要把自己的运行
数据放进示例。安全问题通过 [SECURITY.md](SECURITY.md) 所述私下渠道报告。

后续更新使用 allowlist 复制当前文件，比较通用行为与测试，重新脱敏扫描所有新增
文件及历史，不合并私有源的 Git 历史。公开规则的采用不会更改任何组织的权限或生产环境。
