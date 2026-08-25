"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { exportsApi, intelligenceApi } from "../../lib/endpoints";
import { EmptyDataState, ErrorState, LoadingState } from "../components/StateViews";
import { Toolbar } from "../components/WorkbenchShell";
import {
  attackSurfaceOptions,
  dateTimeLabel,
  intelligenceStatusOptions,
  intelligenceTypeOptions,
  labelFromOptions,
  numberLabel,
  riskLabel,
  riskLevelOptions,
  sortOptions,
  vehicleComponentOptions
} from "./labels";

const initialFilters = {
  q: "",
  cve: "",
  vendor: "",
  product: "",
  vehicle_component: "",
  attack_surface: "",
  risk_level: "",
  tag: "",
  source: "",
  status: "",
  intelligence_type: "",
  sort: "recent",
  page: 1,
  limit: 25
};

export function IntelligenceWorkbench() {
  const [draft, setDraft] = useState(initialFilters);
  const [filters, setFilters] = useState(initialFilters);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [exportError, setExportError] = useState("");

  const query = useMemo(() => ({ ...filters, limit: Number(filters.limit), page: Number(filters.page) }), [filters]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await intelligenceApi.list(query));
    } catch (requestError) {
      setError(requestError.message || "情报列表加载失败。");
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    load();
  }, [load]);

  function updateDraft(name, value) {
    setDraft((current) => ({ ...current, [name]: value }));
  }

  function applyFilters(event) {
    event.preventDefault();
    setFilters({ ...draft, page: 1 });
  }

  function resetFilters() {
    setDraft(initialFilters);
    setFilters(initialFilters);
  }

  function setPage(page) {
    const next = Math.max(1, page);
    setDraft((current) => ({ ...current, page: next }));
    setFilters((current) => ({ ...current, page: next }));
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
  const total = data?.total || 0;
  const page = data?.page || Number(filters.page);
  const limit = data?.limit || Number(filters.limit);
  const start = total ? (page - 1) * limit + 1 : 0;
  const end = Math.min(page * limit, total);

  return (
    <>
      <form onSubmit={applyFilters}>
        <Toolbar>
          <TextFilter label="关键词" name="q" value={draft.q} onChange={updateDraft} placeholder="标题、CVE、组件或标签" />
          <TextFilter label="CVE" name="cve" value={draft.cve} onChange={updateDraft} placeholder="CVE-2026-0001" />
          <TextFilter label="厂商" name="vendor" value={draft.vendor} onChange={updateDraft} placeholder="厂商名称" />
          <TextFilter label="产品" name="product" value={draft.product} onChange={updateDraft} placeholder="产品或系统" />
          <SelectFilter label="车辆组件" name="vehicle_component" value={draft.vehicle_component} onChange={updateDraft} options={vehicleComponentOptions} />
          <SelectFilter label="攻击面" name="attack_surface" value={draft.attack_surface} onChange={updateDraft} options={attackSurfaceOptions} />
          <SelectFilter label="风险等级" name="risk_level" value={draft.risk_level} onChange={updateDraft} options={riskLevelOptions} />
          <TextFilter label="标签" name="tag" value={draft.tag} onChange={updateDraft} placeholder="kev、manual" />
          <TextFilter label="来源" name="source" value={draft.source} onChange={updateDraft} placeholder="NVD、CISA" />
          <TextFilter label="状态" name="status" value={draft.status} onChange={updateDraft} placeholder="active" />
          <SelectFilter label="情报类型" name="intelligence_type" value={draft.intelligence_type} onChange={updateDraft} options={intelligenceTypeOptions} />
          <SelectFilter label="排序" name="sort" value={draft.sort} onChange={updateDraft} options={sortOptions} includeAll={false} />
          <SelectFilter label="每页" name="limit" value={String(draft.limit)} onChange={updateDraft} includeAll={false} options={[["10", "10"], ["25", "25"], ["50", "50"], ["100", "100"]]} />
          <button className="primary-button" type="submit">查询</button>
          <button className="secondary-button" type="button" onClick={resetFilters}>重置</button>
          <button className="secondary-button" type="button" onClick={() => runExport(() => exportsApi.intelligenceCsv(filters))}>导出 CSV</button>
          <button className="secondary-button" type="button" onClick={() => runExport(() => exportsApi.summaryPdf())}>导出摘要 PDF</button>
        </Toolbar>
      </form>

      {exportError ? <div className="inline-error table-message">{exportError}</div> : null}
      {loading ? <LoadingState title="正在加载情报" description="根据筛选条件读取后端情报列表。" /> : null}
      {!loading && error ? <ErrorState message={error} onRetry={load} /> : null}
      {!loading && !error && !items.length ? <EmptyDataState title="没有匹配的情报" description="请调整筛选条件或等待来源同步。" /> : null}
      {!loading && !error && items.length ? (
        <>
          <div className="table-summary">
            <span>共 {total} 条，当前 {start}-{end}</span>
          </div>
          <div className="table-wrap">
            <table className="dense-table">
              <thead>
                <tr>
                  <th>标题</th>
                  <th>CVE</th>
                  <th>厂商 / 产品</th>
                  <th>组件 / 攻击面</th>
                  <th>来源</th>
                  <th>风险</th>
                  <th>状态</th>
                  <th>最近发现</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="cell-title">{item.title}</div>
                      <div className="cell-subtext">{item.summary || "无摘要"}</div>
                    </td>
                    <td>{item.cve_id || "-"}</td>
                    <td>{[item.affected_vendor, item.affected_product].filter(Boolean).join(" / ") || "-"}</td>
                    <td>{[labelFromOptions(vehicleComponentOptions, item.vehicle_component), labelFromOptions(attackSurfaceOptions, item.attack_surface)].filter((value) => value !== "-").join(" / ") || "-"}</td>
                    <td>{(item.source_names || []).join("、") || "-"}</td>
                    <td>
                      <span className={`badge badge-risk-${item.risk_level}`}>{riskLabel(item.risk_level)}</span>
                      <div className="cell-subtext">{numberLabel(item.risk_score, " 分")}</div>
                    </td>
                    <td>{labelFromOptions(intelligenceStatusOptions, item.status)}</td>
                    <td>{dateTimeLabel(item.last_seen_at)}</td>
                    <td><Link className="text-link" href={`/intelligence/${item.id}`}>查看</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={page} hasNext={Boolean(data?.has_next)} onPage={setPage} />
        </>
      ) : null}
    </>
  );
}

function TextFilter({ label, name, value, onChange, placeholder }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input name={name} value={value} placeholder={placeholder} onChange={(event) => onChange(name, event.target.value)} />
    </label>
  );
}

function SelectFilter({ label, name, value, onChange, options, includeAll = true }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select name={name} value={value} onChange={(event) => onChange(name, event.target.value)}>
        {includeAll ? <option value="">全部</option> : null}
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>{optionLabel}</option>
        ))}
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
