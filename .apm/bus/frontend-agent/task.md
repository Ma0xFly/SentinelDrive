---
stage: 10
task: 2
agent: frontend-agent
log_path: ".apm/memory/stage-10/task-10-02.log.md"
has_dependencies: true
---

# Task 10.2 - 访客只读前端

## 背景

后端访客只读已完成并合并（Task 10.1，main @ `60289df`）：`GET /intelligence`（列表/详情）、`GET /stats/overview`、`GET /sources`（列表/详情）已可匿名访问，信源运维字段（config/错误/失败次数/sync_state/recent_jobs/时间戳）在未认证下被裁剪；写端点、导出、告警处置、用户端点仍要求认证。本任务在前端实现访客只读视图。

## 依赖上下文（来自 10.1，务必知晓）

- **后端已就绪**：匿名可读情报列表/详情、态势统计、信源公开字段。信源匿名响应是新的精简结构 `SourcePublicResponse`（仅 `id/name/source_type/status/enabled/base_url`），前端信源页需区分「匿名可见字段」与「认证可见运维字段」。
- **OpenAPI 锁标记与实际行为不一致**：`get_optional_current_user` 因复用 `HTTPBearer`，这些端点 OpenAPI 文档仍显示需 Bearer，但运行时匿名可访问。**前端不要被文档误导**，按「匿名可读」实现。
- 写端点未变：未登录调用 `POST /manual-entries`、`PATCH /alerts/*/status`、`PATCH /sources/*/status`、`POST /sources/pipeline/trigger`、导出端点、用户端点会 401。

## Workspace

- 从 `main` 创建功能分支 `feat/guest-readonly-frontend`
- 只提交本任务自身产出（`frontend/` 下代码/测试）；`.apm/`、`web3开发/`、`backend/`、`worker/` 不提交
- 不 push

## 实现要求

1. **公开页放行**：未登录可访问「态势总览」（/dashboard）、「威胁情报」（列表 /intelligence 与详情 /intelligence/:id）、「数据源」（/sources）。路由守卫 / `getInitialState` / `onPageChange` 需允许 `currentUser` 为空时进入这些页面，而非强制跳登录。其余页面（告警、手工录入、用户管理）保持登录才能访问。
2. **访客视图**：未登录进入公开页时，顶部或侧栏展示「访客模式」提示 + 「登录」入口；隐藏写操作与登录才有的功能：
   - 情报列表页：隐藏「手工录入」快捷入口与导出按钮（导出要求认证）
   - 情报详情页：隐藏导出按钮
   - 数据源页：隐藏启停、手动触发管道、任务日志查看等运维操作（这些后端仍会 401）
   - 告警 / 手工录入 / 用户管理菜单对访客不可见或不可达
3. **认证态不变**：登录用户的完整工作台行为与现在完全一致，不得回归。
4. **401 处理兼容**：现有「401 清凭证跳登录」逻辑保留，但公开页在无 token 时不应触发跳转（因为匿名请求本身 200）。确保 `request` 拦截器对匿名可读端点的 200 不误判为需要登录；对写端点的 401 仍走登录流程。
5. **访问态切换**：访客在公开页点「登录」登录成功后，应回到原页面（或仪表盘）并看到完整视图。

## 验证

- `cd frontend && pnpm build`、`pnpm lint`（biome + tsc）、`pnpm test` 全绿
- 补充前端聚焦测试：未登录可渲染情报/数据源/态势（mock 或组件测试）、写操作入口对访客隐藏、登录后显示完整操作
- 可复用既有 Playwright E2E（`frontend/e2e/`）或 vitest；不要依赖真实外部数据源
- 主检出 `backend/`、`worker/`、`docker-compose.yml` 零改动

## 明确排除

- 不改后端契约；不做新的写操作；不做多租户 RBAC；不引入 AI/工单/通知

## 报告要求

完成后写入 `.apm/memory/stage-10/task-10-02.log.md`（frontmatter：stage/task/title/agent/status/important_findings/compatibility_issues），并向 `.apm/bus/frontend-agent/report.md` 提交 Task Report（Summary / Details / Output / Validation / Issues）。合并与 worktree 清理由 Manager 负责，worker 不自行合并。