---
title: SentinelDrive
---

# APM 记忆索引

## 记忆要点

- 后端 readiness 使用 `/ready`，内部执行轻量 PostgreSQL 和 Redis 探测；`/health` 仅表示进程存活。
- 后端会在内部把 `postgresql+psycopg://` 规范化为 `psycopg.connect` 可直接使用的连接串，用于 readiness 检查；公开的 `DATABASE_URL` 值仍保留给后续 SQLAlchemy 风格使用。
- 前端验证使用 `npm run check`，该命令映射到 `next build`；前端依赖已调整为 Next 15.5.18、React 18.2.0，并使用局部 PostCSS override，确保 install 和 audit 可通过。
- Worker 脚本支持可选的 `CELERY_LOG_LEVEL` 和 `CELERY_WORKER_CONCURRENCY`；这些属于脚本级选项，但尚未列入 `.env.example`。
- 核心持久化使用 SQLAlchemy 2.x 和 Alembic。MVP `IntelligenceType` 值为 `vulnerability`、`exposure`、`incident` 和 `advisory`；未经明确范围批准，不要重新引入更宽泛的通用威胁类型。
- 认证使用无状态 HMAC 签名 bearer token，TTL 为 8 小时。Logout 会记录审计事件，但不会撤销 token；token 签名依赖 `APP_SECRET_KEY`。
- PostgreSQL `audit_action` enum 需要先应用迁移 `20260519_0002_add_auth_audit_actions.py`，才能存储 login/logout 审计事件。
- Connector 运行时契约位于 `worker/sentineldrive_worker/connectors/`，并从 `worker/app/connectors/` 重新导出；当前运行时包含 sample no-op Connector 和骨架执行路径。
- 数据源状态和任务日志消费者必须考虑 skipped connector run 会作为成功 `job_logs` 存储，并在 `metadata.run_status = "skipped"` 中记录跳过状态；除非有迁移显式扩展 `job_status`，重试细节也保留在 job metadata 中。
- Stage 3 的数据源 Connector 和规范化由 worker 负责：collection、raw persistence、normalization、deduplication 和 source attribution 位于 `worker/sentineldrive_worker/`；后端人工录入通过认证 API 直接创建 normalized records。
- 后端迁移测试对工作目录敏感：从 `backend/` 目录运行 `../.venv/bin/python -m pytest tests -q` 或使用容器命令形态，因为迁移测试会按 backend 目录相对路径读取迁移文件。
- 前端集成应以后端认证路由为事实来源：Stage 4 后 `main` 上可用的路由包括 `/auth/login`、`/auth/me`、`/auth/logout`、`/intelligence`、`/alerts`、`/sources`、`/manual-entries`、`/users` 和 `/exports/*`；前端应保持中文 UI 文案，并避免暴露后端内部信息或敏感响应字段。
- 前端下载必须使用共享认证下载 helper，不要直接使用裸导出 URL，因为导出端点要求 bearer token。
- Docker Compose 真实数据源采集要求 `worker` 和 `scheduler` 同时连接 internal network 与出站 `egress` network；PostgreSQL 和 Redis 仍保持内部-only。
- NVD CVE API 请求必须保证 `lastModStartDate` 到 `lastModEndDate` 的窗口不超过连续 120 天；worker 默认首轮同步窗口已改为 120 天。
- 运维文档有意区分 collection、normalization、scoring 和 backend alert evaluation。`make sync-once` 只运行 collection；后续处理需要 worker/Celery task 或 backend alert evaluation。
- 宿主机侧 PostgreSQL dump 记录在 `backups/postgres/` 下，`backups/` 已被 ignore，避免误提交备份产物。
- 定时 worker 管道使用 `sentineldrive.process_pipeline` 执行 collection、raw persistence、normalization 和 scoring。Alert evaluation 按设计仍在 backend 侧；后端 operations API 只能入队已批准的 worker pipeline task，不能暴露任意 Celery 控制、shell 执行、broker URL 或内部服务细节。
- 前端浏览器工作流覆盖使用 Playwright，配合确定性的 mock `/api/*` 响应和 localhost `NO_PROXY` 处理。它验证 UI 行为和端点装配，但不能替代 reverse-proxy、backend、PostgreSQL、Redis、worker、scheduler 或真实数据源集成的 live Compose 验证。

