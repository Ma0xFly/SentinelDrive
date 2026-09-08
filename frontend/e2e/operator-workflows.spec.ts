import { expect, test, type Page, type Route } from '@playwright/test';

const USER = {
  id: '00000000-0000-4000-8000-000000000001',
  email: 'admin@example.test',
  display_name: '安全运营员',
  is_admin: true,
  is_active: true,
  created_at: '2026-05-21T00:00:00Z',
  updated_at: '2026-05-21T00:00:00Z',
  last_login_at: '2026-05-21T00:00:00Z',
};

const INTELLIGENCE_ID = '11111111-1111-4111-8111-111111111111';
const EXTERNAL_INGEST_ID = '88888888-8888-4888-8888-888888888888';
const ALERT_ID = '22222222-2222-4222-8222-222222222222';
const SOURCE_ID = '33333333-3333-4333-8333-333333333333';
const MANUAL_ENTRY_ID = '44444444-4444-4444-8444-444444444444';
const NOW = '2026-05-21T08:00:00Z';
const TEST_TOKEN = 'browser-test-token';

test.beforeEach(async ({ page }) => {
  const state = {
    alertStatus: 'open',
    alertNotes: '等待值班确认。',
    manualEntries: [] as any[],
  };

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, '') || '/';
    const method = request.method();

    if (method === 'POST' && path === '/auth/login') {
      return json(route, { access_token: TEST_TOKEN, token_type: 'bearer' });
    }
    if (request.headers().authorization !== `Bearer ${TEST_TOKEN}`) {
      return json(
        route,
        { detail: { error: { code: 'not_authenticated', message: '登录状态已过期，请重新登录。' } } },
        401,
      );
    }
    if (method === 'GET' && path === '/auth/me') return json(route, USER);
    if (method === 'POST' && path === '/auth/logout') return json(route, { status: 'ok' });

    // Intelligence
    if (method === 'GET' && path === '/intelligence') {
      const tag = url.searchParams.get('tag');
      if (tag === 'external_ingest') {
        return json(route, pageResponse([externalIngestSummary()]));
      }
      return json(route, pageResponse([intelligenceSummary()]));
    }
    if (method === 'GET' && path === `/intelligence/${INTELLIGENCE_ID}`) {
      return json(route, intelligenceDetail());
    }
    if (method === 'GET' && path === `/intelligence/${EXTERNAL_INGEST_ID}`) {
      return json(route, externalIngestDetail());
    }
    if (method === 'GET' && path === '/exports/intelligence.csv') {
      return route.fulfill({
        status: 200,
        headers: {
          'content-type': 'text/csv; charset=utf-8',
          'content-disposition': 'attachment; filename="sentineldrive-intelligence.csv"',
        },
        body: `id,title\n${INTELLIGENCE_ID},Mocked OTA risk\n`,
      });
    }
    if (method === 'GET' && path === `/exports/intelligence/${INTELLIGENCE_ID}/markdown`) {
      return route.fulfill({
        status: 200,
        headers: {
          'content-type': 'text/markdown; charset=utf-8',
          'content-disposition': 'attachment; filename="intelligence-11111111-1111-4111-8111-111111111111.md"',
        },
        body: '# Mocked OTA risk\n\nDeterministic browser test intelligence item.\n',
      });
    }
    if (method === 'GET' && path === '/exports/summary.pdf') {
      return route.fulfill({
        status: 200,
        headers: {
          'content-type': 'application/pdf',
          'content-disposition': 'attachment; filename="sentineldrive-summary.pdf"',
        },
        body: '%PDF-1.4\n%browser-test\n',
      });
    }

    // Alerts
    if (method === 'GET' && path === '/alerts') return json(route, pageResponse([alertSummary(state)]));
    if (method === 'GET' && path === `/alerts/${ALERT_ID}`) return json(route, alertDetail(state));
    if (method === 'PATCH' && path === `/alerts/${ALERT_ID}/status`) {
      const payload = await request.postDataJSON();
      state.alertStatus = payload.status;
      if ('notes' in payload) {
        state.alertNotes = payload.notes;
      }
      return json(route, alertDetail(state));
    }
    if (method === 'POST' && path === '/alerts/evaluate') {
      return json(route, { created: 1, updated: 0, alert_ids: [ALERT_ID] });
    }

    // Sources
    if (method === 'GET' && path === '/sources') return json(route, pageResponse([sourceSummary()]));
    if (method === 'GET' && path === `/sources/${SOURCE_ID}`) return json(route, sourceDetail());
    if (method === 'GET' && path === '/sources/jobs') return json(route, pageResponse([sourceJob()]));
    if (method === 'GET' && path === '/sources/pipeline/status') return json(route, pipelineStatus());
    if (method === 'POST' && path === '/sources/pipeline/trigger') {
      return json(
        route,
        {
          job_id: '55555555-5555-4555-8555-555555555555',
          celery_task_id: 'pipeline-browser-test',
          task_name: 'sentineldrive.process_pipeline',
          status: 'queued',
          message: '处理流水线已加入队列。',
        },
        202,
      );
    }
    if (method === 'PATCH' && path === `/sources/${SOURCE_ID}/status`) return json(route, sourceDetail());

    // Manual entries
    if (method === 'GET' && path === '/manual-entries') return json(route, state.manualEntries);
    if (method === 'POST' && path === '/manual-entries') {
      const payload = await request.postDataJSON();
      const entry = {
        ...payload,
        id: MANUAL_ENTRY_ID,
        created_by_user_id: USER.id,
        created_at: NOW,
        updated_at: NOW,
      };
      state.manualEntries = [entry];
      return json(route, entry, 201);
    }

    // Stats overview (dashboard)
    if (method === 'GET' && path === '/stats/overview') return json(route, statsOverview(url));

    return json(
      route,
      { detail: { error: { code: 'unmocked_route', message: `${method} ${path}` } } },
      500,
    );
  });
});

