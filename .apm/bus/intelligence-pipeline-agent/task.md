---
stage: 10
task: 3
agent: intelligence-pipeline-agent
log_path: ".apm/memory/stage-10/task-10-03.log.md"
has_dependencies: false
---

# Task 10.3 - 垂直信源扩展（NHTSA 召回 + vendor 端点）

## 背景

Stage 10 扩展垂直信源，经 Manager 评审确认范围：A 补 vendor-advisories 端点（零代码）+ B 新增 NHTSA 召回 connector。**通用威胁情报库全部搁置**，不做。本任务只改 worker 侧（connector/normalizer/配置/测试），后端访客只读由 Task 10.1 并行做，两者文件不重叠。

## 范围决策（务必遵守）

- **NHTSA 召回归 `incident`** 情报类型（不是 `vulnerability`，召回不是 CVE）。软件/OTA 相关召回打 `recall` + `software_related` 标签；机械类召回在采集层过滤，不进库。
- **vehicle 端点唯一可用**：`https://api.nhtsa.gov/recalls/recallsByVehicle?make=&model=&modelYear=`（免 key，UA `SentinelDrive/0.1` 可过）。`recallsByMake` 与 `campaigns` 端点需认证（403），不可用——不能做"全量监控所有厂商"，必须按车辆清单。
- **车辆清单配置化**（`metadata.vehicles`）：默认 Tesla 全系 5 台 + Rivian R1T/R1S + Chevy Bolt EV/EUV，近 4 个 model year（每轮约 36 请求）。
- **model 名必须用 VPIC 规范名**（Bolt EV 不是 BOLT、Model 3 不是 MODEL3）；存在数据缺口时 `Count=0` 要宽容，不当错误处理。
- **降噪在采集层**：用 `overTheAirUpdate` 布尔位 + Component/Summary 关键词（software/telematics/cyber/OTA 等）打 `software_related` 标记；非软件相关召回过滤掉。
- **去重**：campaign number（如 `22V063000`）做 `external_id`；cursor 存 `seen_campaigns` 集合，跨轮次幂等。
- **留存**：API JSON 走 `raw_payload` 模式（与 NVD 一致）。
- **无敏感数据**：不采集/不回传任何含 VIN、PII 的字段（`recallsByVehicle` 返回公开召回 campaign 信息，本身无 VIN，但需确认不回传任何可疑字段）。

## Workspace

- 从 `main` 创建功能分支 `feat/nhtsa-recalls-connector`
- 只提交本任务自身产出（`worker/` 下代码/测试/配置）；`.apm/`、`web3开发/`、`backend/`、`frontend*` 不提交

## 实现要求

1. 新增 `worker/sentineldrive_worker/connectors/nhtsa_recalls.py`（或并入既有 connector 模块，保持与现有结构一致）：实现 `NhtsaRecallsConnector`，复用 `HttpClient`、`RawIntelligencePayload`、`ConnectorError`。
2. 在 registry 注册 `nhtsa-recalls`（对齐既有 `samples.py` 里的注册方式）。
3. 源特定 normalizer/映射：把软件相关召回归 `incident`，字段映射（cve/external_id 等按召回语义），tags 打 `recall`+`software_related`，保留 `SourceAttribution`。确认现有 `NormalizerRegistry` 的解析路径能按 `source_name`/`connector` 命中，或显式注册。
4. 扩充 `worker/sentineldrive_worker/connectors/config.py` 的 `DEFAULT_VENDOR_ENDPOINTS`，加入 4 个实测可进的厂商：Vector Informatik（`vector.com/en/services/security-advisories/`）、Wind River（`windriver.com/security`）、Geely GSRC（`security.geely.com/`）、小米 SRC（`trust.mi.com/zh-CN/misrc/response`）。**不要加** QNX（301）、ASRG（SPA）、Mercedes（403）。
5. 新增环境变量 `SOURCE_ENABLED_NHTSA_RECALLS`（默认 `false`），并接入 `_default_env_sources`（reference 既有 `SOURCE_ENABLED_VENDOR_ADVISORIES` 的默认关闭策略）。

## 测试

在 `worker/tests/` 新增 mock 测试（不触真实网络），覆盖：
- happy path：`recallsByVehicle` 返回含软件相关召回的条目，解析正确、campaign number 做 external_id
- 403 / 畸形 JSON / 字段缺失：抛 `ConnectorError` 或宽容处理（`Count=0` 返回空而非错误）
- 车辆间隔离：单一车辆失败不影响其他车辆
- 软件相关过滤：`overTheAirUpdate` 或关键词命中才标记/入库，机械召回被过滤
- 幂等：重复 campaign 跨轮次不重复产出
- vendor 端点扩充后配置可解析
运行 `.venv/bin/python -m pytest worker/tests -q`（或仓库根）确认无回归。

## 明确排除

- 不做通用威胁情报库、不引入新的通知/工单/AI 分析
- 不改后端、前端、docker-compose

## 报告要求

完成后写入 `.apm/memory/stage-10/task-10-03.log.md`（frontmatter：stage/task/title/agent/status/important_findings/compatibility_issues），并向 `.apm/bus/intelligence-pipeline-agent/report.md` 提交 Task Report（Summary / Details / Output / Validation / Issues）。若发现 NMTSA 端点行为与任务描述有出入，在 Important Findings 中如实记录。