# 平台与跨项目接入

## 首次采用

1. 确定自己的 GitHub owner、仓库、可见性和管理员，确认是否复用已有仓库；没有
   远端时先确认归属与可见性，私有内容不能因接入流程被公开。
2. 在自己的账户/组织创建跨项目 GitHub Project。用平台读取真实 Project node ID，
   不把网页里的序号当 node ID。按 STATUS-MAPPING.md 建字段和选项。
3. 在自己的 Linear 工作区选 team key（例如 ENG），创建或复用跨项目项目。
   创建阶段状态，核验当前工作区权限。自动化需要准确状态名，不能默认照搬示例已存在。
4. 按最小范围连接 GitHub 与 Linear。核验仓库是否真的配置新 Issue 原生镜像；用一个
   初始化 Issue 观察并回读，而非仅凭集成开关推断。Project 自定义字段独立维护。
5. 复制 registry.example.json 为 registry.local.json，逐仓登记，核对 allowed_owner
   是能发有效结构化回执的 GitHub 登录名；它不是 owner 限制，仓库范围由 repositories
   和 excluded_repos 决定。多个组织可显式登记；当前只信任一个回执作者。
6. 完成检查后置 example_only=false。配置不含 token，但仍应作为私有运维信息保存。
   保留受信本地运行目录，限制访问；不要接受他人提供的计划文件后直接 apply。

可使用已连接 GitHub 工具或本机 `gh` 读取实际资源；Project 管理能力不足时使用 GitHub
网页或已认证 CLI。不要从连接器取出令牌。没有权限时记录具体缺口，交由管理员授权，
不能自行把仓库改公开或扩大 App 访问范围。

## 每个仓库第一次接入

- 确认 Git root、origin owner/repo、当前分支/HEAD、脏改动和上层/项目 AGENTS。
- 查重后建初始化 Issue，写清模板、AI 规则、平台接入、验证与下一步。
- 加入总 Project，设置项目、优先级和工作类型。未验证状态留待整理/待核验。
- `mirror_mode=native`：先等待并准确查到自动镜像，再关联 Linear 项目；缺失时留
  attention 并复查，不退化为另建重复项。
- `mirror_mode=linked`：先按 source URL 查重，创建一个关联任务并添加准确的 GitHub
  Issue attachment；注明“由协调器维护，未配置原生镜像”。回读 UUID 与 attachment。
- 使用独立分支/worktree 和 Draft PR 安装 templates/AGENTS.md、Issue/PR 模板与流程
  文档。保留原有 AGENTS、模板和 CI，不整文件覆盖。模板中的 example-org 等要替换。
- registry.local.json 只登记用户明确接入的仓库。不要自动抓取账号所有历史仓库。
- 回读 Actions 开关、仓库专属 Runner 注册/在线/标签及环境审批。新仓库不会继承其他
  仓库的注册。平台规则/分支保护受当前权限与套餐影响，未核验不能标已生效。

## 跨项目设置

各仓代码保持独立；总 Project 只是跨仓导航。一个跨仓功能设协调 Issue + 各仓实施
Issue；Linear 同样使用 parent/related/blocked-by 的真实关系，并保留准确源 URL。
父任务的验收覆盖双端集成与最终行为，不能直接投影任一子任务的开发或完成阶段。

优先级建议 P0 紧急、P1 高、P2 中、P3 低；Linear 的数值 1–4 可按本团队约定对应。
工作类型建议功能、缺陷、契约/集成、验证/发布、规划/整理。项目名必须与 Project
的“项目”选项匹配。优先级/类型由接入者维护，当前 CLI 不自动修改它们。

## 验证接入是否成功

先用离线演示了解计划，再对初始化 Issue 运行 snapshot/plan。确保恰好一个准确镜像、
UUID/正文 hash 正确、attention 已人工处理。执行一次授权的跟踪更新并逐平台回读，
再以相同输入重跑确认无重复写入。用测试验证陈旧正文、重复镜像和未验收完成均被拒绝。
记录真实平台 URL、时间、分支、完整 SHA、CI 和限制，避免保存原始私有数据到公开仓库。

撤回时停自己配置的协调调度，保留任务与证据，仅撤回新增受管理规则区块；不删除
原有开发/CI 流程。详见 OPERATIONS.md。
