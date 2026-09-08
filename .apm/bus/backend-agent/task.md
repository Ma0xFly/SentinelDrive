---
stage: 10
task: 1
agent: backend-agent
log_path: ".apm/memory/stage-10/task-10-01.log.md"
has_dependencies: false
---

# Task 10.1 - 访客只读后端

## 背景

Stage 10 增加访客只读访问。经用户确认的公开边界：**情报列表/详情 + 信源非敏感字段 + 态势仪表盘统计**可匿名只读；写操作、导出、告警处置、手工录入、用户管理，以及**信源运维细节（任务日志/最近错误/失败次数/处理计数）保持登录**。本任务只做后端，前端由 Task 10.2 承接。

## Workspace

- 从 `main` 创建功能分支 `feat/guest-readonly-backend`
- 只提交本任务自身产出（`backend/` 下代码与测试）；`.apm/`、`web3开发/`、`frontend*`、`worker/` 不提交

## 实现要求

1. **可选用户依赖**：在 `backend/app/api/deps.py` 新增 `get_optional_current_user`——复用现有 `HTTPBearer(auto_error=False)`，无凭据（`credentials is None`）返回 `None`，有凭据走现有 `decode_access_token` 逻辑；凭据非法仍 401。保留 `get_current_user` 原样不动。
2. **公开 read 面**（改下列 GET 端点用可选用户依赖）：
   - `GET /intelligence`（列表）、`GET /intelligence/{id}`（详情）
   - `GET /stats/overview`（态势统计）
   - `GET /sources`、`GET /sources/{source_id}`：仅公开**非敏感字段**（名称、类型、base_url、启用状态、来源 URL 等公开属性）
3. **运维字段裁剪**：`/sources` 的任务日志、最近错误、失败次数、处理计数等运维字段，在未认证下不返回（或按认证态裁减）。先核对 `backend/app/api/schemas/` 与 `routes/sources.py` 现有哪些字段，把运维敏感字段从匿名响应剥离。不要改动内部持久化。
4. **写端点保持认证**：`POST /manual-entries`、`PATCH /alerts/{id}/status`、`PATCH /sources/{id}/status`、`POST /sources/pipeline/trigger`、`POST /alerts/evaluate`、导出端点（`GET /exports/*`）、用户端点等**全部保持强认证**；管理员操作保持 `require_admin_user`。不能因公开 read 面引入任何匿名写入口。
5. **敏感信息**：匿名响应不得含 raw payload、凭证、Token、内部服务细节。情报详情已有的敏感字段脱敏逻辑保持不变。

## 测试

在 `backend/tests/` 按既有风格新增聚焦测试，覆盖：
- 未认证读情报列表/详情 200
- 未认证读 `/stats/overview` 200
- 未认证读 `/sources` 仅含非敏感字段（断言不含任务日志/错误/计数）
- 未认证访问写端点/导出 401
- 认证用户读 `/sources` 含运维字段
- 非法 token 仍 401
既有测试保持通过（`.venv/bin/python -m pytest backend/tests -q`，或从 `backend/` 目录运行）。

## 明确排除

- 不改前端、worker、docker-compose、迁移；不改认证 token 机制本身（仍是无状态 HMAC bearer）
- 不新增公开写入口、不做多租户 RBAC

## 验收清单

- [ ] 未认证可读三类公开面；写/导出/告警/录入/用户端点仍 401
- [ ] `/sources` 匿名响应的运维字段被裁剪
- [ ] 新增测试通过、既有后端测试无回归
- [ ] 无敏感字段泄露

## 报告要求

完成后写入 `.apm/memory/stage-10/task-10-01.log.md`（frontmatter：stage/task/title/agent/status/important_findings/compatibility_issues），并向 `.apm/bus/backend-agent/report.md` 提交 Task Report（Summary / Details / Output / Validation / Issues）。