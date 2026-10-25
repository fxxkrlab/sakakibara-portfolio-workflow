# 即时回写、定时对账与撤回

## 配置前

完成 ONBOARDING.md，核验实际工具文件、固定源码 SHA、已完成的 CI 证据；不要运行
未知下载的脚本。首次采用者没有既有安装回执时先建立自己的验证记录。记录仓库/版本、
运行目录、唯一协调负责人、配置文件哈希和权限范围。真实配置、Linear 导出、计划及
回执存受控本地目录（runtime/、outbox/ 已 gitignore），不入公开仓库。

## 当前任务即时回写

1. 核对 GitHub 源 Issue 完整正文、准确 Linear attachment/UUID 与 Project 条目。
2. 按当前全 Issue 范围生成结构化回执，绑定正文 hash、完整 SHA、阶段、证据和下一步。
   只完成叶实现时发普通事实说明，不冒充全范围回执。
3. 取单一 Linear 任务的完整归一化对象，保存 runtime/linear-issue.json，执行：

   ```bash
   python3 portfolio_sync.py emit --receipt runtime/receipt.json \
     --linear runtime/linear-issue.json
   ```

4. emit 按 event_id 查重，成功后回读源评论。native 仓库检查评论是否真实进入同步线程；
   未配置评论同步时，只在已有 linked 任务写一条指向源评论的回执，不创建重复任务。
5. 对准确范围 snapshot/plan，审查 Project operations 和 linear_operations，再执行
   授权的 Project apply。即时维护 PR 元数据、优先级、类型与看板 PR 条目。
6. 对每条 linear_operations，再用连接工具 get_issue 核对 UUID、状态和 updatedAt。
   相同才单字段更新 state，随后 get_issue 回读。不得覆盖 description、验收清单或依赖。
   changed/conflict 留待重读和重新计划。accepted 操作不发起 Done，只确认既有完成。

CLI 默认 snapshot 覆盖全部已登记仓库。做即时更新可使用从私有 registry 复制的任务专用
最小配置（只保留本次明确仓库），避免误维护无关任务；仍须审查所有输出 operations。
Issue 和 PR 分别加入 Project，PR 链接从明确源关系读取，不凭相似标题推断。

## 定时对账（可选，默认未安装）

建议每 15 分钟由唯一协调会话唤醒；也可用团队自己的调度器。它依赖运行主机在线、
AI/连接器登录和网络。这里不提供平台 token 服务，不会自动创建调度。给调度器的提示：

> 只处理明确登记的仓库，先核验运行目录和源版本。完整读取 Linear 候选与准确源关联，
> snapshot 后 plan，处理 attention。apply 前刷新两平台数据，有变化停止该项并重计划。
> 只维护跟踪字段并回读，不改验收或依赖、不发起关闭或 Done。无变化不写评论、不通知；
> 只有有意义的完成、失败、权限缺口、阻塞或需要用户操作才通知。保留真实错误与未执行项。

外层调度器需覆盖整个读取/计划/写入周期的唯一运行锁，不能仅依赖 CLI 的 apply/emit
锁。若占用则跳过本轮并保存待处理事件。跨主机需集中写入者；`fcntl` 不是分布式锁。

## 冲突与故障

- 权限失败、空响应、分页不全、超时或解析失败：停止依赖它的写入，保留脱敏错误。
- 缺失镜像：native 先等待复查，linked 按精确源链接查重后建唯一关联任务。
- 多个镜像、较新人工评论、正文变更：负责人重新确认范围，生成当前完整回执。
- 结果 readback mismatch：读取实际平台状态，报告已写入/未知/未写入，不盲目重放。
- GitHub 与 Linear/Project 不是原子 CAS；即使预检查通过仍可能邻接人工修改，回读失败
  时不得宣称同步成功。保留人工更新，不以旧快照回滚它。
- Draft PR 保持开发；CI 通过、合并、部署、启用和实际验收分开记录。父工单不能被叶
  回执或协调器的一次局部成功提前推进。

## 撤回与升级

暂停使用者自行创建的调度；撤回新增进度同步 AGENTS 区块，保留原开发/CI 规则、源
工单和历史证据。不要删除真实产品状态。代码升级先独立分支比较配置兼容性与门禁，
固定最终 SHA，跑指定环境测试，记录新文件 hash；成功后再更新本地运行副本。
公开升级只带 allowlist 代码/文档，不复制 runtime、账号数据或私有 Git 历史。
