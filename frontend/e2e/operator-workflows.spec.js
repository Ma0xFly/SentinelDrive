const { expect, test } = require("@playwright/test");

const USER = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "admin@example.test",
  display_name: "安全运营员",
  is_admin: true,
  is_active: true,
  created_at: "2026-05-21T00:00:00Z",
  updated_at: "2026-05-21T00:00:00Z"
};

const INTELLIGENCE_ID = "11111111-1111-4111-8111-111111111111";
const ALERT_ID = "22222222-2222-4222-8222-222222222222";
const SOURCE_ID = "33333333-3333-4333-8333-333333333333";
const MANUAL_ENTRY_ID = "44444444-4444-4444-8444-444444444444";
const NOW = "2026-05-21T08:00:00Z";

test.beforeEach(async ({ page }) => {
  const state = {
    alertStatus: "open",
    alertNotes: "等待值班确认。",
    manualEntries: []
  };

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "") || "/";
    const method = request.method();

    if (method === "POST" && path === "/auth/login") {
      return json(route, { access_token: "browser-test-token", token_type: "bearer" });
    }

    if (request.headers().authorization !== "Bearer browser-test-token") {
      return json(route, { detail: { error: { code: "not_authenticated", message: "登录状态已过期，请重新登录。" } } }, 401);
    }

    if (method === "GET" && path === "/auth/me") {
      return json(route, USER);
    }
    if (method === "POST" && path === "/auth/logout") {
      return json(route, {});
    }

    if (method === "GET" && path === "/intelligence") {
      return json(route, pageResponse([intelligenceSummary()]));
    }
    if (method === "GET" && path === `/intelligence/${INTELLIGENCE_ID}`) {
      return json(route, intelligenceDetail());
    }

    if (method === "GET" && path === "/manual-entries") {
      return json(route, state.manualEntries);
    }
    if (method === "POST" && path === "/manual-entries") {
      const payload = await request.postDataJSON();
      const entry = {
        ...payload,
        id: MANUAL_ENTRY_ID,
        created_by_user_id: USER.id,
        created_at: NOW,
        updated_at: NOW
      };
      state.manualEntries = [entry];
      return json(route, entry, 201);
    }

    if (method === "GET" && path === "/alerts") {
      return json(route, pageResponse([alertSummary(state)]));
    }
    if (method === "GET" && path === `/alerts/${ALERT_ID}`) {
      return json(route, alertDetail(state));
    }
    if (method === "PATCH" && path === `/alerts/${ALERT_ID}/status`) {
      const payload = await request.postDataJSON();
      state.alertStatus = payload.status;
      if (Object.prototype.hasOwnProperty.call(payload, "notes")) {
        state.alertNotes = payload.notes;
      }
      return json(route, alertDetail(state));
    }
    if (method === "POST" && path === "/alerts/evaluate") {
      return json(route, { created: 1, updated: 0, alert_ids: [ALERT_ID] });
    }

    if (method === "GET" && path === "/sources") {
      return json(route, pageResponse([sourceSummary()]));
    }
    if (method === "GET" && path === `/sources/${SOURCE_ID}`) {
      return json(route, sourceDetail());
    }
    if (method === "GET" && path === "/sources/jobs") {
      return json(route, pageResponse([sourceJob()]));
    }
    if (method === "GET" && path === "/sources/pipeline/status") {
      return json(route, pipelineStatus());
    }
    if (method === "POST" && path === "/sources/pipeline/trigger") {
      return json(route, {
        job_id: "55555555-5555-4555-8555-555555555555",
        celery_task_id: "pipeline-browser-test",
        task_name: "sentineldrive.process_pipeline",
        status: "queued",
        message: "处理流水线已加入队列。"
      }, 202);
    }
    if (method === "PATCH" && path === `/sources/${SOURCE_ID}/status`) {
      return json(route, sourceDetail());
    }

    if (method === "GET" && path === "/exports/intelligence.csv") {
      return route.fulfill({
        status: 200,
        headers: {
          "content-type": "text/csv; charset=utf-8",
          "content-disposition": "attachment; filename=\"sentineldrive-intelligence.csv\""
        },
        body: `id,title\n${INTELLIGENCE_ID},Mocked OTA risk\n`
      });
    }
    if (method === "GET" && path === "/exports/summary.pdf") {
      return route.fulfill({
        status: 200,
        headers: {
          "content-type": "application/pdf",
          "content-disposition": "attachment; filename=\"sentineldrive-summary.pdf\""
        },
        body: "%PDF-1.4\n%browser-test\n"
      });
    }

    return json(route, { detail: { error: { code: "unmocked_route", message: `${method} ${path}` } } }, 500);
  });
});

test("login protects the workbench and supports intelligence detail plus export", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "登录工作台" })).toBeVisible();

  await page.getByPlaceholder("admin@example.test").fill(USER.email);
  await page.getByPlaceholder("输入登录密码").fill("local-test-password");
  await page.getByRole("button", { name: "登录工作台" }).click();

  await expect(page.getByRole("heading", { name: "情报列表" })).toBeVisible();
  await expect(page.getByText("Mocked OTA risk", { exact: false })).toBeVisible();

  await page.getByRole("link", { name: "查看" }).click();
  await expect(page.getByRole("heading", { name: "Mocked OTA risk" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "来源归属" })).toBeVisible();

  await page.getByRole("link", { name: "情报列表" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 CSV" }).click();
  expect((await download).suggestedFilename()).toBe("sentineldrive-intelligence.csv");
});

