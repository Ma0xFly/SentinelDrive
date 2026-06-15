"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { alertsApi, exportsApi } from "../../lib/endpoints";
import { EmptyDataState, ErrorState, LoadingState } from "../components/StateViews";
import { Toolbar } from "../components/WorkbenchShell";
import { dateTimeLabel, riskLabel, riskLevelOptions } from "../intelligence/labels";

const statusOptions = [
  ["open", "未确认"],
  ["acknowledged", "已确认"],
  ["closed", "已关闭"]
];

const sortOptions = [
  ["recent", "最近触发"],
  ["risk_level", "风险等级"]
];

const initialFilters = {
  risk_level: "",
  status: "",
  triggering_rule: "",
  intelligence_id: "",
  sort: "recent",
  page: 1,
  limit: 25
};

export function AlertsWorkbench() {
  const [draft, setDraft] = useState(initialFilters);
  const [filters, setFilters] = useState(initialFilters);
  const [data, setData] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [detailError, setDetailError] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [exportError, setExportError] = useState("");

  const query = useMemo(() => ({ ...filters, page: Number(filters.page), limit: Number(filters.limit) }), [filters]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await alertsApi.list(query);
      setData(result);
      if (!selectedId && result.items?.[0]?.id) {
        setSelectedId(result.items[0].id);
      }
    } catch (requestError) {
      setError(requestError.message || "告警列表加载失败。");
    } finally {
      setLoading(false);
    }
  }, [query, selectedId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    async function loadDetail() {
      if (!selectedId) {
        setSelectedAlert(null);
        return;
      }
      setDetailError("");
      try {
        setSelectedAlert(await alertsApi.detail(selectedId));
      } catch (requestError) {
        setDetailError(requestError.message || "告警详情加载失败。");
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

  function setPage(page) {
    const next = Math.max(1, page);
    setDraft((current) => ({ ...current, page: next }));
    setFilters((current) => ({ ...current, page: next }));
  }

  async function updateStatus({ status, notes, notesTouched }) {
    if (!selectedAlert) {
      return;
    }
    setSaving(true);
    setDetailError("");
    const payload = { status };
    if (notesTouched) {
      payload.notes = notes === "" ? null : notes;
    }
    try {
      const updated = await alertsApi.updateStatus(selectedAlert.id, payload);
      setSelectedAlert(updated);
      await load();
    } catch (requestError) {
      setDetailError(requestError.message || "状态更新失败。");
    } finally {
      setSaving(false);
    }
  }

  async function runExport(download) {
    setExportError("");
    try {
      await download();
    } catch (requestError) {
      setExportError(requestError.message || "导出失败，请稍后重试。");
    }
  }

  const items = data?.items || [];

  return (
    <div className="split-workbench">
      <section className="split-primary">
        <form onSubmit={applyFilters}>
          <Toolbar>
            <SelectFilter label="状态" name="status" value={draft.status} onChange={updateDraft} options={statusOptions} />
            <SelectFilter label="风险" name="risk_level" value={draft.risk_level} onChange={updateDraft} options={riskLevelOptions} />
            <TextFilter label="触发规则" name="triggering_rule" value={draft.triggering_rule} onChange={updateDraft} placeholder="critical_intelligence" />
            <TextFilter label="情报 ID" name="intelligence_id" value={draft.intelligence_id} onChange={updateDraft} placeholder="UUID" />
            <SelectFilter label="排序" name="sort" value={draft.sort} onChange={updateDraft} options={sortOptions} includeAll={false} />
            <SelectFilter label="每页" name="limit" value={String(draft.limit)} onChange={updateDraft} options={[["10", "10"], ["25", "25"], ["50", "50"]]} includeAll={false} />
            <button className="primary-button" type="submit">查询</button>
            <button className="secondary-button" type="button" onClick={resetFilters}>重置</button>
            <button className="secondary-button" type="button" onClick={() => runExport(() => exportsApi.alertsCsv(filters))}>导出告警 CSV</button>
            <button className="secondary-button" type="button" onClick={() => runExport(() => exportsApi.summaryPdf())}>摘要 PDF</button>
          </Toolbar>
        </form>

        {exportError ? <div className="inline-error table-message">{exportError}</div> : null}
        {loading ? <LoadingState title="正在加载告警" description="读取告警队列。" /> : null}
        {!loading && error ? <ErrorState message={error} onRetry={load} /> : null}
        {!loading && !error && !items.length ? <EmptyDataState title="暂无告警" description="当前条件下没有告警。" /> : null}
        {!loading && !error && items.length ? (
          <>
            <div className="table-summary">共 {data.total} 条，当前第 {data.page} 页</div>
            <div className="table-wrap">
              <table className="dense-table">
                <thead>
                  <tr>
                    <th>标题</th>
                    <th>规则</th>
                    <th>风险</th>
                    <th>状态</th>
                    <th>触发时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id} className={item.id === selectedId ? "selected-row" : ""}>
                      <td>{item.title}</td>
                      <td>{item.triggering_rule}</td>
                      <td><span className={`badge badge-risk-${item.risk_level}`}>{riskLabel(item.risk_level)}</span></td>
                      <td>{statusLabel(item.status)}</td>
                      <td>{dateTimeLabel(item.triggered_at)}</td>
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

      <AlertDetail alert={selectedAlert} error={detailError} saving={saving} onSubmit={updateStatus} />
    </div>
  );
}

function AlertDetail({ alert, error, saving, onSubmit }) {
  const [status, setStatus] = useState("");
  const [notes, setNotes] = useState("");
  const [notesTouched, setNotesTouched] = useState(false);

  useEffect(() => {
    setStatus(alert?.status || "open");
    setNotes(alert?.notes || "");
    setNotesTouched(false);
  }, [alert]);

  if (error) {
    return <aside className="split-detail"><ErrorState message={error} /></aside>;
  }
  if (!alert) {
    return <aside className="split-detail"><EmptyDataState title="未选择告警" description="从列表中选择一条告警查看详情。" /></aside>;
  }

  return (
    <aside className="split-detail">
      <h3>{alert.title}</h3>
      <dl className="compact-detail">
        <div><dt>规则</dt><dd>{alert.triggering_rule}</dd></div>
        <div><dt>风险</dt><dd>{riskLabel(alert.risk_level)}</dd></div>
        <div><dt>状态</dt><dd>{statusLabel(alert.status)}</dd></div>
        <div><dt>触发时间</dt><dd>{dateTimeLabel(alert.triggered_at)}</dd></div>
      </dl>
      {alert.intelligence ? (
        <div className="detail-block nested-detail">
          <h3>关联情报</h3>
          <p className="detail-text">{alert.intelligence.title}</p>
          <Link className="text-link" href={`/intelligence/${alert.intelligence.id}`}>打开情报详情</Link>
        </div>
      ) : null}
      <form className="stack-form" onSubmit={(event) => {
        event.preventDefault();
        onSubmit({ status, notes, notesTouched });
      }}>
        <label className="field">
          <span>状态</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            {statusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="field">
          <span>备注</span>
          <textarea value={notes} rows="5" placeholder="留空且未编辑时保留原备注；清空后提交会清除备注。" onChange={(event) => {
            setNotes(event.target.value);
            setNotesTouched(true);
          }} />
        </label>
        <button className="primary-button" type="submit" disabled={saving}>{saving ? "保存中" : "更新状态"}</button>
      </form>
    </aside>
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

function statusLabel(value) {
  return {
    open: "未确认",
    acknowledged: "已确认",
    closed: "已关闭"
  }[value] || value || "-";
}
