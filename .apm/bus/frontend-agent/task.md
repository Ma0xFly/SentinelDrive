---
stage: 9
task: 3
agent: frontend-agent
log_path: ".apm/memory/stage-09/task-09-03.log.md"
has_dependencies: true
---

# Task 9.3 - 核心页面迁移

## 背景

Task 9.1 已审查合并（main @ `903ea67`）：`frontend-pro/` 底座可用——8 域手写 TS 契约层（`src/services/`）、中文 ProLayout 布局壳、登录/token/401/路由守卫全链路、六个占位页。本任务在底座上按真实数据模型重建四个核心工作台页面。仪表盘页不在本任务范围（Task 9.4）。

## Workspace

- backend-agent 正在并行开发 Task 9.2（统计 API，改 `backend/`）。为避免共享检出冲突，本任务在 git worktree 中执行：
  - `git worktree add .apm/worktrees/frontend-pro-pages -b feat/frontend-pro-pages main`
  - 在 worktree 内开发与提交（需在 worktree 内重新 `pnpm install`）；`.apm/` 的日志与报告仍写主检出绝对路径 `/home/myx/Projects/SentinelDrive/.apm/...`
  - 不切主检出的分支、不动主检出的工作区
- 提交信息 `type: description`；只提交 `frontend-pro/` 下自身产出

## 依赖上下文（来自 9.1 Important Findings）

- 路由 name 用中文直接量（umi locale key 在 utoopack 下不生效）；页面文案直接写中文
- `pnpm dev` = 真实后端模式（MOCK=none，proxy → `localhost:8000`，可用 `BACKEND_PROXY_TARGET` 覆盖）；`pnpm start` = mock 模式
- `mock/auth.ts` 可参考扩展页面所需的契约 mock；请求 base path 为 `/api`
- `backend/.venv` 整个虚拟环境缺失（历史认知「缺 fastapi」不准确），真实联调前需重建

## 实现要求

1. **威胁情报列表**（ProTable）：对接 `src/services/intelligence`——搜索、后端支持的筛选参数（CVE、厂商、产品、组件、攻击面、风险等级、标签、来源、状态等，以 typings 为准）、排序、分页；风险等级/严重度/状态用徽章色；列表导出（CSV）入口；行进入详情。中文枚举标签沿用旧 `frontend/app/intelligence/labels.js` 的语义（值映射可对照源码）。
2. **情报详情**（ProDescriptions）：来源归因（来源名称、URL、外部编号、first_seen/last_seen）；领域字段（厂商/产品/车辆组件/攻击面）；风险分数、等级与评分解释因素；关联告警链接；导出动作（Markdown、PDF，对接 `src/services/exports`）；去重键、`external_ids` 与标签（含 `external_ingest`）展示；长文本换行。
3. **告警工作台**：列表（按状态/风险等级筛选）、详情、状态流转（允许的目标状态以 `src/services/alerts` typings 与后端契约为准）、状态变更带备注、中文成功/失败反馈。
4. **数据源管理**：列表（启用状态、最近同步时间、失败次数、最近错误）、任务日志查看、启用/停用、手动触发同步（运维控制面语义，对接 `src/services/sources`）；触发动作有确认与结果反馈。
5. **手工录入**（ProForm）：字段分组对齐旧 `frontend/app/manual-entry` 语义与 `src/services/manualEntries` schema（类型、标题、摘要、厂商/产品、组件、攻击面、来源等）；中文字段校验与错误提示；提交成功反馈。
6. **通用**：加载/错误/空状态全中文；复用 9.1 布局壳与组件，不重复造轮子；不修改 `src/services/` 契约层结构（发现契约缺口记录到报告 Issues，不要顺手改后端）。

## 真实联调（优先尝试）

1. 重建后端环境：`python3 -m venv backend/.venv`（建议建在 worktree 外的主检出或明确路径，避免污染提交）并按 `backend/` 的依赖声明安装（当前网络可用，9.1 已成功 clone 与 pnpm install；若 pip 源不可用再退回 mock 并记录）。
2. 数据库依赖：若 docker 可用，可仅启动 postgres/redis 服务（运行 `docker compose up -d postgres redis` 允许；不得修改 `docker-compose.yml`）；执行迁移与管理员 bootstrap 后以 `pnpm dev` 走真实登录与页面流程。
3. 环境确实无法起真实后端时，扩展契约 mock 完成走查，并在日志中如实记录限制。

## 明确排除

- 不做仪表盘/统计页（Task 9.4，等 9.2 合并）；不删旧 `frontend/`；不改 `docker-compose.yml`
- 不修改 backend/worker 代码；不做 AI 对话、OKR、IOC/车辆资产等模板示例实体
- 不提交真实密钥

## 验收清单

- [ ] 四个页面对接真实后端（或如实记录的 mock）完成核心流程
- [ ] 中文枚举标签与旧版语义一致；无英文残留、无占位页残留（dashboard 占位保留）
- [ ] `pnpm build`、`pnpm lint`、`pnpm test` 全绿
- [ ] 旧 `frontend/`、`docker-compose.yml`、`backend/` 零改动
- [ ] 任务日志与报告按 APM 规范写入

## 报告要求

完成后写入 `/home/myx/Projects/SentinelDrive/.apm/memory/stage-09/task-09-03.log.md`（frontmatter：stage/task/title/agent/status/important_findings/compatibility_issues），并向 `/home/myx/Projects/SentinelDrive/.apm/bus/frontend-agent/report.md` 提交 Task Report（Summary / Details / Output / Validation / Issues）。合并与 worktree 清理由 Manager 负责，worker 不自行合并。
