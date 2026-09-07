# 外部与 AI 情报接入

本文说明外部收集器、AI 分析流程如何通过后端 ingest 端点写入情报，以及写入后如何在工作台中核验结果。

ingest 是 Connector 之外的写入路径：它由后端 API 直接持久化，不依赖 `sources` 配置、worker 采集或 Celery 调度。Connector 采集路径见 [Connector 开发指南](connectors.md)。

## 端点与认证

- 端点：`POST /api/intelligence/ingest`（经 `reverse-proxy` 反向代理到 `backend`）。
- 认证：Bearer token。先调用 `POST /api/auth/login` 获取 `access_token`，再在 `Authorization: Bearer <token>` 中携带。
- 未认证请求返回 `401`，不会写入任何数据。

## 请求字段

请求体为 JSON。必填字段：`source_name`、`source_url`、`title`、`summary`。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source_name` | string（1-160） | 来源名称，用于来源归属展示与筛选。 |
| `source_url` | string（≤1000） | 来源页面 URL，必须是含 `://` 的绝对地址。 |
| `platform` | string（≤80，可选） | 收集器平台标识，会同时写入标签。 |
| `title` | string（3-500） | 情报标题。 |
| `summary` | string（1-4000） | 情报摘要。 |
| `description` | string（≤12000，可选） | 详细描述，写入 raw 记录 snippet。 |
| `external_id` | string（≤240，可选） | 收集器侧唯一编号。 |
| `cve_id` | string（可选） | CVE 编号，格式 `CVE-YYYY-NNNN`，自动转大写。 |
| `cnvd_id` | string（≤80，可选） | CNVD 编号。 |
| `vendor_advisory_id` | string（≤120，可选） | 厂商公告编号。 |
| `affected_vendor` | string（≤160，可选） | 受影响厂商。 |
| `affected_products` | string list（≤50，可选） | 受影响产品，自动去重、小写。 |
| `components` | string list（≤50，可选） | 车辆组件信号，供 worker 规范化推断组件与攻击面。 |
| `attack_surfaces` | string list（≤50，可选） | 攻击面信号。 |
| `severity` | string，默认 `unknown` | 支持 `critical`/`high`/`medium`/`low`/`unknown`，也接受中文别名 `严重`/`高危`/`中危`/`低危`/`信息`。 |
| `external_score` | number（0-100，可选） | 收集器侧评分。≤10 时同时记为 CVSS 分数。 |
| `published_at` | datetime（可选） | 原始发布时间。 |
| `collected_at` | datetime（可选） | 收集时间，缺省为服务端当前时间。 |
| `dedup_key` | string（≤320，可选） | 收集器侧稳定去重键。 |
| `content_hash` | string（≤128，可选） | 内容哈希。 |
| `raw_payload` | object（可选） | 原始 JSON 载荷，≤32 KB，脱敏后留存。 |
| `tags` | string list（≤30，可选） | 追加标签，自动去重、小写。 |

校验规则：

- 未知字段会被拒绝（返回 `422`），不存在静默忽略。
- `title`、`summary`、来源名称等文本如果包含疑似未脱敏的凭证（如 API key、私钥片段），返回 `422`。
- `raw_payload` 超过 32 KB 返回 `422`。
- `cve_id` 不匹配格式时返回 `422`。

## 响应

首次写入返回 `201`；命中已有记录（去重）返回 `200`。响应字段：

```json
{
  "id": "0f1e2d3c-0000-4000-8000-000000000000",
  "raw_intelligence_id": "0f1e2d3c-0000-4000-8000-000000000001",
  "status": "created",
  "duplicate": false,
  "dedup_key": "cve:CVE-2026-7777",
  "title": "Example vendor remote code execution advisory",
  "cve_id": "CVE-2026-7777",
  "source_name": "AI 情报收集器",
  "source_url": "https://collector.example.test/ingest/CVE-2026-7777",
  "message": "外部情报已接收。"
}
```

`status` 为 `created`（新建）或 `updated`（命中去重后合并来源信息），`duplicate` 表示是否命中已有记录。

## 去重优先级

去重是确定性的，优先级从高到低：

1. `cve_id`：存在时直接按 CVE 匹配已有记录。
2. `dedup_key`：按收集器提供的去重键。
3. `external_id`：按 `source_name` + `external_id`。
4. `content_hash`。
5. 来源 URL。
6. 标题 + 摘要 + 来源的规范化文本哈希。

命中已有记录时不新建核心情报，而是合并：追加来源名称/URL、标签和外部编号，更新 `last_seen_at`；severity 只会被更强的取值替换，已有的结构化字段不会被空值覆盖。

## 数据落点与留存

一次成功的 ingest 写入：