test('登录守卫拦截未认证访问，登录后导航到情报详情并支持导出', async ({ page }) => {
  await page.goto('/');
  // Umi dev 首次编译冷启动较慢；等登录页标题文本出现（而不是 URL，因为
  // 编译期间页面可能仍显示 "Bundling..."）
  await page.getByText('SentinelDrive 安全运营台').waitFor({ state: 'visible', timeout: 60_000 });
  await expect(page).toHaveURL(/\/user\/login/);

  await page.getByPlaceholder('邮箱').fill(USER.email);
  await page.getByPlaceholder('密码').fill('local-test-password');
  await page.getByRole('button', { name: /登\s*录/ }).click();

  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByText('态势总览').first()).toBeVisible();

  await page.goto('/intelligence');
  await expect(page.getByText('威胁情报').first()).toBeVisible();

  await page.getByText('Mocked OTA risk').first().click();
  await expect(page).toHaveURL(new RegExp(`/intelligence/${INTELLIGENCE_ID}`));
  await expect(page.getByText('Mocked OTA risk')).toBeVisible();
  await expect(page.getByText('来源归因').first()).toBeVisible();

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出 Markdown' }).click();
  expect((await download).suggestedFilename()).toMatch(/\.md$/);
});

test('情报列表支持 CSV 导出与数据源归属展示', async ({ page }) => {
  await login(page);
  await page.goto('/intelligence');
  await expect(page.getByText('Mocked OTA risk')).toBeVisible();

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出 CSV' }).click();
  expect((await download).suggestedFilename()).toBe('intelligence.csv');
});

test('外部/AI ingest 记录在情报列表与详情页正确渲染', async ({ page }) => {
  // 覆盖 intelligence 默认 mock：当请求带 tag=external_ingest 时返回 ingest 记录
  await page.unroute('**/api/intelligence');
  await page.route('**/api/intelligence**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, '');
    if (path === `/intelligence/${EXTERNAL_INGEST_ID}`) {
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(externalIngestDetail()),
      });
    }
    if (url.searchParams.get('tag') === 'external_ingest') {
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(pageResponse([externalIngestSummary()])),
      });
    }
    return route.fulfill({
      status: 200,
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(pageResponse([intelligenceSummary()])),
    });
  });
  await login(page);
  await page.goto('/intelligence');
  await expect(page.getByText('Mocked OTA risk')).toBeVisible();

  // 在搜索区输入 tag 并查询
  await page.getByLabel('标签').fill('external_ingest');
  await page.getByRole('button', { name: /查\s*询/ }).click();

  // 查询后用表格行定位（fixed 列副本与可见行并存，用 tbody 内的行）
  const row = page.locator('.ant-table-tbody tr.ant-table-row').filter({ hasText: 'Mocked external AI advisory' }).first();
  await expect(row).toBeVisible();
  await row.locator('a').click();
  await expect(page).toHaveURL(new RegExp(`/intelligence/${EXTERNAL_INGEST_ID}`));
  await expect(page.getByText('来源归因').first()).toBeVisible();
  await expect(page.getByText('Mocked external AI advisory')).toBeVisible();

  await expect(page.locator('td').filter({ hasText: 'AI 情报收集器' }).first()).toBeVisible();
  await expect(page.getByText('ai-collector-2026-7777').first()).toBeVisible();
  await expect(page.getByText('cve:CVE-2026-7777').first()).toBeVisible();
  await expect(page.locator('.ant-tag').filter({ hasText: 'external_ingest' })).toBeVisible();
});

