# Connector 开发指南

本文定义 SentinelDrive 数据源实现的 Connector 边界和运行时契约。Worker 提供可复用 Connector runtime、生产数据源 Connectors，以及 sample no-op Connector，用于验证调度、重试、cursor 和 Raw Intelligence-shaped 输出。

## 边界

源特定采集逻辑必须放在 `worker/sentineldrive_worker/connectors/` 下的 Connectors 中。`worker/app/connectors/` 只负责兼容性 re-export。

以下可复用行为必须留在单个 Connector 外部：

- 核心存储。
- Raw retention policy。
- Normalization。
- Deduplication。
- Search indexing。
- 固定规则风险评分。
- Alert triggering。
- Export formatting。

外部与 AI 收集器还有一条非 Connector 写入路径：认证保护的 `POST /intelligence/ingest` 由后端直接写入 raw 与核心情报记录，不经过 Connector、`sources` 配置或 worker 采集。worker 的 `ExternalIngestNormalizer` 按 `entry_origin: external_ingest` 识别这类 raw 记录，其去重键与 ingest 端点对齐，已 normalized 的记录幂等跳过。接入方式见 [外部与 AI 情报接入](external-ingest.md)。

## 当前扩展点

Worker 目前包含：

- `worker/sentineldrive_worker/connectors/contracts.py`：connector protocol、source configuration、cursor context、retry policy 和 Raw Intelligence payload shape。
- `worker/sentineldrive_worker/connectors/config.py`：基于环境变量并兼容数据库行的数据源配置加载。
- `worker/sentineldrive_worker/connectors/nvd_cisa.py`：NVD CVE 与 CISA KEV 源特定 Connectors。
- `worker/sentineldrive_worker/connectors/registry.py`：source-agnostic Connector registry。
- `worker/sentineldrive_worker/connectors/rss_vendor.py`：RSS、Atom 和 vendor advisory metadata Connectors。
- `worker/sentineldrive_worker/connectors/runtime.py`：enable/disable、timeout、retry、rate limiting 和 error recording helpers。
- `worker/sentineldrive_worker/connectors/samples.py`：用于证明 runtime path 的 sample Connector。
- `worker/sentineldrive_worker/normalization/`：source-aware raw-to-normalized mapping、dedup key generation 和 merge/upsert。
- `worker/sentineldrive_worker/scoring/`：normalized threat intelligence rows 的固定规则评分。
- `worker/sentineldrive_worker/persistence/service.py`：sources、sync state、job logs 和 raw intelligence records 的 raw collection persistence。
- `worker/app/tasks.py`：稳定 Celery task 入口 `sentineldrive.sync_sources`、`sentineldrive.normalize_raw_intelligence`、`sentineldrive.score_threat_intelligence` 和 `sentineldrive.process_pipeline`。
- `worker/scripts/sync-once.sh`：调用 sync task 的命令。

未实现且没有测试覆盖的数据源，不要在文档中声明为可运维。

## Connector 形态

Connector 实现 `collect(context: ConnectorContext) -> ConnectorResult`，并暴露 `source: SourceConfig`。源特定 fetch 和 parse 逻辑位于 Connector 内部。Runtime 将 source configuration 和 incremental cursor 放入 `ConnectorContext`，并接收：

- `items`：兼容 `raw_intelligence` 字段的 `RawIntelligencePayload` entries。
- `next_cursor`：成功运行后由 worker persistence service 持久化的 cursor。
- `metadata`：用于 job logs 的非密钥执行 metadata。

每个 `RawIntelligencePayload` 必须保留来源归因：

- Source name。
- Source type。
- Source URL。
- Fetch timestamp。
- 可用时的 first-seen timestamp。
- 可选 external ID。
- 确定性 `raw_hash` 和 `content_hash`。
- Title、summary、snippet、raw content、parsing status 和 retention mode。

新增 Connector 必须记录并测试：必需或可选环境变量、认证要求、timeout、retry、rate limiting、缺失可选凭证行为、raw response retention mode 和 parsing failure behavior。

## 新增 RSS 或 Atom Feeds

普通 RSS 或 Atom 来源优先通过配置新增，而不是写代码：

```env
SOURCE_ENABLED_RSS=true
SOURCE_RSS_FEEDS=[{"name":"Example Security Feed","url":"https://example.test/security/feed.xml","source":"example"}]
```

每个 feed object 必须包含 `url`。`name` 和 `source` 等可选安全字段会保留到 metadata。RSS Connector 负责 RSS 2.0 与 Atom 解析、feed attribution、item timestamps、确定性 external IDs、stable hashes 和 duplicate GUID/URL idempotency。feed 解析行为变更时，更新 `worker/tests/test_rss_vendor_connectors.py`。