- `raw_intelligence` 一行：`source_type` 为 `api`，`processing_status` 为 `normalized`，`retained_payload_mode` 为 `metadata_only`；`raw_payload` 脱敏后保存。
- `threat_intelligence` 一行：`intelligence_type` 为 `vulnerability`（有 CVE）或 `exposure`（有攻击面）或 `advisory`；标签固定包含 `external_ingest`。
- `threat_intelligence_sources` 一行：保留来源名称、来源 URL、外部编号和首次/最近发现时间。

ingest 不创建 `sources` 表中的数据源行，因此 ingest 记录不会出现在 `/sources` 的数据源列表中；`/sources` 的处理控制计数也不受影响（ingest raw 记录已是 normalized 状态）。

## Worker 规范化与评分

- worker 的 `ExternalIngestNormalizer` 按 raw 记录 metadata 中的 `entry_origin: external_ingest` 分发。其去重键计算与 ingest 端点逐字对齐（`cve → dedup_key → external_id → content_hash → url → text`），同一条情报无论走 ingest 端点还是 worker 流水线，都会落到同一行核心情报。
- 已经 normalized 的 external ingest raw 记录会被 worker 幂等跳过，不会重复规范化。
- 评分：`external_score` 非空时写入 `risk_score`（≤10 时同时记为 CVSS）；`risk_level` 由 severity 映射。`risk_score` 为空或 `risk_level` 仍为 `info` 的记录，会由 worker 评分任务 `sentineldrive.score_threat_intelligence`（`make process-once` 的一部分）按固定规则补算。

## 写入示例

先获取 token，再提交一条情报（在部署了 Compose 运行栈的主机上执行）：

```bash
# 在 .env 所在目录执行，管理员账号来自 ADMIN_BOOTSTRAP_EMAIL / ADMIN_BOOTSTRAP_PASSWORD
source .env

token=$(curl -s -X POST http://127.0.0.1/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"'"$ADMIN_BOOTSTRAP_EMAIL"'","password":"'"$ADMIN_BOOTSTRAP_PASSWORD"'"}' \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

curl -s -X POST http://127.0.0.1/api/intelligence/ingest \
  -H "Authorization: Bearer $token" \
  -H "Content-Type: application/json" \
  -d '{
    "source_name": "AI 情报收集器",
    "source_url": "https://collector.example.test/ingest/CVE-2026-7777",
    "title": "Example vendor remote code execution advisory",
    "summary": "Collector summary of a vendor remote code execution advisory.",
    "cve_id": "CVE-2026-7777",
    "severity": "high",
    "external_score": 78,
    "external_id": "ai-collector-2026-7777",
    "tags": ["ai_collector"]
  }'
```

重复提交同一请求返回 `200` 且 `duplicate: true`，核心情报不增加。

## 结果核验

工作台核验（前端为中文运营工作台）：

1. 打开情报列表，在「标签」筛选 `external_ingest` 或在「来源」筛选收集器名称，确认记录出现，并检查 CVE、风险等级和来源列。
2. 点击「查看」进入详情，检查「来源归属」（来源名称、URL、外部编号）、「标签」中的 `external_ingest`，以及「去重键」。
3. 去重核验：对同一 CVE 重复调用 ingest 后，列表总数不变，详情中来源信息被合并。

审计核验：每次 ingest（含重复提交）写入一条 `audit_events`，`action` 为 `manual_entry`，summary 区分首次接收与重复接收，metadata 记录 `entry_origin`、`dedup_key`、`source_name` 和 `platform`。审计记录不包含 raw payload。当前没有审计查询 API，可在宿主机用以下命令查看最近记录：

```bash
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT created_at, action, summary FROM audit_events WHERE action = '"'"'manual_entry'"'"' ORDER BY created_at DESC LIMIT 10;"'
```

## 验证边界

两层验证互不替代：

- **Playwright mock 验证**：`cd frontend && pnpm e2e` 中的外部/AI ingest 场景只在浏览器里 mock `/api/*` 响应，验证情报列表与详情页对 ingest 记录的渲染。它不触达真实后端，不访问真实 NVD/CISA 或网络来源。
- **live Compose 验证**：在运行栈上按「写入示例」用 curl 走真实认证与写入路径，验证持久化、去重、审计与工作台展示。命令见 [测试与 QA 指南](testing.md) 与 [运维手册](operations.md)。

## 相关文档

- [Connector 开发指南](connectors.md)：Connector 采集路径与规范化行为。
- [数据源配置示例](source-configuration.md)：Connector 数据源配置。
- [测试与 QA 指南](testing.md)：E2E 与后端测试覆盖。
- [运维手册](operations.md)：运行栈操作与故障排查。
