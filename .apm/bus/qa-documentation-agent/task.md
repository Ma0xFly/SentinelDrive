---
stage: 9
task: 5
agent: qa-documentation-agent
log_path: ".apm/memory/stage-09/task-09-05.log.md"
has_dependencies: true
---

# Task 9.5 - E2E 移植、部署切换与文档

## 背景

Stage 9 前四个任务已全部合并（main @ `22a8d9b`）：`frontend-pro/` 是完整的 Ant Design Pro v6 前端（登录/布局壳 + 情报列表详情/告警/数据源/手工录入四页面 + 威胁态势仪表盘），旧 Next.js `frontend/` 仍在原地、`docker-compose.yml` 仍指向旧前端。本任务是 Stage 9 收尾：E2E 移植、部署切换、删旧前端、文档同步，并修复两个已知测试缺陷。

## Workspace

- 本任务无并行 worker，直接在主检出从 `main` 创建分支 `chore/frontend-pro-cutover` 开发
- 提交信息 `type: description`；不提交 `.apm/`、`web3开发/`；不 push

## 任务一：E2E 移植与新增

1. 旧 E2E 在 `frontend/e2e/operator-workflows.spec.js`（6 个场景，Playwright + mock `/api/*` 路由拦截，配置 `frontend/playwright.config.js`，webServer 启 next dev）。将 6 个场景语义移植到新前端（目录随改名后为 `frontend/e2e/`）：
   - 登录流转与守卫、情报列表/详情渲染、桌面布局无溢出断言、external_ingest 记录展示、告警流转、手工录入（以旧 spec 的实际断言为准）
   - mock 拦截沿用 `page.route` 对 `/api/*` 的约定；新前端 SPA 路由（如 `/intelligence/:id`）与登录页 URL 已不同于旧版，断言按新路由适配，但**业务语义不得缩水**
2. 新增仪表盘场景：mock `/api/stats/overview` 返回含非零数据的确定性响应，断言四张统计卡片数值、趋势/分布图表渲染（DOM 存在性即可，不截图比对像素）与空态（可选第二组零值断言）
3. webServer 命令改为启动新前端 dev server（`pnpm dev`，mock=none；E2E 的 `page.route` 拦截在浏览器侧生效，proxy 不影响拦截，但 webServer 端口与 baseURL 需按新前端实际端口配置，并用 `BACKEND_PROXY_TARGET` 指向不会响应的地址以证明 mock 隔离）
4. `@playwright/test`、`playwright.config`、npm scripts（`e2e`）在新前端的 package.json 配好；运行 `pnpm e2e` 全绿（需 `npx playwright install chromium`）

## 任务二：部署切换与旧前端移除

1. 新建 `frontend-pro/Dockerfile`（改名前路径）：多阶段构建——pnpm install + build（node:22）→ 静态托管阶段。托管方式优先 nginx 托管 `dist/` 静态文件 + SPA 路由回退 `try_files ... /index.html`（省内存，适配 4GB 目标机）；若模板产物结构不适合静态托管可改用模板 Node server，需在日志说明理由
2. `docker-compose.yml` frontend 服务：build context 改为新前端目录，端口/健康检查/资源限制保持既有保守风格；Caddy 反代已有 `FRONTEND_UPSTREAM` 环境变量，若新前端仍监听 3000 则零改动，否则同步调整
3. **重建 backend 容器镜像**（当前镜像为 9.2 合并前构建、缺 stats 端点）：`docker compose build backend`，使 `/api/stats/overview` 在容器栈可用
4. 目录归位：删除旧前端（`git rm -r frontend` 或等价方式，确保完整移除）；`git mv frontend-pro frontend`；全仓清理残留引用（已知命中：`AGENTS.md`、`docs/glossary.md`、`docs/testing.md`、`docs/qa/coverage-pass-summary.md`，另查 Makefile/脚本）
5. 验证：`docker compose config` 通过；`docker compose up -d --build` 后经反代访问新前端可登录、仪表盘有数据（库内已有 9.3/9.4 的测试数据）；`curl` 容器栈的 `/api/stats/overview`（带 token）返回 200
6. 环境注意：本机 `*:8000` 有一个非本项目的 uvicorn 进程（pid 2506），**不触碰**；容器栈当前运行中（postgres/redis/backend），E2E 用 mock 不依赖真实后端，但 compose 验证会重建 frontend/backend 容器——允许，postgres 数据卷不动

## 任务三：两个已知测试缺陷修复

1. `backend/tests/test_migrations.py`：相对路径 `Path("migrations/versions/...")` 从仓库根运行必失败——改为基于 `__file__` 的路径解析，使其从任意 cwd 可运行
2. `backend/requirements.txt`：补入 `httpx`（测试直接依赖，缺失导致新环境缺装）；若有 requirements 分层则按既有模式放
3. 修复后在 `backend/` 目录与仓库根各跑一次 pytest 确认两者均通过

## 任务四：文档同步

1. `README.md` 与 `docs/testing.md`：前端命令从 `npm run`（Next.js）更新为 `pnpm`（新前端），E2E 运行方式、目录名、测试清单更新；文档索引若有指向旧前端结构的条目同步修正
2. 部署文档（`docs/` 下相关文件）：frontend 服务构建方式变更说明（Next standalone → 静态托管）、镜像重建要求
3. 不虚构命令：所有写入文档的命令必须实际运行验证过

## 明确排除

- 不改业务代码（`frontend*/src` 页面逻辑、`backend/app`、`worker/` 均不动，测试缺陷修复除外）
- 不做性能调优、监控、CI 管道等新能力
- 不提交真实密钥；备份产物不入库

## 验收清单

- [ ] `pnpm e2e` 新前端全绿（≥7 场景：移植 6 + 仪表盘 1）
- [ ] `docker compose config` 通过；up --build 后反代可访问、登录可用、仪表盘有数据
- [ ] 旧 `frontend/` 彻底移除，`frontend-pro` 归位为 `frontend`，全仓无残留引用
- [ ] 两个测试缺陷修复且双 cwd 验证通过；backend 容器含 stats 端点
- [ ] 文档命令全部实际验证；无占位章节
- [ ] 任务日志与报告按 APM 规范写入

## 报告要求

完成后写入 `/home/myx/Projects/SentinelDrive/.apm/memory/stage-09/task-09-05.log.md`（frontmatter：stage/task/title/agent/status/important_findings/compatibility_issues），并向 `/home/myx/Projects/SentinelDrive/.apm/bus/qa-documentation-agent/report.md` 提交 Task Report（Summary / Details / Output / Validation / Issues）。合并由 Manager 负责。