- 外部/AI 情报 ingest（后端 `POST /intelligence/ingest`）会内联规范化并写入 raw 行（`source_type="api"`、`processing_status="normalized"`、`entry_origin="external_ingest"`），worker 的 pending 查询默认不处理它们。去重键优先级为 `cve → external(dedup_key/external_id) → content → url → text`，worker 新增 `ExternalIngestNormalizer`（按 `entry_origin` 解析）已逐字对齐。但后端 raw 元数据不保留 cve_id/external_id/dedup_key/severity/affected_vendor/external_score（external_id 列折叠 external_id/dedup_key/cve_id，content_hash 混入派生值），未来若新增把外部/AI 情报写成 pending raw 的 connector，需在 metadata 显式写入这些字段才能完全对齐。
- 仓库同时存在 `worker/app` 与 `backend/app` 两个同名 `app` 包；涉及跨包的导入/测试依赖 pytest 的 `pythonpath = backend worker` 顺序（backend 在前），调整顺序会引入歧义。
- worker 外部 ingest 去重键对 CVE 做 `.upper()`（`cve:{id.upper()}`），而后端 ingest 使用原样大小写（`cve:{payload.cve_id}`）；规范大写输入下收敛，但若外部写入方提交小写 CVE 会分叉，需由后端 ingest 侧规范化大小写（属 8.2 范围外）。

- `.apm/`、`.agents/`、`.codex/` 已被 Git 跟踪（`.gitignore` 不再忽略它们）。APM 运行时写入（bus、tracker、task log）会表现为工作区改动；派发与合并时需注意让 Worker 只提交自身产出，协调工件由 Manager 统一提交。

## 阶段总结

### Stage 1 - 项目基础与运行时骨架

Stage 1 建立了 SentinelDrive 初始运行时和开发基础。Platform 创建了 `frontend`、`backend`、`scheduler`、`worker`、`postgres`、`redis` 和 `reverse-proxy` 的 Docker Compose 脚手架，PostgreSQL 与 Redis 保持内部-only，并提供安全环境占位。Backend 用 FastAPI 应用外壳替换占位实现，加入环境 settings、`/health`、`/ready`、PostgreSQL/Redis readiness 探测、结构化错误响应和聚焦测试。Frontend 构建了中文安全运营工作台外壳，包含情报、告警、数据源、人工录入和用户页面占位，以及公共 API client 占位和生产构建验证。QA Documentation 添加 README、开发/部署/环境/Connector/运维/测试文档、数据源配置说明和 QA checklist。

主要协作发现：Docker daemon 不可用于后端容器内测试，因此后端验证使用本地 pytest 加 Compose 渲染。前端脚手架依赖需要修正，才能得到可 install、可 audit 的 Next.js 外壳。并行 merge 在 `docs/scaffold.md` 中发生重叠；最终文档保留了后端 readiness 和前端路由更新。后续小型集成 commit 将 `READINESS_TIMEOUT_SECONDS` 补充到环境变量参考中。

关键 commits：`15f5138` runtime scaffold merge，`b84bc62` backend shell merge，`f687046` frontend shell merge，`d23d221` documentation skeleton merge，`8b27160` readiness timeout documentation fix。

**任务日志：**
- task-01-01.log.md
- task-01-02.log.md
- task-01-03.log.md
- task-01-04.log.md

### Stage 2 - 核心领域模型与服务契约

Stage 2 完成了后端持久化基础、认证/用户/审计表面、worker Connector 运行时契约和跨服务配置装配。Backend 添加 SQLAlchemy 模型、Alembic 迁移、面向 PostgreSQL 的索引和 enum 处理、管理员 bootstrap 密码哈希、bearer-token 认证、管理员风格的用户管理端点和可复用审计日志。Platform 通过 `make config-check` 添加生产类占位校验，装配 worker/scheduler 环境设置，并强化文档中关于公共前端配置和内部-only 服务的说明。Intelligence Pipeline 添加 worker 侧 Connector 契约、数据源配置加载、registry/runtime helper、sample connector 执行、重试/超时/限速/错误处理、Celery task/scheduler 装配和聚焦 worker 契约测试。

