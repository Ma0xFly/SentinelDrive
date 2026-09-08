# 数据源配置示例

本文记录安全的数据源配置示例。Worker 已实现 Connector runtime contract、raw persistence、NVD、CISA KEV、RSS、vendor advisory metadata collection、sample no-op Connector、raw normalization、fixed scoring 和 scheduled processing pipeline。Manual entry 与 alert evaluation 由后端 API/service layer 处理，不属于 Connector。

## 全局数据源设置

```env
SOURCE_SYNC_INTERVAL_SECONDS=3600
SOURCE_TIMEOUT_SECONDS=20
SOURCE_RATE_LIMIT_PER_MINUTE=20
SOURCE_RETRY_ATTEMPTS=3
SOURCE_ENABLED_SAMPLE=true
SOURCE_RSS_FEEDS=[]
SOURCE_VENDOR_ADVISORY_ENDPOINTS=
RAW_RETENTION_DAYS=90
HTML_RETENTION_MODE=metadata_only
PDF_RETENTION_MODE=metadata_only
```

Worker 和 scheduler 使用相同默认值。Celery Beat 使用 `SOURCE_SYNC_INTERVAL_SECONDS` 调度 `sentineldrive.process_pipeline`，该任务会采集已启用数据源、持久化 raw rows、规范化 pending raw rows，并对 normalized intelligence 评分。

未来数据库驱动的数据源行可在 source `config` 字段中覆盖 `sync_interval_seconds`、`timeout_seconds`、`rate_limit_per_minute`、`retry_attempts`、`headers` 和 `credentials`。文档示例中不要存放真实密钥。

## NVD

```env
SOURCE_ENABLED_NVD=true
NVD_API_KEY=
```

`NVD_API_KEY` 是可选项。留空时，NVD Connector 不发送 `apiKey` header，配置加载器使用更严格的未认证限速。不要提交真实 NVD API key。

运行时状态：NVD Connector 使用 NVD API 2.0 CVE endpoint，参数包括 `lastModStartDate`、`lastModEndDate`、`startIndex` 和 `resultsPerPage`。首轮同步默认使用最近 120 天窗口，匹配 NVD 对 CVE API 日期参数的范围限制，并对单次运行分页做上限控制，避免完整历史导入。

## CISA KEV

```env
SOURCE_ENABLED_CISA_KEV=true
```

运行时状态：CISA KEV Connector 可读取官方 JSON catalog 形态（包含 `vulnerabilities` 数组），也支持等价 catalog 字段的 CSV 数据。

## 厂商公告

```env
SOURCE_ENABLED_VENDOR_ADVISORIES=false
SOURCE_VENDOR_ADVISORY_ENDPOINTS=
```

`SOURCE_VENDOR_ADVISORY_ENDPOINTS` 接收 endpoint objects 的 JSON list。留空时使用内置代表性 seed list。该来源默认关闭，因为厂商页面差异较大，启用 unattended collection 前应先人工审查。

安全 override 示例：

```env
SOURCE_VENDOR_ADVISORY_ENDPOINTS=[{"vendor":"Bosch","url":"https://psirt.bosch.com/security-advisories/","verification_status":"official_security_entry"}]
```

内置代表性端点：

- BYD：`https://www.bydglobal.com/`，标记 `verification_status: needs_manual_review` 和 `endpoint_type: official_fallback`。
- NIO：`https://niosrc.bugbank.cn/` 和 `https://niosrc-en.bugbank.cn/`。
- Li Auto：`https://security.lixiang.com/`。
- Qualcomm：`https://www.qualcomm.com/company/product-security` 和 `https://docs.qualcomm.com/product/publicresources/securitybulletin`。
- Bosch：`https://psirt.bosch.com/security-advisories/`。
- Vector Informatik：`https://www.vector.com/en/services/security-advisories/`。
- Wind River：`https://www.windriver.com/security`。
- Geely GSRC：`https://security.geely.com/`。
- Xiaomi SRC：`https://trust.mi.com/zh-CN/misrc/response`。

运行时状态：vendor advisory Connector 抓取 endpoint 页面，保存轻量页面 metadata，并记录类似公告的链接。HTML 与 PDF 派生记录使用 metadata-only retention；默认不下载 PDF 附件。

## NHTSA 召回

```env
SOURCE_ENABLED_NHTSA_RECALLS=false
```

NHTSA 召回 Connector 默认关闭。它使用免认证的 `https://api.nhtsa.gov/recalls/recallsByVehicle?make=&model=&modelYear=` 端点，按配置的车辆清单（默认 Tesla 全系 + Rivian R1T/R1S + Chevy Bolt EV/EUV，近 4 个 model year）逐车查询，`recallsByMake` 与 `campaigns` 端点因需认证（403）不可用。

运行时状态：只保留软件/OTA 相关召回——`overTheAirUpdate` 布尔位或 Component/Summary 命中软件、telematics、cyber、OTA 等关键词即打 `software_related` 标记，机械类召回在采集层过滤。campaign number 作为 external ID，cursor 保存 `seen_campaigns` 集合实现跨轮幂等。API JSON 以 `raw_payload` 模式保留安全公开召回字段，不回传 VIN/PII。

## RSS

```env
SOURCE_ENABLED_RSS=true
SOURCE_RSS_FEEDS=[{"name":"Example Security Feed","url":"https://example.test/security/feed.xml","source":"example"}]
```

`SOURCE_RSS_FEEDS` 接收 feed objects 的 JSON list。每个对象必须包含 `url`；可选安全字段 `name` 和 `source` 会保留到 item metadata。

运行时状态：RSS Connector 支持 RSS 2.0 和 Atom feeds，保留 feed attribution，并将 item GUID 或 URL 映射为确定性 external ID 和稳定 hash。畸形 feed 会清晰失败；重复 GUID 或 URL 会以幂等方式重新处理。

数据库驱动 source rows 可使用同样形态设置 `config.feeds` 或 `config.endpoints`。`config.credentials` 和 `config.headers` 不会进入 runtime metadata summaries。

## Sample Runtime Connector

```env
SOURCE_ENABLED_SAMPLE=true
```

Sample Connector 会发出一个确定性的 Raw Intelligence-shaped heartbeat item，并推进内存 cursor。它只用于验证 worker runtime path、测试、retry/timeout/rate-limit helpers 和 scheduler wiring，不是生产情报源。

当 worker 配置了 `DATABASE_URL`，sample 运行会像其他 Connector 一样被持久化：

- `sources` 中更新 source status 和 latest success/error 字段。
- `sync_states` 中更新 cursor、last run、next run 和 failure counts。
- success、failure 和 skipped outcomes 写入 `job_logs`。
- successful payloads 写入或更新 `raw_intelligence`。

Connector 输出的 Raw Intelligence-shaped 字段示例：

- `source_name`
- `source_type`
- `source_url`
- `external_id`
- `fetched_at`
- `first_seen_at`
- `title`
- `summary`
- `snippet`
- `raw_content`
- `raw_hash`
- `content_hash`
- `parsing_status`
- `processing_status`
- `metadata`
- `retained_payload_mode`

## 人工情报录入

Manual entries 通过后端 API 创建，不通过 source Connector 配置。后端创建的 manual entries 已写入 normalized threat intelligence records；worker normalization pipeline 会跳过这些已完成 raw rows。如果遇到 raw manual rows，normalization 会保留现有 intelligence types，将 research leads 映射为 `advisory`，添加 `research_lead` tag，并默认使用 `under_review` 状态。
