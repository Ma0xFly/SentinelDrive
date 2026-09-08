---
stage: 10
task: 4
agent: qa-documentation-agent
log_path: ".apm/memory/stage-10/task-10-04.log.md"
has_dependencies: true
---

# Task 10.4 - 配置与文档同步

## 背景

Stage 10 前三任务已合并（main @ `d1e6c53`）：10.1 访客只读后端、10.2 访客只读前端、10.3 垂直信源扩展（NHTSA + vendor 端点）。本任务收尾：补齐配置、同步文档、新增访客浏览 E2E，并做 Stage 10 QA 总结。

## 已存在的事实（勿重复，先核实再动）

- 10.3 已改 `docs/connectors.md`、`docs/environment.md`、`docs/source-configuration.md`（记录 NHTSA connector、`SOURCE_ENABLED_NHTSA_RECALLS`、新增 Vector Informatik/Wind River/Geely/Xiaomi 端点）。**但这些 docs 的改动不完整**：
  - `.env.example` **仍缺 `SOURCE_ENABLED_NHTSA_RECALLS=false`**（实测 grep 确认缺失；`SOURCE_ENABLED_VENDOR_ADVISORIES=false` 已有）——必须补。
- 访客只读行为（10.1/10.2）：未登录可匿名读情报列表/详情、`/stats/overview`、数据源公开字段；写操作、导出、告警处置、用户管理、信源运维字段保持登录。前端公开页 = 态势总览/威胁情报（列表+详情）/数据源；访客菜单 3 项、登录菜单 6 项；「访客模式」提示 + 登录按钮，登录后回跳原页。

## Workspace

- 从 `main` 创建分支 `docs/stage10-docs`（或 `chore/stage10-docs`，符合 `type: description`）
- 只提交本任务自身产出（`.env.example`、`README.md`、`docs/*`、`frontend/e2e/*`、`frontend/playwright.config.ts` 如需要）；`.apm/`、`web3开发/` 不提交；不 push

## 实现要求

1. **`.env.example`**：补 `SOURCE_ENABLED_NHTSA_RECALLS=false`（与 vendor-advisories 同样的默认关闭策略），按环境变量组位置插入并在注释中说明用途；确认 `SOURCE_ENABLED_VENDOR_ADVISORIES` 注释说明准确。
2. **`README.md` 同步**：
   - 「功能特性」补访客只读（未登录可浏览情报/数据源/态势，写操作需登录）。
   - 「使用指南」补访客模式说明（公开页、访客提示、登录入口）。
   - 「内置信源」表补 NHTSA 召回（默认关）与厂商公告新增端点说明，或注明见 source-configuration.md。
   - 保持命令、服务名与实现一致。
3. **`docs/testing.md` / `docs/development.md`（如涉及）**：补访客只读的验证说明与 E2E 运行方式（新增访客场景）。
4. **访客浏览 E2E 场景**（`frontend/e2e/operator-workflows.spec.ts` 追加）：
   - mock `/api/*`，覆盖：未登录访问情报列表/详情与数据源页可渲染；访客菜单仅公开 3 项；写操作入口（导出/手工录入/数据源启停）对访客隐藏；访客访问受保护页（如 `/alerts`）跳登录并携带 redirect。
   - 沿用既有 mock 约定与 `isPublicPath` 语义；不依赖真实外部数据源；保持测试小而稳。
   - 运行 `cd frontend && pnpm e2e` 全绿。
5. **QA 总结**：在任务日志记录验证结果、文档链接校验、残余风险（如 NHTSA 未真实联网验证、公开端点 OpenAPI 锁标记差异、数据源匿名字段渲染为「-」）。

## 明确排除

- 不改业务代码（`backend/app`、`worker/sentineldrive_worker/connectors`、`frontend/src` 页面逻辑均不动；E2E 断言除外）
- 不 push；不引入新的公共/外部行为

## 验收清单

- [ ] `.env.example` 含 `SOURCE_ENABLED_NHTSA_RECALLS=false`，变量注释准确
- [ ] README 反映访客只读与新增信源，命令/服务名准确
- [ ] 访客浏览 E2E 场景通过，`pnpm e2e` 全绿
- [ ] 文档链接校验无损坏；无占位章节
- [ ] 任务日志记录 QA 结果与残余风险

## 报告要求

完成后写入 `.apm/memory/stage-10/task-10-04.log.md`（frontmatter：stage/task/title/agent/status/important_findings/compatibility_issues），并向 `.apm/bus/qa-documentation-agent/report.md` 提交 Task Report（Summary / Details / Output / Validation / Issues）。合并由 Manager 负责。