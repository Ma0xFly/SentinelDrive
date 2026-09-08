# SentinelDrive

**车联网（Connected Vehicle）威胁情报工作台** —— 面向汽车软件与网络安全运营的中文工作台。系统从公开漏洞库、厂商安全公告、车辆召回等信源汇聚情报，经规范化、去重、评分后形成结构化的威胁情报库，支撑威胁态势可视化、告警处置与人工研判。

本仓库提供单台 Linux 服务器可部署的 Docker Compose 运行栈：Ant Design Pro 前端工作台、FastAPI 后端、Celery 采集与处理管道、PostgreSQL 存储、Redis 缓存/broker 和 Caddy 反向代理。

---

## 功能特性

- **威胁态势总览**：情报总数、近期新增、告警与启用来源统计卡片，近 30 天情报趋势、严重度分布、情报类型占比、告警状态分布与来源覆盖 Top 10 图表。
- **威胁情报库**：结构化情报列表（按 CVE、厂商、产品、组件、攻击面、风险等级、标签、来源、状态等筛选与排序）与详情页（来源归因、评分解释、关联告警、去重键），支持 CSV/Markdown/PDF 导出。
- **告警处置**：固定规则自动产生告警（关键情报、已知被利用漏洞、高风险车辆关键组件、多来源 CVE、厂商/组件集中爆发），支持带备注的状态流转与复核。
- **数据源管理**：查看各信源启用状态、最近同步、失败次数与最近错误，查看任务日志，启停信源并手动触发采集/处理管道。
- **手工录入**：支持漏洞、公告、事件、暴露面、研究线索五类情报的分组表单录入，带契约级校验并自动接入规范化/去重/评分流程。
- **用户与审计**：管理员初始化、用户管理，关键动作写审计日志；认证使用无状态 HMAC 签名 Token。
- **访客只读**：未登录可匿名浏览态势总览、威胁情报（列表与详情）和数据源公开字段；写操作、导出、告警处置、用户管理与信源运维需登录。
- **安全边界**：PostgreSQL / Redis / worker / scheduler 保持内部网络，仅 reverse-proxy 暴露公网；NVD API Key 可选（无 Key 时自动严格限速）；不展示或导出未脱敏凭证与敏感原始数据。

---

## 架构

### 服务组成

| 服务 | 职责 | 公网暴露 |
| --- | --- | --- |
| `reverse-proxy` | Caddy 公共入口，路由 `/` 到前端、`/api/*` 到后端 | 宿主机 HTTP/HTTPS 端口 |
| `frontend` | Ant Design Pro 中文工作台（nginx 静态托管） | 仅内部 |
| `backend` | FastAPI API：认证、情报、告警、数据源、手工录入、导出、统计、审计 | 仅内部 |
| `worker` | Celery Worker：Source Connector 采集、规范化、去重、评分 | 内部（出站采集） |
| `scheduler` | Celery Beat：定时派发同步与处理任务 | 内部（出站采集） |
| `postgres` | PostgreSQL 16 持久化存储 | 内部 |
| `redis` | Redis 7 缓存 / broker / result backend | 内部 |

只有 `reverse-proxy` 发布宿主机端口；其余服务位于内部 Compose 网络，`worker`/`scheduler` 额外连接 `egress` 网络用于出站采集。

### 数据流

```mermaid
flowchart LR
    A[Source Connectors<br/>NVD / CISA KEV / RSS / 厂商公告] --> B[Raw Intelligence<br/>原始情报]
    B --> C[Normalize 规范化]
    C --> D[Deduplicate 去重]
    D --> E[Threat Intelligence<br/>规范化情报]
    E --> F[Score 风险评分]
    F --> G[Alert 告警评估]
    E --> H[搜索 / 详情 / 导出]
    F --> H
    G --> I[告警工作台]
    H --> J[态势总览仪表盘]
```

采集由 `worker` 按定时或手动触发执行，规范化、去重、评分在 `worker` 侧完成，告警评估位于 `backend` 侧；每个阶段可独立重放（`make process-once`）。