test('桌面视口布局无水平溢出', async ({ page }) => {
  await login(page);

  const viewports = [
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ];

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    // 已有 token，直接导航到 dashboard
    await page.goto('/dashboard');
    await expect(page.getByText('态势总览').first()).toBeVisible();
    await expect(page.locator('body')).not.toHaveHorizontalOverflow();

    await page.goto('/intelligence');
    await expect(page.getByText('Mocked OTA risk')).toBeVisible();
    await expect(page.locator('body')).not.toHaveHorizontalOverflow();

    await page.getByText('Mocked OTA risk').first().click();
    await expect(page.getByText('Mocked OTA risk')).toBeVisible();
    await expect(page.locator('body')).not.toHaveHorizontalOverflow();
  }
});

test('告警流转：打开详情、切换状态、关联情报可访问', async ({ page }) => {
  await login(page);
  await page.goto('/alerts');

  await expect(page.getByText('告警列表').first()).toBeVisible();

  await page.getByText('Critical mocked alert').first().click();
  const drawer = page.locator('.ant-drawer', { has: page.getByText('告警详情') });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText('打开关联情报')).toBeVisible();

  await drawer.getByRole('combobox').click();
  await page.getByText('已确认', { exact: true }).click();
  await drawer.getByRole('button', { name: '更新状态' }).click();

  await expect(drawer).toContainText('已确认');
});

test('数据源流水线：手动触发同步', async ({ page }) => {
  await login(page);
  await page.goto('/sources');

  await expect(page.getByText('采集数据源').first()).toBeVisible();
  await expect(page.getByText('NVD Mock Source')).toBeVisible();

  await page.getByRole('button', { name: '手动触发同步' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('手动触发采集管道');
  await dialog.getByRole('button', { name: '触发同步' }).click();
  await expect(page.getByText(/采集管道任务已提交/)).toBeVisible();
});

test('手工录入：校验拒绝空提交，成功提交后列表出现新条目', async ({ page }) => {
  await login(page);
  await page.goto('/manual-entries');

  await page.getByRole('button', { name: '手工录入' }).click();
  await expect(page.getByText('新建手工录入').first()).toBeVisible();

  // 空提交触发必填校验
  await page.getByRole('button', { name: /确\s*定/ }).click();
  await expect(page.getByText(/请输入标题|标题至少/)).toBeVisible();

  await page.getByPlaceholder('至少 3 个字符').fill('Mocked supplier advisory');
  await page.getByPlaceholder('一句话概述该情报的核心内容').fill('Browser workflow validates manual entry submission.');
  await page.getByPlaceholder('厂商公告、内部分析').fill('内部测试源');
  await page.getByRole('button', { name: /确\s*定/ }).click();

  await expect(page.getByText('手工录入「Mocked supplier advisory」提交成功')).toBeVisible();
  await expect(page.getByText('Mocked supplier advisory').first()).toBeVisible();
});

test('仪表盘：统计卡片展示非零数据，图表区域渲染', async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/dashboard/);

  await expect(page.getByText('情报总数')).toBeVisible();
  await expect(page.getByText('42').first()).toBeVisible();
  await expect(page.getByText('告警总数')).toBeVisible();
  await expect(page.getByText('7').first()).toBeVisible();
  await expect(page.getByText('启用中数据源')).toBeVisible();
  await expect(page.getByText('3').first()).toBeVisible();

  await expect(page.getByText('近 30 天情报新增趋势', { exact: true })).toBeVisible();
  await expect(page.getByText('严重度分布', { exact: true })).toBeVisible();
  await expect(page.getByText('情报类型占比', { exact: true })).toBeVisible();
  await expect(page.getByText('告警状态分布', { exact: true })).toBeVisible();

  await expect(page.locator('.g2-container, canvas, svg').first()).toBeVisible();
});

test('仪表盘：零值数据展示空态提示', async ({ page }) => {
  await page.route('**/api/stats/overview', (route) =>
    json(route, emptyStatsOverview()),
  );
  await login(page);
  await expect(page.getByText('暂无统计数据，情报与告警入库后将在此展示态势图表')).toBeVisible();
});

// -------- helpers --------