test("manual entry validates required fields and submits a clean entry", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "手工录入" }).click();

  await page.getByRole("button", { name: "提交条目" }).click();
  await expect(page.getByText("标题至少需要 3 个字符。")).toBeVisible();

  await page.getByPlaceholder("至少 3 个字符").fill("Mocked supplier advisory");
  await page.getByPlaceholder("厂商公告、内部分析").fill("内部测试源");
  await page.getByPlaceholder("记录影响范围、触发条件和处置线索").fill("Browser workflow validates manual entry submission.");
  await page.getByRole("button", { name: "提交条目" }).click();

  await expect(page.getByText("手工情报已提交。")).toBeVisible();
  await expect(page.getByRole("heading", { name: "已录入条目" })).toBeVisible();
  await expect(page.getByText("Mocked supplier advisory")).toBeVisible();
});

test("source operations expose pipeline trigger and separate alert evaluation", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "来源管理" }).click();

  await expect(page.getByRole("heading", { name: "处理控制" })).toBeVisible();
  await expect(page.getByText("待归一化原始记录")).toBeVisible();
  await expect(page.getByRole("heading", { name: "NVD Mock Source" })).toBeVisible();

  await page.getByRole("button", { name: "触发处理流水线" }).click();
  await expect(page.getByText("处理流水线已加入队列。")).toBeVisible();

  await page.getByRole("button", { name: "评估告警" }).click();
  await expect(page.getByText("告警评估已执行。 新建 1 条告警。")).toBeVisible();
});

test("alert review updates status and keeps linked intelligence reachable", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "告警" }).click();

  await expect(page.getByRole("heading", { name: "Critical mocked alert" })).toBeVisible();
  await expect(page.getByRole("link", { name: "打开情报详情" })).toHaveAttribute("href", `/intelligence/${INTELLIGENCE_ID}`);

  await page.locator(".split-detail").getByLabel("状态").selectOption("acknowledged");
  await page.getByPlaceholder("留空且未编辑时保留原备注；清空后提交会清除备注。").fill("浏览器流程已确认。");
  await page.getByRole("button", { name: "更新状态" }).click();

  await expect(page.locator(".split-detail")).toContainText("已确认");
});

async function login(page) {
  await page.goto("/");
  await page.getByPlaceholder("admin@example.test").fill(USER.email);
  await page.getByPlaceholder("输入登录密码").fill("local-test-password");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page.getByRole("heading", { name: "情报列表" })).toBeVisible();
}

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

function pageResponse(items) {
  return {
    items,
    total: items.length,
    page: 1,
    limit: 25,
    has_next: false,
    has_previous: false
  };
}

function intelligenceSummary() {
  return {
    id: INTELLIGENCE_ID,
    title: "Mocked OTA risk",
    summary: "Deterministic browser test intelligence item.",
    intelligence_type: "vulnerability",
    cve_id: "CVE-2026-0001",
    severity: "high",
    risk_level: "high",
    risk_score: 82,
    status: "active",
    affected_vendor: "Example Auto",
    affected_product: "OTA Gateway",
    vehicle_component: "telematics",
    attack_surface: "remote",
    source_names: ["NVD Mock Source"],
    source_urls: ["https://example.test/advisory"],
    tags: ["mocked", "e2e"],
    first_seen_at: NOW,
    last_seen_at: NOW
  };
}

function intelligenceDetail() {
  return {
    ...intelligenceSummary(),
    cwe_id: "CWE-79",
    cvss_score: 8.2,
    cvss_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
    affected_version: "<= 1.2.3",
    exploit_status: "proof_of_concept",
    confidence: "high",
    dedup_key: "cve:CVE-2026-0001",
    score_explanation: "Mocked scoring explanation.",
    score_metadata: { source_confidence: "mocked" },
    sources: [
      {
        id: "66666666-6666-4666-8666-666666666666",
        source_name: "NVD Mock Source",
        source_url: "https://example.test/advisory",
        external_id: "CVE-2026-0001",
        first_seen_at: NOW,
        last_seen_at: NOW
      }
    ],
    related_alerts: [alertSummary({ alertStatus: "open" })]
  };
}

function alertSummary(state) {
  return {
    id: ALERT_ID,
    title: "Critical mocked alert",
    threat_intelligence_id: INTELLIGENCE_ID,
    triggering_rule: "critical_intelligence",
    risk_level: "high",
    status: state.alertStatus,
    triggered_at: NOW,
    notes: state.alertNotes
  };
}

function alertDetail(state) {
  return {
    ...alertSummary(state),
    intelligence: intelligenceSummary()
  };
}

function sourceSummary() {
  return {
    id: SOURCE_ID,
    name: "NVD Mock Source",
    source_type: "api",
    status: "enabled",
    last_success_at: NOW,
    last_error_at: null,
    failure_count: 0,
    recent_jobs: { success: 1, failed: 0, skipped: 0 }
  };
}

function sourceDetail() {
  return {
    ...sourceSummary(),
    base_url: "https://example.test/nvd",
    last_error_message: null
  };
}

function sourceJob() {
  return {
    id: "77777777-7777-4777-8777-777777777777",
    source_id: SOURCE_ID,
    job_name: "nvd.mock.collect",
    task_name: "sentineldrive.collect_source",
    status: "success",
    run_status: "completed",
    retried: false,
    skipped: false,
    started_at: NOW,
    finished_at: NOW
  };
}

function pipelineStatus() {
  return {
    pending_raw_rows: 2,
    failed_raw_rows: 0,
    scoring_pending_intelligence_rows: 1,
    open_alerts: 1,
    latest_pipeline_job: {
      task_name: "sentineldrive.process_pipeline",
      status: "success",
      finished_at: NOW,
      message: "最近处理完成。"
    },
    latest_source_job: sourceJob(),
    recent_failures: []
  };
}