主要审查发现：原始数据库模型分支使用了更宽泛的通用 intelligence types，且遗漏 MVP 必需的 `exposure` 与 `incident`；Manager review 在 merge 前修正并补充测试。后端认证有意使用无状态 token；logout 当前只做审计。Docker-backed 验证仍因 Docker daemon socket 不可用而无法执行，因此验证依赖本地后端/worker 测试、Alembic offline SQL 渲染、Compose config 渲染和配置检查。并行 merge 冲突主要出现在文档，已解决并保留 auth/persistence 与 Connector runtime 描述。

关键 commits：`7262ece` database models merge，`5607616` configuration/secrets merge，`5cdbedb` auth/users/audit merge，`fbef862` connector runtime merge。

**任务日志：**
- task-02-01.log.md
- task-02-02.log.md
- task-02-03.log.md
- task-02-04.log.md

### Stage 3 - 数据源采集与规范化

Stage 3 完成从公开/人工来源到原始持久化和规范化威胁情报的 ingest 路径。Intelligence Pipeline 添加 worker 侧原始采集持久化，覆盖 `sources`、`sync_states`、`job_logs` 和 `raw_intelligence`；随后实现 NVD、CISA KEV、RSS/Atom 和代表性厂商公告 Connectors，具备 mock 测试、可选 NVD API key、保守的 NVD 首轮同步窗口、轻量 HTML/PDF 元数据留存和 endpoint/feed 配置。Backend 添加认证后的人工录入 API，可直接创建 normalized intelligence，并把 research lead 处理为带 `research_lead` tag 的 advisory records。Intelligence Pipeline 最后添加 worker 侧规范化与去重管道，包含源特定 normalizers、确定性 CVE/URL/title/hash dedup keys、source attribution upserts、raw processing-status 更新和 `sentineldrive.normalize_raw_intelligence` Celery task。

主要审查发现：Task 3.1 保留现有 `job_status` enum，将 skipped/retry 语义放入 metadata，而不是增加迁移。在 source Connector 批次审查期间，Manager 添加 `0709af5`，确保 NVD incomplete-page 分页保持在同一个 last-modified window 内，并对 endpoint error 中类似 token 的值进行脱敏。规范化审查期间，Manager 添加 `a0aed35`，对 normalization error message 中类似 token 的值进行脱敏。阶段级验证重新运行 worker tests、compile checks、config validation 和 Compose rendering，结果成功。

关键 commits：`c12b202` raw collection persistence merge，`ab92d8a` manual entry API merge，`650e9f8` source connectors merge，`fe23751` normalization pipeline merge。

**任务日志：**
- task-03-01.log.md
- task-03-02.log.md
- task-03-03.log.md
- task-03-04.log.md
- task-03-05.log.md

### Stage 4 - 搜索、评分、告警与导出

Stage 4 完成了前端工作台需要的后端 API 和透明风险工作流。Backend 添加认证后的 intelligence search/detail 端点，支持 PostgreSQL 搜索/筛选/排序行为、来源归因、评分字段、关联告警和共享响应脱敏 helper。Intelligence Pipeline 添加确定性的固定规则风险评分，评分解释覆盖 CVSS、KEV、PoC、可利用性、认证要求、车辆关键影响、多厂商/组件影响和来源可信度。Backend 随后添加确定性告警生成、告警列表/详情/状态 API、数据源状态和任务日志 API、带审计的数据源状态更新，以及情报 CSV、单条情报 Markdown、告警 CSV 和轻量 PDF 摘要导出端点。

主要审查发现：告警 API review 期间，Manager 添加 `5c15140`，确保 status PATCH 未提供 `notes` 时保留既有告警备注。最终 source/export review 期间，Manager 添加 `f09ce1b`，让 SQL job-log filters 从与响应字段相同的 metadata 语义中派生 `retried` 和 `skipped`，包括 `attempts > 1` 和 `metadata.run_status = "skipped"`。阶段级验证成功重新运行后端聚焦测试、从 `backend/` 运行完整后端套件（review fix 后 `67 passed`）、后端 compile checks、whitespace checks 和 worker scoring tests。

关键 commits：`4c7f645` intelligence search API merge，`2177ae5` risk scoring service merge，`d457956` alert generation API merge，`dd0e5ec` source status and exports merge。

**任务日志：**
- task-04-01.log.md
- task-04-02.log.md
- task-04-03.log.md
- task-04-04.log.md
- task-04-05.log.md

