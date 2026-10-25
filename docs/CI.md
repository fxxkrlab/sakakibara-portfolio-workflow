# CI 接入与清理

本工具只用标准库。采用者应在自己指定的隔离 Linux CI 环境执行单测、离线演示和
公开检查。当前 workflow 仅 `workflow_dispatch`，没有 pull_request、push 或定时触发；
默认变量开关关闭，不会为任意 fork/PR 提供有权限的自托管执行环境。

启用前由仓库管理员完成：

1. 核验 Actions 可用，本仓库专属 Runner 已注册且 online，标签包含 self-hosted、
   Linux、X64、portfolio-ci、portfolio-container。标签本身不证明隔离，需核对真实环境。
2. Runner 使用独立非 root 用户、独立 rootless Docker daemon 与 DockerRootDir；
   不挂宿主生产 socket，不允许访问生产数据库或其他项目资源。此验证 job 不使用 Docker。
3. 公开仓库应使用一次性、无私网/生产权限的 Runner。配置 `workflow-validation` 环境
   和 required reviewers，审核准确 ref/SHA 后执行。不要给陌生代码授权 self-hosted job。
4. 设置仓库变量 `PORTFOLIO_CI_ENABLED=true`；保护 workflow 和环境配置，限制维护权限。
5. 使用一次性 work 目录。依赖、产物、缓存、临时文件和登录资料都在该目录；成功、
   失败、取消或中断均由 Runner started/completed/recovery hooks 回收。不要跨 job 复用
   产品代码或构建缓存。此仓不需要 registry 登录，不默认上传任何镜像。
6. 按现场真实 daemon 与路径编写最小权限清理 hooks；不能把其他组织的路径/主机复制
   为默认，也不能对宿主 Docker 全局 prune。只保留 Runner 基础程序/镜像与最小日志。

手动触发后，记录准确 source SHA、run/job URL、测试数量、失败/跳过、清理证明；
读取 Actions 最终结论。`always()` 步骤不能单独保证进程中断后的清理，必须由外层
Runner recovery 补足。这里不提供可直接部署到任意服务器的危险清理脚本。

如产品另需 GHCR，把它作为独立授权和 job：最小 `packages:write`，一次性登录目录，
完整源码标签，上传后回读 manifest/digest 与 revision，再清理本 job 资源。构建产物
发布不授权正式版本发布或生产部署。

没有 Runner 或审批环境时记录 CI=NOT_RUN，并交付静态证据与候选，不能把其他仓库
的测试结果移用到本候选。适用的真实数据库/客户端测试按原 Issue 环境执行。