数据库驱动 source rows 可在 `config.feeds` 中提供相同 shape。不要把凭证或私有 headers 写进文档示例。

## 新增 API 型来源

如果新增来源无法用 RSS 或 vendor endpoint metadata 表达：

1. 在 `worker/sentineldrive_worker/connectors/` 下添加源特定 fetch/parse 逻辑。
2. 只返回 `RawIntelligencePayload` objects；不要在 Connector 中写 storage、normalization、scoring、alerts、exports 或 search 行为。
3. 在 `worker/sentineldrive_worker/connectors/registry.py` 注册 Connector。
4. 在 `worker/sentineldrive_worker/connectors/config.py` 添加环境变量或数据库驱动 `SourceConfig` 加载。
5. 添加 mocked tests，覆盖 success、non-2xx、malformed payload、missing optional credentials、timeout、retry、rate limiting、attribution 和 idempotent output。
6. 在 `docs/source-configuration.md` 记录 source configuration，并在 `docs/environment.md` 记录新增变量。

凭证保存在 `SourceConfig.credentials` 或 `SourceConfig.headers` 中；runtime logs 和 summaries 必须脱敏。HTML 或 PDF 派生记录默认使用 metadata-only retention，除非后续任务明确实现附件存储。

## 数据源配置

全局 runtime 默认值来自：

- `SOURCE_SYNC_INTERVAL_SECONDS`
- `SOURCE_TIMEOUT_SECONDS`
- `SOURCE_RATE_LIMIT_PER_MINUTE`
- `SOURCE_RETRY_ATTEMPTS`

当前数据源启用状态来自 `SOURCE_ENABLED_NVD`、`SOURCE_ENABLED_CISA_KEV`、`SOURCE_ENABLED_VENDOR_ADVISORIES`、`SOURCE_ENABLED_RSS` 和 `SOURCE_ENABLED_SAMPLE`。`SOURCE_RSS_FEEDS` 和 `SOURCE_VENDOR_ADVISORY_ENDPOINTS` 接收公共 feed 或 endpoint objects 的 JSON list。Loader 也支持形状类似后端 `sources` 和 `sync_states` models 的数据库驱动 source rows，因此可以不改 runtime control flow 就新增 RSS feeds 或 vendor endpoints。

Secrets 和 private headers 只能保存在 `SourceConfig.credentials` 和 `SourceConfig.headers`；runtime summaries 和 errors 不得打印它们。数据库驱动的 `config.feeds` 与 `config.endpoints` 会保留到 source metadata，而 `config.credentials` 和 `config.headers` 会从 runtime summaries 中排除。

## 运行时行为

`sentineldrive.sync_sources` 加载 source configs，跳过 disabled sources，通过 registry 创建 Connector，并独立运行每个 Connector。失败的 Connector 返回 failed source record 并记录 sanitized error state，但不会阻止 worker 处理其他 sources。配置 `DATABASE_URL` 后，task 会把每次 source run 持久化到现有数据库 schema。

Runtime 应用：

- `SourceConfig.timeout_seconds` 的 per-source timeout。
- `RetryPolicy` 的 retry attempts。
- `rate_limit_per_minute` 的保守 per-source rate limiting。
- 通过 `ConnectorContext.cursor` 和 `ConnectorResult.next_cursor` 传递 incremental cursor。

Celery Beat 使用 `SOURCE_SYNC_INTERVAL_SECONDS` 调度 `sentineldrive.process_pipeline`。`sentineldrive.sync_sources` 仍作为 collection-only task 保留，用于手动 replay 和故障排查。

## 持久化行为

每次 source run，worker 记录：

- `sources` row：当前 status 和 latest success/error metadata。
- `sync_states` row：last run、next run、failure count 和 cursor。
- `job_logs` row：success、failed 和 skipped runs。
- `raw_intelligence` rows：成功 connector payloads。

Sync cursors 只在成功 connector runs 后推进。失败运行保留上一 cursor 并增加 failure count。Skipped runs 被记录在 job log metadata 中，因为当前共享 job status 值为 `queued`、`running`、`success` 和 `failed`。

## 规范化行为

`sentineldrive.normalize_raw_intelligence` 读取 `processing_status` 为 `pending` 或 `collected` 的 raw rows，经 worker normalizer registry 分发，并 upsert `threat_intelligence` 与 `threat_intelligence_sources`。每条 raw row 独立处理；规范化失败只将该 raw row 标记为 failed，并写入脱敏错误信息。

