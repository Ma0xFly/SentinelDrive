"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { alertsApi, sourcesApi } from "../../lib/endpoints";
import { EmptyDataState, ErrorState, LoadingState } from "../components/StateViews";
import { Toolbar } from "../components/WorkbenchShell";
import { dateTimeLabel } from "../intelligence/labels";

const sourceStatusOptions = [
  ["enabled", "启用"],
  ["disabled", "停用"],
  ["error", "异常"]
];

const sourceTypeOptions = [
  ["api", "API"],
  ["rss", "RSS"],
  ["html", "HTML"],
  ["pdf", "PDF"],
  ["manual", "手工"],
  ["vendor", "厂商"]
];

const sourceSortOptions = [
  ["name", "名称"],
  ["recent", "最近更新"],
  ["failures", "失败优先"]
];

const jobStatusOptions = [
  ["queued", "排队"],
  ["running", "运行中"],
  ["success", "成功"],
  ["failed", "失败"]
];

const initialFilters = {
  status: "",
  source_type: "",
  q: "",
  sort: "name",
  page: 1,
  limit: 25
};

const initialOperationLimits = {
  normalization_limit: "100",
  scoring_limit: "100",
  alert_limit: "100"
};

const sensitiveTextPattern = /(password|token|secret|api[_-]?key|authorization|bearer)\b/i;

