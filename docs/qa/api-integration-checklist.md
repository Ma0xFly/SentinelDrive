# API 集成 Checklist

后端 API 行为新增或变更时使用本 checklist。

## 当前 API 表面

- [ ] `GET /health` 返回已实现的 health response。
- [ ] `GET /intelligence` 要求 bearer auth，并返回有界 pagination metadata。
- [ ] `GET /intelligence/{intelligence_id}` 要求 bearer auth，对缺失记录返回确定性 404。
- [ ] `GET /alerts`、`GET /alerts/{alert_id}`、`PATCH /alerts/{alert_id}/status` 和 `POST /alerts/evaluate` 要求 bearer auth。
- [ ] `GET /sources`、`GET /sources/{source_id}`、`GET /sources/jobs` 和 `PATCH /sources/{source_id}/status` 要求 bearer auth。
- [ ] `GET /exports/intelligence.csv`、`GET /exports/intelligence/{intelligence_id}/markdown`、`GET /exports/alerts.csv` 和 `GET /exports/summary.pdf` 要求 bearer auth。

## 请求处理

- [ ] 合法请求返回已记录状态码。
- [ ] 非法请求返回确定性错误响应。
- [ ] 缺失必填字段已测试。
- [ ] 不支持的筛选器或值已测试。
- [ ] 已实现的分页或结果上限已测试。
- [ ] Intelligence sorting 对 `recent`、`first_seen`、`risk_score` 和 `severity` 保持稳定。
- [ ] Alert sorting 对 `recent` 和 `risk_level` 保持稳定。

## 安全

- [ ] 认证成功路径已测试。
- [ ] 认证失败路径已测试。
- [ ] 管理员专用路由的授权失败已测试。
- [ ] 响应不包含未脱敏凭证、Token、私有个人数据或批量 VIN 数据。

## 情报行为

- [ ] Search filters 只使用已实现字段。
- [ ] Source attribution 在预期位置出现。
- [ ] Intelligence responses 不包含 raw payload fields 和 collector secrets。
- [ ] Export endpoints 生成 CSV、Markdown 和 PDF 响应，并包含下载 headers 与已记录 content types。
- [ ] Export endpoints 在适用时遵守已实现 intelligence 和 alert filters。
- [ ] Export outputs 省略 raw payloads、不安全 metadata、credentials、tokens 和疑似密钥值。
- [ ] Alert trigger evaluation 覆盖 critical intelligence、KEV 或 known exploited signals、高风险车辆关键组件、same-CVE multi-source observations 和短时间 vendor/component bursts。
- [ ] Alert evaluation 不为同一 intelligence record 和 triggering rule 创建重复 alerts。
- [ ] Alert detail responses 包含安全 intelligence source attribution，并省略敏感 metadata。
- [ ] Alert status updates 写入包含 before/after status 和 notes 的 audit events。
- [ ] Source status responses 暴露 sync state、failure counts、retry/skipped metadata 和 recent job counters，且不泄露 source credentials。
- [ ] Source status updates 写入包含 before/after source status 的 audit events。
- [ ] Deduplication 和 scoring behavior 在适用时通过 API-visible outcomes 得到验证。