### 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 19 · Ant Design Pro v6（Umi Max 4 · antd 6 · utoopack · Tailwind CSS v4）· pnpm/Node 22 |
| 后端 | FastAPI · SQLAlchemy 2.x · Alembic · PostgreSQL 16 · Redis 7 |
| 处理 | Celery Worker + Beat · 标准库 HTTP 采集 · XML/JSON 解析 |
| 交付 | Docker Compose · Caddy 反向代理 · nginx 静态托管 |
| 质量 | pytest · Playwright E2E · Biome/TypeScript · vitest |

---

## 快速开始

### 前置条件

- Ubuntu 22.04 或更新版本（目标资源：4 核 CPU / 4 GB 内存 / 40 GB SSD）
- Docker Engine 与 Docker Compose v2
- GNU Make

### 部署与初始化

```bash
# 拉取代码并进入目录
git clone git@github.com:Ma0xFly/SentinelDrive.git sentineldrive
cd sentineldrive

# 准备环境文件并至少替换占位密钥
cp .env.example .env
```

生产部署时，将 `.env` 中以下占位值替换为部署环境专用密钥（本地开发可保留安全占位值）：

```env
APP_ENV=production
APP_SECRET_KEY=replace-with-a-strong-random-secret
POSTGRES_PASSWORD=replace-with-a-strong-database-password
DATABASE_URL=postgresql+psycopg://sentineldrive:replace-with-a-strong-database-password@postgres:5432/sentineldrive
ADMIN_BOOTSTRAP_EMAIL=admin@example.com
ADMIN_BOOTSTRAP_PASSWORD=replace-with-a-strong-admin-password
CADDY_HOST=sentineldrive.example.com
CADDY_TLS_EMAIL=security@example.com
```

仅做本地 HTTP 预览时，可改用：

```env
CADDY_HOST=:80
CADDY_TLS_EMAIL=
```

校验配置、构建并启动：

```bash
make config-check
make compose-config
docker compose up -d --build
make migrate
make admin-bootstrap
```

检查健康状态：

```bash
curl -fsS "http://127.0.0.1/api/health"   # 进程存活
curl -fsS "http://127.0.0.1/api/ready"    # PostgreSQL/Redis 就绪
docker compose ps
```

浏览器访问 `http://你的服务器IP`（或 `https://你的域名`）。

### 首次登录

管理员账号来自 `.env` 的 `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`。密码只用于初始化或更新管理员，系统保存的是密码哈希；不要把 `.env` 提交到 Git，也不要把真实密码写入文档。

```text
Email:    admin@example.test   （默认开发占位）
Password: change-me-development-only  （默认开发占位）
```

---

## 使用指南

未登录时以**访客模式**进入，可只读浏览三个公开页：**态势总览**、**威胁情报**（列表与详情）和**数据源**（公开字段）。右上角显示「访客模式」提示与「登录」按钮，登录后自动回跳原页面。

登录后左侧导航包含六个工作台页面：

- **态势总览**：情报/告警/来源统计卡片与四类图表，是运营首屏。
- **威胁情报**：列表页支持全参数筛选、排序、分页与 CSV 导出；点击行进入详情页查看来源归因、评分解释、关联告警与去重键，可导出 Markdown/PDF。
- **告警**：按状态/风险等级筛选，抽屉查看详情，带备注进行状态流转（未确认 → 已确认/已关闭）。
- **数据源**：查看各信源同步状态与失败原因，查看任务日志，启停信源，手动触发同步/处理管道（会二次确认）。
- **手工录入**：分组表单录入漏洞/公告/事件/暴露面/研究线索，带中文校验；提交后自动进入规范化与评分流程。
- **用户管理**：管理员创建或停用用户。

管理员可通过右上角进入 **用户管理** 创建或停用用户。未登录访问受保护页面会跳转登录页。

---

## 数据源与情报处理

### 情报类型

规范化情报分为四类：`vulnerability`（漏洞）、`exposure`（暴露面）、`incident`（事件）、`advisory`（公告）。

### 内置信源