export function SourcesWorkbench() {
  const [draft, setDraft] = useState(initialFilters);
  const [filters, setFilters] = useState(initialFilters);
  const [data, setData] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedSource, setSelectedSource] = useState(null);
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [pipelineLoading, setPipelineLoading] = useState(true);
  const [pipelineError, setPipelineError] = useState("");
  const [pipelineNotice, setPipelineNotice] = useState("");
  const [pipelineTriggering, setPipelineTriggering] = useState(false);
  const [alertEvaluating, setAlertEvaluating] = useState(false);
  const [operationLimits, setOperationLimits] = useState(initialOperationLimits);

  const query = useMemo(() => ({ ...filters, page: Number(filters.page), limit: Number(filters.limit) }), [filters]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await sourcesApi.list(query);
      setData(result);
      if (!selectedId && result.items?.[0]?.id) {
        setSelectedId(result.items[0].id);
      }
    } catch (requestError) {
      setError(requestError.message || "来源列表加载失败。");
    } finally {
      setLoading(false);
    }
  }, [query, selectedId]);

  const loadPipelineStatus = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setPipelineLoading(true);
    }
    setPipelineError("");
    try {
      const result = await sourcesApi.pipelineStatus();
      setPipelineStatus(result || {});
    } catch (requestError) {
      setPipelineError(requestError.message || "处理状态加载失败。");
    } finally {
      if (!silent) {
        setPipelineLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadPipelineStatus();
  }, [loadPipelineStatus]);

  useEffect(() => {
    async function loadDetail() {
      if (!selectedId) {
        setSelectedSource(null);
        setJobs(null);
        return;
      }
      setDetailError("");
      try {
        const [source, jobPage] = await Promise.all([
          sourcesApi.detail(selectedId),
          sourcesApi.jobs({ source_id: selectedId, sort: "recent", page: 1, limit: 8 })
        ]);
        setSelectedSource(source);
        setJobs(jobPage);
      } catch (requestError) {
        setDetailError(requestError.message || "来源详情加载失败。");
      }
    }
    loadDetail();
  }, [selectedId]);

  function updateDraft(name, value) {
    setDraft((current) => ({ ...current, [name]: value }));
  }

  function applyFilters(event) {
    event.preventDefault();
    setFilters({ ...draft, page: 1 });
    setSelectedId(null);
  }

  function resetFilters() {
    setDraft(initialFilters);
    setFilters(initialFilters);
    setSelectedId(null);
  }

  function updateOperationLimit(name, value) {
    setOperationLimits((current) => ({ ...current, [name]: value }));
  }

  function setPage(page) {
    const next = Math.max(1, page);
    setDraft((current) => ({ ...current, page: next }));
    setFilters((current) => ({ ...current, page: next }));
  }

  async function refreshAll() {
    setPipelineNotice("");
    await Promise.all([load(), loadPipelineStatus()]);
  }

  async function triggerPipeline() {
    setPipelineTriggering(true);
    setPipelineError("");
    setPipelineNotice("");
    try {
      const result = await sourcesApi.triggerPipeline(
        buildLimitPayload(operationLimits, ["normalization_limit", "scoring_limit", "alert_limit"])
      );
      setPipelineNotice(operationMessage(result, "处理流水线已触发。"));
      await Promise.all([load(), loadPipelineStatus({ silent: true })]);
    } catch (requestError) {
      setPipelineError(requestError.message || "处理流水线触发失败。");
    } finally {
      setPipelineTriggering(false);
    }
  }

  async function evaluateAlerts() {
    setAlertEvaluating(true);
    setPipelineError("");
    setPipelineNotice("");
    try {
      const result = await alertsApi.evaluate({ limit: parsePositiveInteger(operationLimits.alert_limit, 100) });
      setPipelineNotice(operationMessage(result, "告警评估已执行。"));
      await loadPipelineStatus({ silent: true });
    } catch (requestError) {
      setPipelineError(requestError.message || "告警评估失败。");
    } finally {
      setAlertEvaluating(false);
    }
  }

  async function updateStatus({ status, reason }) {
    if (!selectedSource) {
      return;
    }
    setSaving(true);
    setDetailError("");
    try {
      const updated = await sourcesApi.updateStatus(selectedSource.id, { status, reason: reason || null });
      setSelectedSource(updated);
      await load();
    } catch (requestError) {
      setDetailError(requestError.message || "来源状态更新失败。");
    } finally {
      setSaving(false);
    }
  }

  const items = data?.items || [];

  return (
    <>
      <PipelineControlPanel
        status={pipelineStatus}
        loading={pipelineLoading}
        error={pipelineError}
        notice={pipelineNotice}
        limits={operationLimits}
        triggering={pipelineTriggering}
        evaluating={alertEvaluating}
        onLimitChange={updateOperationLimit}
        onRefresh={refreshAll}
        onTrigger={triggerPipeline}
        onEvaluate={evaluateAlerts}
      />

      <div className="split-workbench">
        <section className="split-primary">
          <form onSubmit={applyFilters}>
            <Toolbar>
              <SelectFilter label="状态" name="status" value={draft.status} onChange={updateDraft} options={sourceStatusOptions} />
              <SelectFilter label="类型" name="source_type" value={draft.source_type} onChange={updateDraft} options={sourceTypeOptions} />
              <TextFilter label="名称" name="q" value={draft.q} onChange={updateDraft} placeholder="NVD、CISA、RSS" />
              <SelectFilter label="排序" name="sort" value={draft.sort} onChange={updateDraft} options={sourceSortOptions} includeAll={false} />
              <SelectFilter label="每页" name="limit" value={String(draft.limit)} onChange={updateDraft} options={[["10", "10"], ["25", "25"], ["50", "50"]]} includeAll={false} />
              <button className="primary-button" type="submit">查询</button>
              <button className="secondary-button" type="button" onClick={resetFilters}>重置</button>
            </Toolbar>
          </form>

          {loading ? <LoadingState title="正在加载来源" description="读取来源状态和最近任务摘要。" /> : null}
          {!loading && error ? <ErrorState message={error} onRetry={load} /> : null}
          {!loading && !error && !items.length ? <EmptyDataState title="暂无来源" description="当前条件下没有来源配置。" /> : null}
          {!loading && !error && items.length ? (
            <>
              <div className="table-summary">共 {data.total} 个来源，当前第 {data.page} 页</div>
              <div className="table-wrap">
                <table className="dense-table">
                  <thead>
                    <tr>
                      <th>来源</th>
                      <th>类型</th>
                      <th>状态</th>
                      <th>最近成功</th>
                      <th>最近失败</th>
                      <th>失败次数</th>
                      <th>最近任务</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr key={item.id} className={item.id === selectedId ? "selected-row" : ""}>
                        <td>{item.name}</td>
                        <td>{sourceTypeLabel(item.source_type)}</td>
                        <td>{sourceStatusLabel(item.status)}</td>
                        <td>{dateTimeLabel(item.last_success_at)}</td>
                        <td>{dateTimeLabel(item.last_error_at)}</td>
                        <td>{item.failure_count}</td>
                        <td>{jobSummary(item.recent_jobs)}</td>
                        <td><button className="text-button" type="button" onClick={() => setSelectedId(item.id)}>查看</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={data.page} hasNext={data.has_next} onPage={setPage} />
            </>
          ) : null}
        </section>

        <SourceDetail source={selectedSource} jobs={jobs} error={detailError} saving={saving} onSubmit={updateStatus} />
      </div>
    </>
  );
}