### Stage 5 - 前端工作台集成

Stage 5 将中文前端工作台连接到认证后端 API，并用可用 MVP 工作流替换占位运营页面。Frontend 添加共享 API/data layer、客户端 session provider、login/logout/current-user 处理、受保护 workbench shell、中文 loading/error/empty/session-expired 状态，以及认证导出下载 helper。工作台页面现在覆盖 intelligence search/detail，包含筛选、分页、风险/来源/评分展示和导出；alert list/detail/status update 与 alert export；source status、source detail、job log 和 source status controls；manual entry create/update/list；current-user/admin 基础用户管理。

主要审查发现：5.1 review 期间，Manager 添加 `421e7e0`，避免登录失败时显示 session-expired 文案，并保证导出始终走认证下载 helper。5.2-5.4 review 期间，Manager 添加 `de45589`，移除指向非 UUID 示例 ID 的占位 intelligence detail 导航链接。Backend 随后通过 `bd43094` 完成 frontend API fit pass：当操作者在 alert list 或 alert CSV export filter 中输入非法 intelligence ID 时，返回结构化 `invalid_intelligence_id` 422。阶段级验证成功重新运行前端生产构建、frontend audit、后端聚焦 API tests、从 `backend/` 运行完整后端套件（`69 passed`）、后端 compile checks 和 whitespace checks。

关键 commits：`f5ba154` frontend data layer merge，`5177b15` workbench pages merge，`b3f5595` frontend API fit refinements merge。

**任务日志：**
- task-05-01.log.md
- task-05-02.log.md
- task-05-03.log.md
- task-05-04.log.md
- task-05-05.log.md

### Stage 6 - 加固、文档与部署就绪

Stage 6 完成项目加固和操作者交接。QA Documentation 盘点可用的后端、worker、前端、配置、Compose 和文档验证面，随后更新测试指导和 residual-risk 文档，而不是添加重复测试。Platform 执行了第一次完整 Docker Compose runtime verification，使用 live containers 和外部数据源访问；该 smoke test 发现并修复 runtime-only 问题，包括后端 bcrypt 兼容、worker PostgreSQL enum binding、worker/scheduler 出站 egress，以及 NVD 120 天 date-window 限制。QA Documentation 随后刷新 README 和 `docs/` 中的操作者/开发者文档，使命令示例与已实现 MVP 对齐，并明确 collection、normalization、scoring 和 alert evaluation 是分离的运维步骤。Platform 最后用具体 runbook 替换占位运维指导，覆盖 PostgreSQL 备份/恢复、服务生命周期、日志、健康检查、数据源操作、导出、留存、磁盘使用、例行维护和故障排查。

主要协作发现：Stage 6 将若干早期 residual risks 转化为已验证部署行为，尤其是 Docker runtime startup/routing 和 opt-in live-source checks。最后两个文档分支在 `docs/operations.md` 中重叠；merge 保留了 QA 的跨文档一致性更新，同时保留 Platform 的完整 backup/restore runbook。阶段级 merge 后验证成功重新运行 configuration validation、Compose rendering、whitespace checks 和 README/docs link validation。

关键 commits：`13daa8a` coverage pass merge，`6f829f2` Compose deployment verification merge，`9e8eb21` operator/developer documentation merge，`587c7e4` operations runbook merge。

**任务日志：**
- task-06-01.log.md
- task-06-02.log.md
- task-06-03.log.md
- task-06-04.log.md

### Stage 7 - 运维加固与管道自动化

Stage 7 完成初始预览后要求的运维自动化层。Intelligence Pipeline 添加定时 `sentineldrive.process_pipeline` worker path，将 source collection、raw persistence、normalization 和 scoring 串联起来，同时保留各阶段入口用于聚焦 replay。由于后端告警生成依赖 backend ORM/service packaging，alert evaluation 按设计仍在 backend 侧；operator `make process-once` 路径和后端 API 表面会明确保持这种分离。