| 信源 | 类型 | 默认状态 | 说明 |
| --- | --- | --- | --- |
| NVD | 官方 API | 开 | CVE 漏洞库，可选 API Key，无 Key 时严格限速 |
| CISA KEV | 官方 JSON | 开 | 已知被利用漏洞目录 |
| RSS/Atom | 可配置 feed | 开（空） | 通过 `SOURCE_RSS_FEEDS` 配置 |
| 厂商公告 | HTML 元数据 | 关 | 比亚迪 / 蔚来 / 理想 / 高通 / 博世 / Vector Informatik / Wind River / Geely / Xiaomi 安全公告入口，轻量元数据留存 |
| NHTSA 召回 | 免认证 API | 关 | 按配置车辆清单查询软件/OTA 相关召回，机械类召回在采集层过滤 |

数据源通过环境变量配置（启用开关、RSS feed 列表、厂商端点 JSON），详细见 [数据源配置](docs/source-configuration.md) 与 [环境变量参考](docs/environment.md)。

### 采集与处理

```bash
make sync-once      # 只执行采集：写入 source/job/raw 数据
make process-once   # 采集 + 规范化 + 去重 + 评分 + 后端告警评估
```

采集由 worker 定时（Celery Beat，默认 1 小时）或 `make sync-once` 触发。处理管道为「采集 → 原始情报 → 规范化 → 去重 → 威胁情报 → 评分 → 告警」，各阶段独立、可重放、幂等；重复输入不会产生重复核心情报记录。

### 评分与告警

风险评分使用固定规则（CVSS 分数、CISA KEV/已知被利用、车辆关键组件、多厂商影响、远程可利用性等），输出 0–100 分数与 Critical/High/Medium/Low 等级，并带可解释的评分因素。告警规则覆盖关键情报、已知被利用漏洞、高风险车辆关键组件、多来源 CVE 与厂商/组件短期集中爆发；告警不发送外部通知，由工作台处置。

---

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `make config-check` | 校验环境配置占位规则（不打印密钥） |
| `make compose-config` | 渲染并校验 `docker-compose.yml` |
| `docker compose up -d --build` | 后台构建并启动运行栈 |
| `make logs` | 跟随查看 Compose 日志 |
| `make migrate` | 应用数据库迁移 |
| `make admin-bootstrap` | 创建/更新初始管理员 |
| `make sync-once` | 执行一次数据源采集 |
| `make process-once` | 执行一次完整处理路径（采集→规范化→评分→告警评估） |
| `make backend-test` | 运行后端测试 |
| `make frontend-check` | 前端生产构建检查 |
| `make down` | 停止运行栈（不删持久化卷） |

---

## 配置

所有服务配置来自环境变量（`.env`，从 `.env.example` 复制）。关键变量：

- 认证与安全：`APP_SECRET_KEY`、`ADMIN_BOOTSTRAP_EMAIL`、`ADMIN_BOOTSTRAP_PASSWORD`
- 数据库与缓存：`DATABASE_URL`、`REDIS_URL`、`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`
- 数据源：`NVD_API_KEY`、`SOURCE_ENABLED_*`、`SOURCE_RSS_FEEDS`、`SOURCE_VENDOR_ADVISORY_ENDPOINTS`
- 反向代理：`CADDY_HOST`、`CADDY_TLS_EMAIL`、`REVERSE_PROXY_HTTP_PORT`、`REVERSE_PROXY_HTTPS_PORT`

完整变量说明见 [环境变量参考](docs/environment.md)。**不要把真实密钥提交到仓库**。

---

## 文档索引

- [Ubuntu Docker Compose 部署指南](docs/deployment.md)
- [运维手册（备份/恢复/维护）](docs/operations.md)
- [本地开发指南](docs/development.md)
- [测试与 QA 指南](docs/testing.md)
- [环境变量参考](docs/environment.md)
- [Connector 开发指南](docs/connectors.md)
- [数据源配置示例](docs/source-configuration.md)
- [外部与 AI 情报接入](docs/external-ingest.md)
- [术语表](docs/glossary.md)
- [Compose 部署验证](docs/qa/compose-deployment-verification.md)

---

## 实现状态

运行栈已包含：工作台五个页面与访客只读面、态势总览仪表盘、认证与用户管理、情报搜索/详情/导出、人工录入、告警生成与处置、数据源管理与运维触发、Source Connector 运行时（NVD/CISA KEV/RSS/厂商公告/NHTSA 召回）、规范化去重评分管道、审计日志与聚焦测试。数据库 bootstrap 后默认为空，可通过人工录入或启用数据源同步添加数据。
