# Connector 行为 Checklist

## 配置

- [ ] Connector 有明确 `SourceConfig` 加载路径。
- [ ] 必需和可选环境变量已记录。
- [ ] 缺失可选凭证时行为已定义。
- [ ] 凭证和 private headers 保存在 `credentials` 或 `headers` 中，日志会脱敏。

## 抓取

- [ ] 成功 fetch 已测试。
- [ ] Non-2xx 响应已测试。
- [ ] Timeout 已测试。
- [ ] Retry exhaustion 已测试。
- [ ] Rate limit behavior 已测试。
- [ ] 外部网络在自动化测试中被 mock。

## 解析与持久化

- [ ] Malformed response body 已测试。
- [ ] `RawIntelligencePayload` 包含 source name、source type、source URL、fetch timestamp 和 hashes。
- [ ] HTML/PDF 来源默认 metadata-only retention。
- [ ] Source failure 不阻塞其他 sources。
- [ ] Sync cursor 只在成功运行后推进。

## 规范化与重处理

- [ ] Normalizer 或 fallback 行为已定义。
- [ ] 同一 CVE、URL、title/source 或 hash 的重复输入不会创建重复核心情报。
- [ ] Source attribution 会合并并更新 `last_seen_at`。
- [ ] 失败 raw row 只标记自身失败，错误信息脱敏。
