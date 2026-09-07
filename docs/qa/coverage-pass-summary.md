# 自动化测试覆盖总结

日期：2026-05-21

## 范围

本轮汇总并巩固当前 MVP backend、worker pipeline、frontend workbench、configuration、Compose rendering 和 documentation command surface 的自动化覆盖。未新增宽泛产品功能或 live integration checks。

## 盘点

| 区域 | Test or check surface | 覆盖总结 |
| --- | --- | --- |
| Backend API and services | `backend/tests/` | 69 个测试覆盖 health/readiness、auth/session/user basics、admin bootstrap、manual entry、intelligence search/detail、alerts、source status/job logs、exports、settings、models 和 migration contents。 |
| Worker pipeline | `worker/tests/` | 57 个测试覆盖 Connector contracts、mocked NVD/CISA/RSS/vendor sources、raw persistence、source status/job logs、normalization/deduplication/source attribution 和 fixed risk scoring。 |
| Frontend workbench | `frontend/src/pages/`, `frontend/src/services/`, `pnpm build`, `pnpm e2e` | 生产 `max build` 静态构建覆盖 route tree。Playwright 浏览器工作流用 mocked API data 覆盖 login-gated access、intelligence list/detail/export、external ingest record rendering、manual entry validation、source pipeline trigger、alert status updates 和 dashboard stats/empty state。 |
| Configuration and Compose | `scripts/config-check.sh`, `docker-compose.yml`, `Makefile` | 直接检查验证 development config rules 和 rendered Compose service wiring。 |
| Documentation and QA | `docs/testing.md`, `docs/qa/*.md` | 测试指南包含 CI-ready commands、acceptance-area coverage map、expected pass criteria 和 residual risks。 |

## 已运行命令

| Command | Result |
| --- | --- |
| `cd backend && ../.venv/bin/python -m pytest tests -q` | 通过：69 tests，存在 1 个 Starlette dependency 的 `python_multipart` pending deprecation warning。 |
| `.venv/bin/python -m pytest worker/tests -q` | 通过：57 tests。 |
| `cd frontend && pnpm build` | 通过：`max build` 完成 `/dashboard`、`/intelligence`、`/alerts`、`/sources`、`/manual-entries`、`/user/login` 等路由的静态产物。 |
| `cd frontend && pnpm e2e` | 通过：9 个 Playwright browser tests，使用确定性 mocked `/api/*` responses。 |
| `cd frontend && pnpm audit --omit=dev` | 通过：0 个生产依赖漏洞。 |
| `make config-check` | development environment 下通过。 |
| `make compose-config` | 通过：Compose 成功渲染。 |

## 新增或变更测试

在 `frontend/e2e/operator-workflows.spec.ts` 和 `frontend/playwright.config.ts` 中新增 Playwright 浏览器工作流覆盖。Suite 启动本地 Umi dev server，并在浏览器中拦截 `/api/*` 请求，因此工作流确定且不需要 live source collection、backend credentials、PostgreSQL、Redis 或 Celery。

## 文档变更

- 更新 `docs/testing.md`，加入 CI-ready command list、精确 pass criteria、acceptance-area coverage map 和 residual risk list。
- 更新 `docs/qa/frontend-page-checklist.md`，引用可运行浏览器工作流 suite。
- 更新本 QA summary：`docs/qa/coverage-pass-summary.md`。

## 残余风险

- Frontend browser workflow validation 使用 mocked `/api/*` responses。它验证 UI behavior 和 endpoint wiring，但不能证明 live backend、reverse-proxy、PostgreSQL、Redis、worker 或 scheduler integration。
- Browser tests 尚未覆盖 logout/session expiry、mocked API failure rendering、responsive layout、generated PDF visual rendering 或深层 search/filter edge cases。
- Docker runtime validation 不由 `make compose-config` 覆盖。完整 `make up`、reverse-proxy routing、Docker 内 PostgreSQL/Redis readiness、worker execution 和 scheduler behavior 需要 Docker daemon。
- Live NVD/CISA/RSS/vendor source checks 有意排除在自动化测试外。它们应作为 opt-in operator validation，需要显式 credentials 和 network access。
- Live PostgreSQL migration execution 不在 unit suite 中覆盖。当前测试检查 migration contents 和 model metadata；部署验证应对隔离 PostgreSQL 实例运行 migrations。
- Export file rendering 已通过 backend response 测试，CSV download initiation 已通过 browser 测试。Visual PDF rendering 不在当前矩阵内。

## 后续推荐覆盖

- 增加在具备 Docker 的基础设施上运行 Compose startup checks 的部署验证 job。
- 增加默认关闭的 opt-in live Connector smoke test profile，要求显式 credentials/network configuration。
