---
title: SentinelDrive
---

# APM 任务追踪器

## 任务追踪

**Stage 1：** 已完成

**Stage 2：** 已完成

**Stage 3：** 已完成

**Stage 4：** 已完成

**Stage 5：** 已完成

**Stage 6：** 已完成

**Stage 7：** 已完成

**Stage 8：** 已完成

**Stage 9：** 进行中

## Stage 9 任务追踪

| 任务 | 名称 | Agent | 状态 | 任务日志 |
| --- | --- | --- | --- | --- |
| 9.1 | Pro v6 前端底座搭建 | frontend-agent | Done（已合并 903ea67） | `.apm/memory/stage-09/task-09-01.log.md` |
| 9.2 | 威胁统计聚合 API | backend-agent | Done（已合并 de21098） | `.apm/memory/stage-09/task-09-02.log.md` |
| 9.3 | 核心页面迁移 | frontend-agent | Done（已合并 bfbbc81） | `.apm/memory/stage-09/task-09-03.log.md` |
| 9.4 | 威胁态势仪表盘 | frontend-agent | Active · `feat/frontend-pro-dashboard`（worktree） | `.apm/memory/stage-09/task-09-04.log.md` |
| 9.5 | E2E 移植、部署切换与文档 | qa-documentation-agent | Pending | `.apm/memory/stage-09/task-09-05.log.md` |

## Worker 追踪

| Agent | Instance | 备注 |
|-------|----------|------|
| platform-agent | 1 | |
| backend-agent | 1 | |
| intelligence-pipeline-agent | 1 | |
| frontend-agent | 1 | |
| qa-documentation-agent | 1 | |

## 版本控制

| Repository | Base Branch | Branch Convention | Commit Convention |
|-----------|-------------|-------------------|-------------------|
| SentinelDrive | main | `type/short-description` | `type: description`，允许 `feat`、`fix`、`refactor`、`docs`、`test`、`chore` |

## 工作备注

- Stage 9 范围决策（2026-09-06 与用户确认）：前端整体迁移到 Ant Design Pro v6（React 19 + Umi Max 4 + antd 6 + Tailwind v4 + utoopack + pnpm/Node 22）；“OKR 图表”确认为威胁态势统计仪表盘（非 OKR 管理模块）；AI 助手（antd-X）本期不做；多语言先仅中文。
- 新前端暂放 `frontend-pro/`，旧 `frontend/` 在 Task 9.5 才删除归位；9.1/9.3/9.4 不得修改 `docker-compose.yml` 与旧前端。
- 页面必须基于真实数据模型（threat_intelligence/sources/alerts/手工录入），禁止照搬 Pro 模板的 IOC、车辆资产、STIX2 示例实体。
- 9.1 发现：`backend/.venv` 整个虚拟环境缺失（非仅缺 fastapi/httpx）。→ 9.2 已在主检出重建（按 requirements.txt 钉定版本补装，测试 84 passed），此问题已解决。
- Pro v6 菜单 locale key 在 utoopack 构建链下不生效：路由 name 直接写中文，页面文案直接中文；formatMessage 链路未验证。
- 前端脚本语义：`pnpm dev`=真实后端（MOCK=none + proxy），`pnpm start`=mock；pnpm 11 需 `pnpm approve-builds --all`（已记入 pnpm-workspace.yaml）。
- 9.5 部署切换注意：新前端 base path `/`，`/api` 经 Caddy `handle_path` 转发，与现有反代语义一致；`frontend-pro/tsconfig.json` 已改 `declaration: false`（TS 7 noEmit 下 TS2883）。
- 9.2 发现的既有缺陷（待 9.5 一并修复）：`backend/tests/test_migrations.py` 用相对路径读迁移文件，从仓库根运行必失败、从 `backend/` 运行才通过；`httpx` 是测试直接依赖但未列入 `backend/requirements.txt`。
- `/stats/overview` 消费语义（供 9.4 仪表盘）：分布键按枚举全量补零（响应结构稳定）；趋势固定 30 条、最旧→最新、date 序列化为字符串；来源 Top 10 含禁用来源，按去重关联情报数排序、平局按名称升序。
- 真实联调环境已就绪可复用（9.3 建立并保持运行）：postgres/redis/backend 容器、`backend/.venv`（主检出）、管理员 `admin@example.test`（compose 默认开发占位密码）。9.4/9.5 直接复用，不得 down/restart。
- 后端契约缺口（9.3 记录，未修）：`GET /manual-entries` 无分页与筛选参数（前端暂做客户端筛选），数据量增长需补；ingest 的 `components`/`attack_surfaces` 列表字段与详情单值字段无自动推导。留作后续小任务候选。
- 登录后偶发落在 `/dashboard` 而非 redirect 目标（9.3 观察一次、无法复现）：疑似整页跳转与 initialState 恢复竞态，影响低；若频发改 `history.push` 并等 initialState 就绪。
