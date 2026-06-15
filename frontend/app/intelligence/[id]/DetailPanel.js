"use client";

import Link from "next/link";
import { useState } from "react";
import { exportsApi, intelligenceApi } from "../../../lib/endpoints";
import { useApiResource } from "../../../lib/dataHooks";
import { EmptyDataState, ErrorState, LoadingState } from "../../components/StateViews";
import { Toolbar } from "../../components/WorkbenchShell";
import {
  attackSurfaceOptions,
  dateTimeLabel,
  intelligenceTypeOptions,
  labelFromOptions,
  numberLabel,
  riskLabel,
  severityLabel,
  vehicleComponentOptions
} from "../labels";

export function IntelligenceDetailPanel({ itemId }) {
  const { data, error, loading, reload } = useApiResource(() => intelligenceApi.detail(itemId), [itemId]);
  const [exportError, setExportError] = useState("");

  async function runExport(download) {
    setExportError("");
    try {
      await download();
    } catch (requestError) {
      setExportError(requestError.message || "导出失败，请稍后重试。");
    }
  }

  if (loading) {
    return <LoadingState title="正在加载详情" description="读取情报详情、来源归属和关联告警。" />;
  }
  if (error) {
    return <ErrorState message={error} onRetry={reload} />;
  }
  if (!data) {
    return <EmptyDataState title="未找到情报详情" description="后端没有返回该情报记录。" />;
  }

  return (
    <div className="detail-stack">
      <Toolbar>
        <button className="secondary-button" type="button" onClick={() => runExport(() => exportsApi.intelligenceCsv({ q: data.title, limit: 100 }))}>导出情报 CSV</button>
        <button className="secondary-button" type="button" onClick={() => runExport(() => exportsApi.intelligenceMarkdown(data.id))}>导出 Markdown</button>
        <button className="secondary-button" type="button" onClick={() => runExport(() => exportsApi.summaryPdf())}>摘要 PDF</button>
        {exportError ? <span className="inline-error">{exportError}</span> : null}
      </Toolbar>

      <section className="detail-summary">
        <div>
          <h2>{data.title}</h2>
          <p>{data.summary || "后端暂未提供摘要。"}</p>
        </div>
        <div className="risk-panel">
          <span>风险</span>
          <strong>{numberLabel(data.risk_score, " 分")}</strong>
          <em>{riskLabel(data.risk_level)}</em>
        </div>
      </section>

      <dl className="detail-grid">
        <Field label="情报类型" value={labelFromOptions(intelligenceTypeOptions, data.intelligence_type)} />
        <Field label="状态" value={data.status} />
        <Field label="CVE" value={data.cve_id} />
        <Field label="CWE" value={data.cwe_id} />
        <Field label="CVSS" value={[numberLabel(data.cvss_score), data.cvss_vector].filter((value) => value !== "-").join(" / ")} />
        <Field label="严重度" value={severityLabel(data.severity)} />
        <Field label="厂商" value={data.affected_vendor} />
        <Field label="产品" value={data.affected_product} />
        <Field label="版本" value={data.affected_version} />
        <Field label="车辆组件" value={labelFromOptions(vehicleComponentOptions, data.vehicle_component)} />
        <Field label="攻击面" value={labelFromOptions(attackSurfaceOptions, data.attack_surface)} />
        <Field label="利用状态" value={data.exploit_status} />
        <Field label="可信度" value={data.confidence} />
        <Field label="首次发现" value={dateTimeLabel(data.first_seen_at)} />
        <Field label="最近发现" value={dateTimeLabel(data.last_seen_at)} />
        <Field label="去重键" value={data.dedup_key} />
      </dl>

      <Section title="标签">
        <TagList values={data.tags} />
      </Section>

      <Section title="来源归属">
        <SourceList sources={data.sources} fallbackNames={data.source_names} fallbackUrls={data.source_urls} />
      </Section>

      <Section title="评分解释">
        <p className="detail-text">{data.score_explanation || "后端暂未返回评分解释。"}</p>
        <MetadataView value={data.score_metadata} />
      </Section>

      <Section title="关联告警">
        <RelatedAlerts alerts={data.related_alerts} />
      </Section>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value || "-"}</dd>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="detail-block">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

function TagList({ values = [] }) {
  if (!values.length) {
    return <p className="detail-text">无标签。</p>;
  }
  return (
    <div className="tag-list">
      {values.map((tag) => <span className="badge" key={tag}>{tag}</span>)}
    </div>
  );
}

function SourceList({ sources = [], fallbackNames = [], fallbackUrls = [] }) {
  const rows = sources.length ? sources : fallbackNames.map((name, index) => ({
    source_name: name,
    source_url: fallbackUrls[index]
  }));

  if (!rows.length) {
    return <p className="detail-text">无来源归属。</p>;
  }

  return (
    <div className="source-list">
      {rows.map((source, index) => (
        <div className="source-row" key={source.id || `${source.source_name}-${index}`}>
          <strong>{source.source_name || "未命名来源"}</strong>
          {source.source_url ? <a className="text-link" href={source.source_url} target="_blank" rel="noreferrer">打开来源</a> : <span>无链接</span>}
          <span>{source.external_id || "无外部编号"}</span>
          <span>{dateTimeLabel(source.last_seen_at || source.first_seen_at)}</span>
        </div>
      ))}
    </div>
  );
}

function MetadataView({ value }) {
  const entries = Object.entries(value || {});
  if (!entries.length) {
    return <p className="detail-text">无评分元数据。</p>;
  }
  return (
    <dl className="metadata-grid">
      {entries.map(([key, item]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{typeof item === "object" ? JSON.stringify(item) : String(item)}</dd>
        </div>
      ))}
    </dl>
  );
}

function RelatedAlerts({ alerts = [] }) {
  if (!alerts.length) {
    return <p className="detail-text">暂无关联告警。</p>;
  }
  return (
    <div className="table-wrap">
      <table className="dense-table">
        <thead>
          <tr>
            <th>标题</th>
            <th>风险</th>
            <th>状态</th>
            <th>触发时间</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => (
            <tr key={alert.id}>
              <td><Link className="text-link" href="/alerts">{alert.title}</Link></td>
              <td>{riskLabel(alert.risk_level)}</td>
              <td>{alert.status}</td>
              <td>{dateTimeLabel(alert.triggered_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