function PipelineControlPanel({
  status,
  loading,
  error,
  notice,
  limits,
  triggering,
  evaluating,
  onLimitChange,
  onRefresh,
  onTrigger,
  onEvaluate
}) {
  const metrics = [
    {
      label: "待归一化原始记录",
      value: displayCount(firstValue(status, ["pending_raw_count", "pending_raw_rows", "raw_pending", "pending_raw"])),
      note: "采集后待处理"
    },
    {
      label: "失败原始记录",
      value: displayCount(firstValue(status, ["failed_raw_count", "failed_raw_rows", "raw_failed", "failed_raw"])),
      note: "需要排查"
    },
    {
      label: "待评分情报",
      value: displayCount(firstValue(status, [
        "scoring_pending_intelligence_rows",
        "scoring_pending_count",
        "pending_scoring_count",
        "scoring_pending",
        "pending_score_count"
      ])),
      note: "等待风险评分"
    },
    {
      label: "打开告警",
      value: displayCount(firstValue(status, ["open_alert_count", "open_alerts", "active_alert_count", "pending_alert_count"])),
      note: "待运营处理"
    }
  ];
  const latestPipeline = firstObject(status, [
    "latest_pipeline_trigger",
    "latest_pipeline_job",
    "latest_pipeline_run",
    "latest_pipeline_task",
    "latest_processing_run"
  ]);
  const latestSource = firstObject(status, ["latest_source_job", "latest_source_run", "latest_sync_job", "latest_collection_job"]);
  const failures = firstArray(status, ["recent_failures", "failures", "recent_failed_jobs", "failed_jobs"]).slice(0, 5);

  return (
    <section className="operations-panel" aria-label="处理操作">
      <div className="operations-header">
        <div>
          <h3>处理控制</h3>
          <p>手动触发采集、归一化、评分，并单独执行后端告警评估。</p>
        </div>
        <div className="operations-buttons">
          <button className="secondary-button" type="button" onClick={onRefresh} disabled={loading || triggering || evaluating}>
            {loading ? "刷新中" : "刷新状态"}
          </button>
          <button className="primary-button" type="button" onClick={onTrigger} disabled={triggering}>
            {triggering ? "触发中" : "触发处理流水线"}
          </button>
          <button className="secondary-button" type="button" onClick={onEvaluate} disabled={evaluating}>
            {evaluating ? "评估中" : "评估告警"}
          </button>
        </div>
      </div>

      <div className="operation-metrics">
        {metrics.map((item) => (
          <div className="operation-metric" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.note}</small>
          </div>
        ))}
      </div>

      <div className="operation-limits">
        <NumberField
          label="归一化上限"
          name="normalization_limit"
          value={limits.normalization_limit}
          onChange={onLimitChange}
        />
        <NumberField label="评分上限" name="scoring_limit" value={limits.scoring_limit} onChange={onLimitChange} />
        <NumberField label="告警上限" name="alert_limit" value={limits.alert_limit} onChange={onLimitChange} />
      </div>

      {loading ? <div className="operation-message">正在读取处理状态。</div> : null}
      {error ? <div className="operation-message operation-error" role="alert">{error}</div> : null}
      {notice ? <div className="operation-message operation-success" role="status">{notice}</div> : null}

      <div className="operation-runs">
        <OperationRun title="最近处理运行" item={latestPipeline} fallbackName="处理流水线" />
        <OperationRun title="最近来源运行" item={latestSource} fallbackName="来源采集" />
      </div>

      <RecentFailures failures={failures} />
    </section>
  );
}

