# 公开发布前的脱敏检查

公开副本使用 allowlist 文件迁移，保留协调器与测试的通用行为；配置、文档与 CI 引导
重新整理为可配置模板。没有复制任何私有 Git 历史。目标仓库原有 GPL LICENSE 和其
初始公开提交保留。固定来源对应关系和差异审计应保存在私有发布记录，不能反向泄漏来源。

## 本次通用化范围

| 来源内容类型 | 公开处理 |
| --- | --- |
| 协调器与完整测试 | 保留；替换组织/团队样例，接受通用 Linear identifier |
| 真实仓库登记 | 全部删除，改为 example-org 两个虚构仓库；默认禁止联网 |
| 私有 Issue/PR/Project/UUID/源 SHA/产物 digest | 不公开，示例只用明确虚构值 |
| 运维、全局 AI 规则 | 保留行为规则，重写具体主机/路径/账号/工单/调度上下文 |
| CI workflow | 改为默认关闭的手动验证模板，清理与隔离规则改为使用者自己的配置 |
| 运行数据、安装回执、调度、日志、Git 对象 | 不复制；本地私有配置与运行目录忽略 |

额外通用行为：支持 phase_mapping、配置显式启用、源评论窗口超限拒绝自动处理，
忽略无回执权限的评论，避免外部评论者阻断合法负责人的进度；可信作者冲突仍拒绝。
原生同步、部署、服务器、账号和定时执行均不被宣称已经配置。

## 检查步骤

1. 只迁移明确文件，逐文件人工读取，包括隐藏文件、文档链接、注释、测试、示例、
   workflow、文件名和可执行脚本。不要整目录复制后仅做 token 替换。
2. 删除真实账号/邮箱/本机目录、服务器 IP/域名/端口、私有仓库和工单、workspace/
   team/project/node ID、源 SHA、镜像 digest、业务数据、安装/运行回执及 credential。
   公开认可的版权和目标公开仓库 URL 可以保留。
3. 使用公开检查脚本：

   ```bash
   python3 scripts/check_publication.py --history
   # 私有发布者在仓库外保存禁止出现的原组织信息，每行一个，再执行：
   python3 scripts/check_publication.py --history --deny-file /secure/path/deny-terms.txt
   ```

4. deny-file 不提交、不打印内容。脚本只输出规则与路径，不回显命中原文。它检查常见
   token/私钥、主机地址、用户目录、私有 Linear/Project 标识等，并在 --history 下检查
   所有 refs 可达 commit、commit 元数据与 blob。它不是通用秘密检测器，人工复查必需。
5. 复查 staged diff、git status、远端 refs、当前树和完整可达历史。确认没有子模块、
   LFS/大二进制、附件、runtime 导出或私有 remote 被带入。公开 commit 使用公开身份。
6. 推送前记录文件 SHA256 与检查结论；推送后回读目标 commit/tree/文件与 PR，确认
   服务端与本地一致。仅上传经过检查的 ref，不 mirror、不要 push --all 或复制私有 tags。

后续每次发布都重复这些检查，包括新增文件、PR 正文和 CI 输出。脱敏结论仅覆盖已检查
的明确候选内容，不能保证任意后续提交或平台外附件安全。若发现真实秘密，不在公开
Issue 粘贴；停止公开并按 SECURITY.md 私下处理。
