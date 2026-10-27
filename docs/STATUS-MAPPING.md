# 状态、字段与证据

phase 是稳定的回执语义；平台状态名称可在 registry 的 phase_mapping 中覆盖。默认：

| phase | Linear | GitHub Project Status | 进入依据 |
| --- | --- | --- | --- |
| backlog | Backlog | 待整理 | 已登记，待核对范围 |
| todo | Todo | 待开发 | 范围与验收明确，准备实施 |
| development | In Progress | 开发中 | 正在实现；Draft PR 仍属此阶段 |
| review | In Review | 待审核 | 当前候选明确正式请求审核 |
| merge_pending | In Review | 待合并 | 审查通过，等待获准合并 |
| deployment_pending | 待部署 | 待部署 | 审查/合并证据齐备，等待部署决策 |
| acceptance_pending | 待验收 | 待验收 | 已有部署或本任务范围交付证据 |
| blocked | 阻塞 | 阻塞 | 有具体阻塞、解除所需证据和下一步 |
| accepted | Done | 完成 | 原负责人已完成全部验收并完成两处源系统 |

Linear 可把待部署/待验收/阻塞建为 started 类状态，Done 为 completed。GitHub 阶段
选项必须唯一；Linear accepted 状态不能与任何非完成阶段共用。review 与 merge_pending
可以共用 Linear In Review，精细区别保留在 Project 和回执。

## GitHub Project 字段

当前 CLI 使用下列固定字段名称（可以翻译文档，代码字段名仍须一致）。

| 名称 | 类型 | 用途/选项 |
| --- | --- | --- |
| Status | Single select | 上表 GitHub 状态，或本地 phase_mapping 对应值 |
| 项目 | Single select | registry 中各仓 project 名称 |
| 优先级 | Single select | P0 / P1 / P2 / P3，人工或平台工具维护 |
| 工作类型 | Single select | 功能 / 缺陷 / 契约/集成 / 验证/发布 / 规划/整理，人工维护 |
| 验证层级 | Single select | 待核验 / 本地/静态 / 服务器CI/数据库 / 已部署待验收 / 真实用户/客户端验收 |
| 下一步 | Text | 下一步及源回执链接 |
| 阻塞原因 | Text | 当前阻塞，无阻塞时清空 |
| Branch | Text | 真实工作分支 |
| Linear | Text | 准确 Linear 任务 URL |
| 验收标准 | Text（可选） | 便于导航；CLI 不写，源正文仍为验收依据 |

CLI 仅允许 Status、项目、验证层级、下一步、阻塞原因、Branch、Linear。它不自动
创建字段/选项；写入前校验实际字段和值。每次写入后回读，未知选项立即拒绝。

## 回执门禁

所有可推进全任务阶段的回执都要求 `scope=issue`、准确 Issue URL、Linear identifier
及 UUID、当前源正文 UTF-8 SHA256、UUID event_id、带时区 occurred_at。代码活跃阶段
需要 40 位 source_sha；除 accepted 外有下一步。未来超过 5 分钟的回执拒绝。

证据是 `{kind,url}` 数组，url 必须 HTTPS。部署阶段要求 review 或 merge kind；待验收
要求 deployment 或 delivery；“已部署待验收”验证要求 deployment；真实验收验证要求
acceptance。这些只是格式门禁，**操作者仍须打开证据确认真实内容与 SHA**，工具不检验
证据内容或数字签名。文档交付可用 delivery，但不能拿 CI 当部署证据。

accepted 要求 GitHub 已 CLOSED、Linear 已是配置的 accepted 状态、all_conditions_met=true、
scope_body_sha256 匹配当前正文、owner_receipt_url、acceptance 证据。关闭与 Done 应由
原负责人先按完整验收流程办理，CLI 只投影，不能靠回执自己触发完成。

receipt 只接受配置的 allowed_owner 作者。较新的未结构化负责人评论会令旧回执失效，
需要重新对账。同 event_id 不同 payload、同时间不同阶段、重复镜像、正文变化均拒绝。
超过 100 条源评论的任务当前拒绝自动处理，改人工全量对账；不会悄悄忽略旧历史。

没有新完整回执时，普通 Linear Backlog/Todo/开发/审核可投影普通阶段，但不回退
已有待审核、待合并、待部署、待验收、阻塞和完成。映射和任务阶段仍需负责人判断。