function OperationRun({ title, item, fallbackName }) {
  const summary = runSummary(item, fallbackName);

  return (
    <div className="operation-run">
      <h3>{title}</h3>
      {summary.length ? (
        <dl className="compact-detail">
          {summary.map(([label, value]) => (
            <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
          ))}
        </dl>
      ) : (
        <p className="detail-text">暂无运行记录。</p>
      )}
    </div>
  );
}

function RecentFailures({ failures }) {
  if (!failures.length) {
    return null;
  }

  return (
    <div className="operation-failures">
      <h3>最近失败</h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>来源/任务</th>
              <th>状态</th>
              <th>原因</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {failures.map((failure, index) => (
              <tr key={failure.id || failure.job_id || `${safeText(failure.name || failure.job_name)}-${index}`}>
                <td>{safeText(firstValue(failure, ["source_name", "name", "job_name", "task_name"]), "-")}</td>
                <td>{safeText(firstValue(failure, ["status", "run_status", "task_status"]), "-")}</td>
                <td>{safeOperationalText(firstValue(failure, ["message", "error_message", "last_error_message", "reason"]), "-")}</td>
                <td>{dateTimeLabel(firstValue(failure, ["occurred_at", "finished_at", "last_error_at", "created_at", "started_at"]))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SourceDetail({ source, jobs, error, saving, onSubmit }) {
  const [status, setStatus] = useState("enabled");
  const [reason, setReason] = useState("");

  useEffect(() => {
    setStatus(source?.status || "enabled");
    setReason("");
  }, [source]);

  if (error) {
    return <aside className="split-detail"><ErrorState message={error} /></aside>;
  }
  if (!source) {
    return <aside className="split-detail"><EmptyDataState title="未选择来源" description="从列表中选择一个来源查看同步状态。" /></aside>;
  }

  return (
    <aside className="split-detail">
      <h3>{source.name}</h3>
      <dl className="compact-detail">
        <div><dt>类型</dt><dd>{sourceTypeLabel(source.source_type)}</dd></div>
        <div><dt>状态</dt><dd>{sourceStatusLabel(source.status)}</dd></div>
        <div><dt>最近成功</dt><dd>{dateTimeLabel(source.last_success_at)}</dd></div>
        <div><dt>最近失败</dt><dd>{dateTimeLabel(source.last_error_at)}</dd></div>
        <div><dt>连续失败</dt><dd>{source.failure_count}</dd></div>
        <div><dt>错误</dt><dd>{source.last_error_message || "-"}</dd></div>
      </dl>
      <form className="stack-form" onSubmit={(event) => {
        event.preventDefault();
        onSubmit({ status, reason });
      }}>
        <label className="field">
          <span>来源状态</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            {sourceStatusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="field">
          <span>原因</span>
          <input value={reason} placeholder="记录启停或异常处理原因" onChange={(event) => setReason(event.target.value)} />
        </label>
        <button className="primary-button" type="submit" disabled={saving}>{saving ? "保存中" : "更新来源状态"}</button>
      </form>

      <div className="detail-block nested-detail">
        <h3>最近任务</h3>
        <JobTable jobs={jobs?.items || []} />
      </div>
    </aside>
  );
}

function JobTable({ jobs }) {
  if (!jobs.length) {
    return <p className="detail-text">暂无任务日志。</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>任务</th>
            <th>状态</th>
            <th>运行状态</th>
            <th>重试</th>
            <th>跳过</th>
            <th>完成时间</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>{job.job_name}</td>
              <td>{jobStatusLabel(job.status)}</td>
              <td>{job.run_status || "-"}</td>
              <td>{job.retried ? "是" : "否"}</td>
              <td>{job.skipped ? "是" : "否"}</td>
              <td>{dateTimeLabel(job.finished_at || job.started_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TextFilter({ label, name, value, onChange, placeholder }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} placeholder={placeholder} onChange={(event) => onChange(name, event.target.value)} />
    </label>
  );
}

function NumberField({ label, name, value, onChange }) {
  return (
    <label className="field operation-number-field">
      <span>{label}</span>
      <input
        min="1"
        max="500"
        step="1"
        type="number"
        value={value}
        onChange={(event) => onChange(name, event.target.value)}
      />
    </label>
  );
}

function SelectFilter({ label, name, value, onChange, options, includeAll = true }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(name, event.target.value)}>
        {includeAll ? <option value="">全部</option> : null}
        {options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}
      </select>
    </label>
  );
}

function Pagination({ page, hasNext, onPage }) {
  return (
    <div className="pagination">
      <button className="secondary-button" type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>上一页</button>
      <span>第 {page} 页</span>
      <button className="secondary-button" type="button" disabled={!hasNext} onClick={() => onPage(page + 1)}>下一页</button>
    </div>
  );
}

function sourceStatusLabel(value) {
  return sourceStatusOptions.find(([key]) => key === value)?.[1] || value || "-";
}

function sourceTypeLabel(value) {
  return sourceTypeOptions.find(([key]) => key === value)?.[1] || value || "-";
}

function jobStatusLabel(value) {
  return jobStatusOptions.find(([key]) => key === value)?.[1] || value || "-";
}

function jobSummary(summary) {
  if (!summary) {
    return "-";
  }
  return `${summary.success} 成功 / ${summary.failed} 失败 / ${summary.skipped} 跳过`;
}

function buildLimitPayload(limits, keys) {
  return keys.reduce((payload, key) => {
    payload[key] = parsePositiveInteger(limits[key], 100);
    return payload;
  }, {});
}

function parsePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return fallback;
  }
  return Math.min(parsed, 500);
}

function displayCount(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return "-";
}

function firstValue(source, keys) {
  if (!source || typeof source !== "object") {
    return undefined;
  }
  for (const key of keys) {
    const value = source[key];
    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }
  return undefined;
}

function firstObject(source, keys) {
  const value = firstValue(source, keys);
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function firstArray(source, keys) {
  const value = firstValue(source, keys);
  return Array.isArray(value) ? value : [];
}

function operationMessage(result, fallback) {
  const message = firstValue(result, ["message", "detail", "status_message"]);
  if (message) {
    return safeOperationalText(message, fallback);
  }
  const taskStatus = firstValue(result, ["task_status", "status", "state"]);
  if (taskStatus) {
    return `${fallback} 状态：${statusLabel(taskStatus)}`;
  }
  const created = firstValue(result, ["created", "created_count"]);
  if (created !== undefined) {
    return `${fallback} 新建 ${displayCount(created)} 条告警。`;
  }
  return fallback;
}

function runSummary(item, fallbackName) {
  if (!item) {
    return [];
  }

  const rows = [];
  const name = firstValue(item, ["source_name", "source", "display_name"]);
  const status = firstValue(item, ["task_status", "status", "state", "run_status"]);
  const message = firstValue(item, ["message", "summary", "error_message", "last_error_message"]);
  const finishedAt = firstValue(item, ["finished_at", "completed_at", "updated_at", "created_at", "started_at", "triggered_at"]);
  if (name || fallbackName) {
    rows.push(["对象", safeText(name, fallbackName)]);
  }
  if (status) {
    rows.push(["状态", statusLabel(status)]);
  }
  if (finishedAt) {
    rows.push(["时间", dateTimeLabel(finishedAt)]);
  }
  if (message) {
    rows.push(["摘要", safeOperationalText(message)]);
  }
  return rows;
}

function statusLabel(value) {
  const optionLabel = [...jobStatusOptions, ...sourceStatusOptions].find(([key]) => key === value)?.[1];
  return optionLabel || safeText(value, "-");
}

function safeText(value, fallback = "") {
  if (value === undefined || value === null || value === "") {
    return fallback;
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

function truncate(value, limit) {
  if (!value || value.length <= limit) {
    return value;
  }
  return `${value.slice(0, limit - 1)}…`;
}

function safeOperationalText(value, fallback = "") {
  const text = safeText(value, fallback);
  if (!text || text === fallback) {
    return text;
  }
  if (sensitiveTextPattern.test(text)) {
    return "错误信息已隐藏";
  }
  return truncate(text, 160);
}
