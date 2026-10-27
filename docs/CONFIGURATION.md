# 配置与数据契约

## 依赖和支持范围

Python 3.10+、POSIX/macOS/Linux/WSL，纯标准库；联网需要已登录的 `gh`。`gh` 可以
在 PATH；macOS 兼容标准 Homebrew 安装路径。没有 Windows 原生文件锁适配。
CLI 不安装依赖、不启动服务器、不读取自定义 token 环境文件。

默认配置 `config/registry.local.json`；可用 `--registry PATH`（放子命令前）指定。
仓库只提供 `registry.example.json`。`example_only=true` 或缺失会拒绝所有 CLI 操作；
完成自己的配置与权限核验后置 false。示例数据不是真实平台对象，不能直接用于联网。

| 配置 | 含义 |
| --- | --- |
| version | 当前为 1 |
| example_only | 必须显式 false 才能启动 CLI |
| project_id | GitHub Project 的真实 node ID |
| project_url | 便于人工回读的页面 URL；CLI 以 node ID 执行 |
| allowed_owner | 唯一受信 GitHub 回执作者登录名，不是仓库 owner 限制 |
| linear_team / linear_default_project | 给接入者与 AI 的上下文；CLI 不查询或创建 Linear |
| repositories | 明确接入的 repo、Project 项目选项、native/linked 镜像模式 |
| excluded_repos | 即使出现在登记中也不允许投影写入的仓库 |
| phase_mapping | 可选；每 phase 对应准确 linear/github 状态名；缺项沿用默认 |

Project 字段目前固定中文名称，见 STATUS-MAPPING.md。一个 CLI 实例负责一个 Project，
多台主机不可各自认为本地锁能约束其他机器；应指定唯一写入者。

## Linear 输入

由已连接 Linear 工具分页列候选，对每个精确任务回读取 identifier、UUID、状态、
更新时间和 attachments；不要把列表中的不完整 description 当完整验收。保存成数组：

```json
[
  {
    "id": "ENG-1",
    "uuid": "11111111-1111-4111-8111-111111111111",
    "url": "https://linear.app/example-workspace/issue/ENG-1/demo",
    "status": "In Progress",
    "updatedAt": "2026-01-05T00:00:00Z",
    "attachments": [{"url": "https://github.com/example-org/service-api/issues/1"}]
  }
]
```

id 使用 ENG-1 这样的 identifier，不用 UUID 代替。来源于连接器时注意某些列表的 id
可能是 UUID，须归一化。输入必须包含本次范围内所有候选，包括可能的重复镜像；
空结果、分页不全和权限错误不能当作“没有任务”。CLI 无法独立判断快照新鲜度，操作者
应在计划前和 apply 前各取一次新数据并核对 expected_updated_at。

## 结构化回执

examples/receipt.json 是字段示例。source_body_sha256 对精确源正文 UTF-8 字节计算，
包括真实换行；不要对 Markdown 渲染结果计算，也不要手写哈希。

```python
import hashlib
body_hash = hashlib.sha256(source_body.encode("utf-8")).hexdigest()
```

`source_sha` 是实现所在完整 commit SHA；branch/PR 不能替代 SHA。
`work_kind=code` 表示代码；文档可用 documentation。phase 与 validation 见状态指南。
可附 `pr_url` 供人工维护 PR 关联，当前 CLI 不操作 PR。发生新的事实时生成新 event_id；
同一事件重试必须保留相同 payload，包括 occurred_at。

snapshot 的原始输出包含配置 Project 的全部字段和条目元数据；登记仓库范围只限制
读取的源 Issue 正文/评论与后续计划，不裁剪整块 Project 元数据。整个 snapshot 都须
按私有数据保存，不要因为使用最小 registry 就将其公开。

## 计划与结果

plan 输出 operations（GitHub Project）、linear_operations（供连接工具执行的计划）、
attention（歧义/缺失/拒绝原因）和 digest。digest 只是意外修改校验，不是授权签名。
不要处理不受信本地计划文件。不要手改计划中的状态来绕过回执；应修改真实事实并重建。

apply 使用新鲜 Linear 输入比对计划的 UUID、identifier、status、updatedAt，再现场读取
GitHub 源/Project。冲突返回 conflict-source / conflict-linear / conflict-project /
conflict-item；已成功的其他项可能已写入，不是跨平台事务。逐项核对 result，不要只看
进程退出码。网络失败可能发生在写入之后，重试前先读真实平台状态。

Project 字段值超过 3000 字符会被截断并按截断值回读。不要把大型报告塞入字段，使用
HTTPS 证据链接。Project 字段与字段值查询支持单页前 100 项，配置应保持小于此上限；
超大 Project 结构须先人工核对。Issue 列表与 Project 条目分页读取，评论超过窗口则拒绝。