Backend 和 Frontend 随后添加 operations control surface。Backend 引入认证后的 `/sources/pipeline/status` 和 `/sources/pipeline/trigger`、可 fake 的 Celery client、安全状态计数、脱敏、审计日志，以及后端 Celery enqueue 支持的配置/文档。Frontend 将中文 `/sources` 运维面板接入 processing status summaries、refresh、受限 processing trigger 和独立 alert evaluation controls。QA Documentation 添加 Playwright 浏览器工作流覆盖，使用确定性的 mocked API responses 验证 login-gated access、intelligence list/detail/export、manual-entry validation/submission、source processing controls、alert evaluation 和 alert status updates。Manager verification 期间，`0673ac5` 收紧了 E2E source-operations assertion，避免同时存在 loading 与 success `role=status` 元素时出现歧义。

Platform 完成了针对本地 Compose 栈的真实 backup/restore drill。文档化的 PostgreSQL dump、破坏性 restore、migrations、service restart、readiness checks 和 post-restore data proof 均按预期工作，生成的 dump 保持在 ignored 的 `backups/` 下。

阶段级验证成功重新运行相关后端聚焦测试（`24 passed`，存在既有 Starlette multipart deprecation warning）、前端 Playwright E2E（`4 passed`）、前端生产构建、frontend production audit、configuration validation、Compose rendering 和 whitespace checks。剩余浏览器/runtime 区分已明确：mocked Playwright tests 验证前端工作流和 API 装配；live Compose validation 仍是 reverse-proxy、backend、PostgreSQL、Redis、worker、scheduler 和 live-source 行为的事实来源。

关键 commits：`4ad499e` processing pipeline merge，`3af699c` operations pipeline API merge，`8518bef` operations control UI merge，`f0b4a45` browser workflow coverage merge，`0673ac5` E2E stabilization。

**任务日志：**
- task-07-01.log.md
- task-07-02-backend.log.md
- task-07-02-frontend.log.md
- task-07-03.log.md
- task-07-04.log.md

### Stage 8 - 前端适配与 AI 情报接入预留

Stage 8 是 Stage 1-7 标记完成后由用户追加的运营适配阶段，聚焦工作台布局质量与外部/AI 情报写入通道。阶段由 Manager 2 启动并完成前两个任务后因上下文丢失中断；Manager 3 依据两月后的 handoff-02 重建阶段：核实 8.1/8.2 已合并，判定 8.3 未执行（无任务日志、worker 无外部来源 normalizer），补写 plan/tracker 的 Stage 8 条目后经用户确认继续协调。启动时还发现 `main` 上存在交接之外的 5 个中文化 commit（`b4a81ba`、`5ca08eb`、`ed223cc`、`b39d16b`、`99d1b65`），未纳入 APM 追踪，按用户指示保持现状。

任务结果：8.1 修复工作台宽屏利用不足与来源详情挤压，并补充三档桌面视口布局 E2E（`fa67fcd`）。8.2 交付认证保护的 `POST /intelligence/ingest`，内联规范化写入核心情报/raw/来源归因，CVE 优先去重并脱敏审计（`782deda`）。8.3 为 worker 新增 `ExternalIngestNormalizer`，按 `entry_origin="external_ingest"` 注册，去重键逐字对齐后端 `_dedup_key`，已规范化记录幂等跳过（`79fd4d3`）；审查确认提交仅含 4 个 worker 文件，worker 全量 88 测试通过。8.4 新增外部 ingest 渲染场景的 Playwright E2E（6/6 通过）、`docs/external-ingest.md` 接入文档及 README/testing/connectors 同步（`2220f53`）。

主要审查发现：ingest 写入的 raw 行为 `processing_status="normalized"`，worker pending 查询不会重复处理；后端 raw metadata 不保留 cve_id/external_id/severity 等字段，未来若有把外部情报写成 pending raw 的 connector 需在 metadata 显式补齐；worker `app` 与 backend `app` 包名冲突，跨包测试依赖 pytest pythonpath 的 backend 优先顺序；worker 去重键对 CVE 大写化而后端保留原样大小写，规范输入下收敛、小写输入会分叉。8.4 的 worker 环境无法运行后端 ingest 测试套件（缺 fastapi/httpx 且离线安装失败），该套件在 8.2 审查时已验证且后端代码此后未变。8.4 的 E2E 用 `tag=external_ingest` mock 分支隔离场景，避免破坏既有列表断言。

**任务日志：**
- task-08-01.log.md
- task-08-02.log.md
- task-08-03.log.md
- task-08-04.log.md