去重优先级是确定性的：

- 存在 CVE ID 时使用 CVE ID，并合并 NVD、CISA KEV、RSS、vendor 和 manual sources 的相同 CVE。
- Canonical source URL。
- Title + source name。
- Content hash 或 normalized text hash。

Merge 会保留所有 source names 和 URLs 且不重复，更新 source attribution `last_seen_at`，并保守填充结构化字段。更强 exploit/severity/confidence 信号可替换弱默认值，但空 fallback 值不得覆盖结构化数据。

## 评分与处理管道

`sentineldrive.score_threat_intelligence` 对未评分或仍为默认 `info` 风险等级的 normalized rows 评分。传入 `force=True` 时可重新评估已评分 rows，但更新必须幂等。任务只写入 `risk_score`、`risk_level`、`metadata.scoring` 和 `updated_at`。

固定规则引擎透明且确定。它组合 CVSS、KEV、known exploited、PoC、remote exploitability、authentication requirement、车辆关键组件影响、多厂商/通用组件影响和 source confidence。分数限制在 0-100，并映射到 `critical`、`high`、`medium` 和 `low`。`metadata.scoring` 中的 explanation payload 保存 rule version、source fingerprint、score、level、contributing factors 和 detected signals。

`sentineldrive.process_pipeline` 按顺序运行 collection、raw persistence、normalization 和 scoring。每阶段都应可重试且幂等：raw records 使用既有 raw upsert，normalization 使用确定性 dedup keys 和 source attribution upserts，scoring 只替换 score fields 与确定性 `metadata.scoring`。

Alert creation 保留在 backend service layer，因为 worker image 不包含 backend ORM models。操作者可运行 `make process-once`，先执行 worker processing，再运行 backend alert evaluation script。

## Raw Retention 默认值

- API 与 RSS 来源可在体积合理时保存 raw JSON 或 XML item payloads。
- HTML 和 PDF 来源默认保存 URL、title、summary 或 snippet、hash、fetch metadata 和 parsing status，不保存完整快照或下载附件。
- Vendor advisory endpoint pages 和发现的 PDF links 使用 metadata-only payloads。默认不下载 PDF attachments。

Persistence service 会对 HTML 和 PDF source types 强制 metadata-only retention，即使 Connector 意外发出 `raw_content`。

## 测试要求

Connector tests 必须 mock 外部网络来源。覆盖：

- 成功 fetch 和 parse。
- Timeout。
- Non-2xx 或源特定错误响应。
- Malformed response body。
- 缺失可选 API key。
- Rate limit behavior。
- Retry exhaustion。
- 重复处理不生成重复核心情报。
- Source attribution 保留。
- 固定评分边界、信号因素、source confidence、幂等 metadata update 和代表性车辆组件。

Contract、source Connector 和 persistence tests 位于 `worker/tests/`。它们使用 mocked HTTP responses、sample Connector、in-memory success/failing/flaky/slow Connectors 和 SQLite-backed persistence tests，不执行 live network calls。

## 已实现 Source Connectors

- `nvd`：使用 NVD API 2.0 CVE modified-date windows，通过 `apiKey` header 支持可选 `NVD_API_KEY`，首轮同步保守，分页有上限。
- `cisa-kev`：解析包含 `vulnerabilities` arrays 的官方风格 JSON catalogs，以及字段等价的 CSV catalogs。
- `rss`：解析可配置 RSS 2.0 和 Atom feeds，保留 feed attribution、item timestamps、canonical URL、deterministic external ID 和 stable hashes。
- `vendor-advisories`：抓取配置的 vendor endpoints，记录页面 metadata 和类似公告的 links，并保持 HTML/PDF 派生 payloads 为 metadata-only。内置代表性 seed list 覆盖 BYD、NIO、Li Auto、Qualcomm 和 Bosch；BYD 标记为 manual-review fallback entry point。

Connectors 只发出 `RawIntelligencePayload` items。规范化与去重由 worker normalization package 处理。固定评分由 worker scoring package 处理。搜索和告警评估留在 Connector 外部。

## 文档 Checklist

- [ ] 将 Connector 添加到 `docs/source-configuration.md`。
- [ ] 在 `docs/environment.md` 记录新增环境变量。
- [ ] 示例中不要出现真实 Token、凭证或私有 URL。
- [ ] 说明 HTML 和 PDF 来源的 raw retention 行为。
- [ ] 在声明 Connector 完成前，添加 mocked network response 测试。
