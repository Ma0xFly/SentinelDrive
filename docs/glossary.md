# 术语表

本表约定全项目（代码文案、文档、前端界面）统一使用的中英文术语。新增文案或文档时请遵循本表；如需调整译法，先更新本表再全库同步。

## 核心术语

| 英文 | 统一中文译法 | 不要使用 | 说明 |
| --- | --- | --- | --- |
| threat intelligence | 威胁情报 | 保留英文不译 | 全库统一。 |
| intelligence item / entry | 情报条目 | 核心情报记录、人工条目 | 单条情报记录的统称。 |
| source | 数据源 | 信息源 | 包括 NVD、CISA KEV、RSS、厂商公告等。 |
| data source management | 数据源管理 | 信息源管理 | 前端页面与文档统一。 |
| manual entry | 人工录入 | 手工录入、手工补录、人工情报 | 功能名为「人工录入」，单条记录为「人工录入条目」。 |
| alert | 告警 | 报警 | 全库统一。 |
| open alert | 未关闭告警 | 打开告警 | open 在此为"未关闭"状态，非动词。 |
| connector | Connector（保留英文） | 采集器 | 代码与文档统一保留英文。 |
| normalization / normalize | 规范化 | 标准化 | 流水线阶段名。 |
| deduplication / dedup | 去重 | — | — |
| scoring | 评分 / 风险评分 | — | 流水线阶段名「评分」。 |
| risk level | 风险等级 | — | 取值：信息/低/中/高/严重。 |
| risk score | 风险评分 / 风险分 | — | 0-100 数值。 |
| severity | 严重度 | 严重性 | 与风险等级区分。 |
| exploit status | 利用状态 | — | 取值：未知/未发现利用/PoC/已利用。 |
| known exploited | 在野利用（已知在野利用） | 已知被利用 | 行业标准译法，见 CISA KEV 语境。 |
| source confidence | 数据源可信度 | 来源信心 | 取值：低/中/高。 |
| vehicle-critical component | 车控关键组件 | 车辆关键部件 | — |
| retention | 留存 | 保留 | 全库统一。 |
| source attribution | 数据源归属 | 来源归属 | — |
| API base URL | API 基址 | 接口 | 前端登录页与页脚统一为「API 基址」。 |
| readiness | 就绪 | — | `/ready` 端点语境。 |
| pipeline | 流水线 | 管道 | 采集-规范化-评分处理链。 |

## 枚举值展示约定

数据库、API 字段和枚举值（如 `open`、`acknowledged`、`critical`、`tbox`）在代码、接口和导出数据中**一律保留英文原值**，保证契约稳定和机器可处理；中文标签只在前端展示层映射，统一维护在 `frontend/app/intelligence/labels.js`，不要在组件内新建重复映射。

## 标点与格式约定

- 中文文档使用直角引号「」或弯引号“”时，同一文档内保持一致；推荐直角引号。
- 文档统一使用 LF 换行、UTF-8 无 BOM 编码。
- 保留英文的技术词：Docker Compose 服务名（backend/worker/scheduler/frontend）、Celery、PostgreSQL、Redis、Caddy、RSS、CVE、CVSS、KEV。
