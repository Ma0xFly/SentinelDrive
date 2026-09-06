---
stage: 9
task: 1
agent: frontend-agent
log_path: ".apm/memory/stage-09/task-09-01.log.md"
has_dependencies: false
---

# Task 9.1 - Pro v6 前端底座搭建

## 背景

Manager 决策（2026-09-06 与用户确认）：前端整体从手写样式 Next.js 迁移到 Ant Design Pro v6 底座（React 19 + Umi Max 4 + antd 6 + Tailwind CSS v4 + antd-style + Biome，构建工具 utoopack，已核实 v6 正式发布）。本期为 Stage 9，共 5 个任务：9.1 底座（本任务）→ 9.3 核心页面迁移 → 9.4 威胁态势仪表盘 → 9.5 E2E 移植与部署切换；9.2 统计聚合 API 由 Backend Agent 并行开发。

范围口径：用户所说「OKR 图表」已确认为**威胁态势统计仪表盘**，不是 OKR 目标管理模块；AI 助手（@ant-design/x）本期明确不做；多语言先仅中文。

## Workspace

- 从 `main` 创建功能分支：`feat/frontend-pro-scaffold`
- 新前端初始化在 `frontend-pro/` 目录；旧 `frontend/` 保持完全不动（由 Task 9.5 移除归位）
- 只提交本任务自身产出；`.apm/`、`web3开发/` 等无关路径不得提交

## 目标

搭建可构建、可登录、带中文运营布局壳的 Pro v6 应用底座，为 9.3/9.4 的页面实现做好契约与骨架准备。

## 实现要求

1. **环境与脚手架**：Node 22 LTS + pnpm 11（可用 `corepack enable && corepack prepare pnpm@11 --activate`）。用官方 Ant Design Pro v6 模板初始化（`pnpm create umi@latest` 选 ant-design-pro 模板，或等价方式），随后裁剪：删除模板 demo 页面、示例图表页、无用 mock 演示；i18n 仅保留 zh-CN。
2. **API 契约接入**：优先配置 `openAPI` 插件从 FastAPI schema 生成服务层（schema 可不起服务导出：`.venv/bin/python -c "from app.main import app; import json; print(json.dumps(app.openapi(), ensure_ascii=False))" > openapi.json`，注意仓库 `.venv` 当前缺 fastapi，安装失败属已知环境限制）。若自动生成不可行，允许基于 `backend/app/api/routes/` 与 `backend/app/api/schemas/` 源码手写等价 TypeScript 类型层与请求函数，目录结构对齐 openapi 插件产物（typings + services），便于将来切换为自动生成。在任务日志中记录实际采用方式。
3. **端点事实**（避免臆造）：后端路由为 `/auth`、`/users`、`/alerts`、`/manual-entries`、`/intelligence`、`/sources`、`/exports`、`/health`，后端本身**无全局 `/api` 前缀**，`/api` 由反向代理注入。登录为 `POST /auth/login`（经反代即 `/api/auth/login`）。请求 base path 以现有 `docker-compose.yml` 反代配置语义为准，但**本任务不得修改 `docker-compose.yml`**。
4. **布局壳**：ProLayout 中文布局，安全运营工作台风格——信息密度适合扫描、视觉克制、任务导向，不做营销化设计。导航：态势总览（仪表盘，9.4 实现）、威胁情报、告警、数据源、手工录入、用户管理。主题 token 用克制配色（antd 6 cssVar 模式），并设置默认亮色主题。
5. **认证对接**：登录页对接 `POST /auth/login`；token 持久化 + 全局请求拦截附加鉴权头 + 401 统一处理（清凭证跳登录）；`access.ts` 或等价路由守卫拦截未登录访问。本机起真实后端需要 PostgreSQL，若环境不便，允许先用模板 mock 或本地 mock 验证登录流转，并在日志中如实说明（9.3 会做真实联调）。
6. **路由占位**：五个业务页面建中文标题 + 明确标注「Task 9.3/9.4 实现」的空态占位，不放假数据。
7. **版本控制**：提交信息 `type: description`（如 `feat: 搭建 Pro v6 前端底座与认证布局壳`）；只提交 `frontend-pro/` 下自身产出。

## 明确排除

- 不删除或修改旧 `frontend/`；不修改 `docker-compose.yml` 与任何后端/worker 代码
- 不引入 @ant-design/x、AI 对话、OKR 实体、IOC/车辆资产/STIX2 等模板示例实体
- 不提交真实密钥；模板自带密钥类示例必须清除或替换为安全占位
- 不做英文语言包与语言切换 UI（保留 i18n 框架能力即可）

## 验收清单

- [ ] `pnpm build` 成功；`pnpm dev` 可启动
- [ ] 登录流程可用（真实后端或 mock，如实记录）
- [ ] 未登录访问受保护路由跳转登录页；401 有统一处理
- [ ] 界面全中文、无模板 demo 残留、无营销化内容
- [ ] 旧 `frontend/` 与 `docker-compose.yml` 零改动
- [ ] 任务日志与报告按 APM 规范写入

## 报告要求

完成后写入任务日志 `.apm/memory/stage-09/task-09-01.log.md`（frontmatter：stage/task/title/agent/status/important_findings/compatibility_issues），并向 `.apm/bus/frontend-agent/report.md` 提交 Task Report（Summary / Details / Output / Validation / Issues）。