async function login(page: Page) {
  await page.goto('/');
  // Umi dev 首次编译冷启动较慢；等登录页标题文本出现（编译期间可能显示 "Bundling..."）
  await page.getByText('SentinelDrive 安全运营台').waitFor({ state: 'visible', timeout: 60_000 });
  await page.getByPlaceholder('邮箱').fill(USER.email);
  await page.getByPlaceholder('密码').fill('local-test-password');
  await page.getByRole('button', { name: /登\s*录/ }).click();
  await expect(page).not.toHaveURL(/\/user\/login/, { timeout: 15_000 });
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function pageResponse<T>(items: T[]) {
  return {
    items,
    total: items.length,
    page: 1,
    limit: 25,
    has_next: false,
    has_previous: false,
  };
}

function intelligenceSummary() {
  return {
    id: INTELLIGENCE_ID,
    title: 'Mocked OTA risk',
    summary: 'Deterministic browser test intelligence item.',
    intelligence_type: 'vulnerability',
    source_names: ['NVD Mock Source'],
    source_urls: ['https://example.test/advisory'],
    canonical_source_url: 'https://example.test/advisory',
    cve_id: 'CVE-2026-0001',
    cwe_id: null,
    cvss_score: 8.2,
    cvss_vector: null,
    severity: 'high',
    affected_vendor: 'Example Auto',
    affected_product: 'OTA Gateway',
    affected_version: null,
    vehicle_component: 'telematics',
    attack_surface: 'remote',
    exploit_status: 'proof_of_concept',
    confidence: 'high',
    risk_score: 82,
    risk_level: 'high',
    status: 'active',
    tags: ['mocked', 'e2e'],
    first_seen_at: NOW,
    last_seen_at: NOW,
    created_at: NOW,
    updated_at: NOW,
    metadata: {},
    score_metadata: {},
    score_explanation: null,
    sources: [],
    related_alert_count: 1,
  };
}

function intelligenceDetail() {
  return {
    ...intelligenceSummary(),
    raw_intelligence_id: null,
    external_ids: { cve_id: 'CVE-2026-0001' },
    dedup_key: 'cve:CVE-2026-0001',
    normalized_text_hash: 'abc123',
    score_explanation: 'Mocked scoring explanation.',
    score_metadata: { source_confidence: 'mocked' },
    sources: [
      {
        id: '66666666-6666-4666-8666-666666666666',
        source_name: 'NVD Mock Source',
        source_url: 'https://example.test/advisory',
        external_id: 'CVE-2026-0001',
        first_seen_at: NOW,
        last_seen_at: NOW,
      },
    ],
    related_alerts: [alertSummary({ alertStatus: 'open', alertNotes: '等待值班确认。' })],
  };
}

function externalIngestSummary() {
  return {
    id: EXTERNAL_INGEST_ID,
    title: 'Mocked external AI advisory',
    summary: 'Deterministic external/AI ingest browser test item.',
    intelligence_type: 'vulnerability',
    source_names: ['AI 情报收集器'],
    source_urls: ['https://collector.example.test/ingest/CVE-2026-7777'],
    canonical_source_url: 'https://collector.example.test/ingest/CVE-2026-7777',
    cve_id: 'CVE-2026-7777',
    cwe_id: null,
    cvss_score: 7.8,
    cvss_vector: null,
    severity: 'high',
    affected_vendor: 'Example Vendor',
    affected_product: 'External Collector',
    affected_version: null,
    vehicle_component: null,
    attack_surface: null,
    exploit_status: 'unknown',
    confidence: 'medium',
    risk_score: 78,
    risk_level: 'high',
    status: 'active',
    tags: ['external_ingest', 'ai_collector'],
    first_seen_at: NOW,
    last_seen_at: NOW,
    created_at: NOW,
    updated_at: NOW,
    metadata: {},
    score_metadata: {},
    score_explanation: null,
    sources: [],
    related_alert_count: 0,
  };
}

function externalIngestDetail() {
  return {
    ...externalIngestSummary(),
    raw_intelligence_id: null,
    external_ids: { cve_id: 'CVE-2026-7777', external_id: 'ai-collector-2026-7777' },
    dedup_key: 'cve:CVE-2026-7777',
    normalized_text_hash: 'abc456',
    sources: [
      {
        id: '99999999-9999-4999-8999-999999999999',
        source_name: 'AI 情报收集器',
        source_url: 'https://collector.example.test/ingest/CVE-2026-7777',
        external_id: 'ai-collector-2026-7777',
        first_seen_at: NOW,
        last_seen_at: NOW,
      },
    ],
    related_alerts: [],
  };
}

function alertSummary(state: { alertStatus: string; alertNotes: string }) {
  return {
    id: ALERT_ID,
    title: 'Critical mocked alert',
    threat_intelligence_id: INTELLIGENCE_ID,
    triggering_rule: 'critical_intelligence',
    risk_level: 'high',
    status: state.alertStatus,
    triggered_at: NOW,
    notes: state.alertNotes,
  };
}

function alertDetail(state: { alertStatus: string; alertNotes: string }) {
  return {
    ...alertSummary(state),
    intelligence: intelligenceSummary(),
  };
}

function sourceSummary() {
  return {
    id: SOURCE_ID,
    name: 'NVD Mock Source',
    source_type: 'api',
    status: 'enabled',
    last_success_at: NOW,
    last_error_at: null,
    failure_count: 0,
    recent_jobs: { success: 1, failed: 0, skipped: 0 },
  };
}

function sourceDetail() {
  return {
    ...sourceSummary(),
    base_url: 'https://example.test/nvd',
    last_error_message: null,
  };
}

function sourceJob() {
  return {
    id: '77777777-7777-4777-8777-777777777777',
    source_id: SOURCE_ID,
    job_name: 'nvd.mock.collect',
    task_name: 'sentineldrive.collect_source',
    status: 'success',
    run_status: 'completed',
    retried: false,
    skipped: false,
    started_at: NOW,
    finished_at: NOW,
    items_seen: 10,
    items_created: 2,
    items_updated: 1,
    error_message: null,
  };
}

function pipelineStatus() {
  return {
    pending_raw_rows: 2,
    failed_raw_rows: 0,
    scoring_pending_intelligence_rows: 1,
    open_alerts: 1,
    latest_pipeline_job: {
      task_name: 'sentineldrive.process_pipeline',
      status: 'success',
      finished_at: NOW,
      message: '最近处理完成。',
    },
    latest_source_job: sourceJob(),
    recent_failures: [],
  };
}

function statsOverview(url: URL) {
  // 当查询参数 zero=true 时返回零值响应，用于空态场景
  if (url.searchParams.get('zero') === 'true') return emptyStatsOverview();
  return {
    totals: {
      total_intelligence: 42,
      new_last_24_hours: 5,
      new_last_7_days: 18,
    },
    by_intelligence_type: { vulnerability: 20, advisory: 15, exposure: 5, incident: 2 },
    by_severity: { critical: 3, high: 12, medium: 18, low: 6, unknown: 3 },
    by_risk_level: { critical: 2, high: 10, medium: 15, low: 10, info: 5 },
    by_processing_status: { normalized: 40, pending: 2 },
    trend: [
      { date: '2026-05-15', count: 2 },
      { date: '2026-05-16', count: 3 },
      { date: '2026-05-17', count: 1 },
      { date: '2026-05-18', count: 4 },
      { date: '2026-05-19', count: 2 },
    ],
    alerts: {
      total: 7,
      by_status: { open: 2, acknowledged: 3, closed: 2 },
      trend: [
        { date: '2026-05-15', count: 1 },
        { date: '2026-05-16', count: 2 },
        { date: '2026-05-17', count: 1 },
      ],
    },
    sources: {
      enabled: 3,
      top: [
        { id: SOURCE_ID, name: 'NVD Mock Source', intelligence_count: 12 },
        { id: '44444444-4444-4444-8444-444444444445', name: 'CISA Mock', intelligence_count: 6 },
      ],
    },
  };
}

function emptyStatsOverview() {
  return {
    totals: { total_intelligence: 0, new_last_24_hours: 0, new_last_7_days: 0 },
    by_intelligence_type: { vulnerability: 0, advisory: 0, exposure: 0, incident: 0 },
    by_severity: { critical: 0, high: 0, medium: 0, low: 0, unknown: 0 },
    by_risk_level: { critical: 0, high: 0, medium: 0, low: 0, info: 0 },
    by_processing_status: { normalized: 0, pending: 0 },
    trend: [],
    alerts: { total: 0, by_status: { open: 0, acknowledged: 0, closed: 0 }, trend: [] },
    sources: { enabled: 0, top: [] },
  };
}

expect.extend({
  async toHaveHorizontalOverflow(locator: any) {
    const hasOverflow = await locator.evaluate(
      (element: Element) => element.scrollWidth > element.clientWidth + 1,
    );
    return {
      pass: hasOverflow,
      message: () => `expected ${locator} ${hasOverflow ? 'not ' : ''}to have horizontal overflow`,
    };
  },
});

declare global {
  namespace PlaywrightTest {
    interface Matchers<R> {
      toHaveHorizontalOverflow(): Promise<R>;
    }
  }
}
