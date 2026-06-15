"use client";

import { useCallback, useEffect, useState } from "react";
import { manualEntriesApi } from "../../lib/endpoints";
import { EmptyDataState, ErrorState, LoadingState } from "../components/StateViews";
import { Toolbar } from "../components/WorkbenchShell";
import { attackSurfaceOptions, dateTimeLabel, riskLevelOptions, severityLabel, vehicleComponentOptions } from "../intelligence/labels";

const categoryOptions = [
  ["vulnerability", "漏洞"],
  ["advisory", "公告"],
  ["incident", "事件"],
  ["exposure", "暴露面"],
  ["research_lead", "研究线索"]
];

const severityOptions = [
  ["unknown", "未知"],
  ["low", "低"],
  ["medium", "中"],
  ["high", "高"],
  ["critical", "严重"]
];

const exploitOptions = [
  ["unknown", "未知"],
  ["none_known", "未发现利用"],
  ["proof_of_concept", "PoC"],
  ["exploited", "已利用"]
];

const confidenceOptions = [
  ["low", "低"],
  ["medium", "中"],
  ["high", "高"]
];

const statusOptions = [
  ["active", "有效"],
  ["under_review", "复核中"],
  ["resolved", "已解决"],
  ["dismissed", "已忽略"]
];

const emptyForm = {
  category: "vulnerability",
  title: "",
  summary: "",
  source_name: "",
  source_url: "",
  cve_id: "",
  cwe_id: "",
  cvss_score: "",
  cvss_vector: "",
  severity: "unknown",
  affected_vendor: "",
  affected_product: "",
  affected_version: "",
  vehicle_component: "",
  attack_surface: "",
  exploit_status: "unknown",
  confidence: "medium",
  risk_score: "",
  risk_level: "info",
  tags: "",
  status: "under_review"
};

export function ManualEntryWorkbench() {
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setEntries(await manualEntriesApi.list());
    } catch (requestError) {
      setError(requestError.message || "手工录入列表加载失败。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function updateField(name, value) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function startEdit(entry) {
    setEditingId(entry.id);
    setForm({
      category: entry.category || "vulnerability",
      title: entry.title || "",
      summary: entry.summary || "",
      source_name: entry.source_name || "",
      source_url: entry.source_url || "",
      cve_id: entry.cve_id || "",
      cwe_id: entry.cwe_id || "",
      cvss_score: entry.cvss_score ?? "",
      cvss_vector: entry.cvss_vector || "",
      severity: entry.severity || "unknown",
      affected_vendor: entry.affected_vendor || "",
      affected_product: entry.affected_product || "",
      affected_version: entry.affected_version || "",
      vehicle_component: entry.vehicle_component || "",
      attack_surface: entry.attack_surface || "",
      exploit_status: entry.exploit_status || "unknown",
      confidence: entry.confidence || "medium",
      risk_score: entry.risk_score ?? "",
      risk_level: entry.risk_level || "info",
      tags: (entry.tags || []).filter((tag) => tag !== "manual").join(", "),
      status: entry.status || "under_review"
    });
    setSuccess("");
    setFormError("");
  }

  function resetForm() {
    setForm(emptyForm);
    setEditingId(null);
    setFormError("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError("");
    setSuccess("");
    const validation = validateForm(form);
    if (validation) {
      setFormError(validation);
      return;
    }
    setSaving(true);
    try {
      const payload = formToPayload(form);
      if (editingId) {
        await manualEntriesApi.update(editingId, payload);
        setSuccess("手工情报已更新。");
      } else {
        await manualEntriesApi.create(payload);
        setSuccess("手工情报已提交。");
      }
      resetForm();
      await load();
    } catch (requestError) {
      setFormError(requestError.message || "提交失败，请稍后重试。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="split-workbench">
      <section className="split-primary">
        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <SelectField label="类别" name="category" value={form.category} onChange={updateField} options={categoryOptions} />
            <TextField label="标题" name="title" value={form.title} onChange={updateField} placeholder="至少 3 个字符" />
            <TextField label="来源名称" name="source_name" value={form.source_name} onChange={updateField} placeholder="厂商公告、内部分析" />
            <TextField label="来源 URL" name="source_url" value={form.source_url} onChange={updateField} placeholder="https://example.test/advisory" />
            <TextField label="CVE" name="cve_id" value={form.cve_id} onChange={updateField} placeholder="CVE-2026-0001" />
            <TextField label="CWE" name="cwe_id" value={form.cwe_id} onChange={updateField} placeholder="CWE-79" />
            <TextField label="CVSS 分" name="cvss_score" value={form.cvss_score} onChange={updateField} placeholder="0-10" />
            <TextField label="CVSS 向量" name="cvss_vector" value={form.cvss_vector} onChange={updateField} placeholder="CVSS:3.1/..." />
            <SelectField label="严重度" name="severity" value={form.severity} onChange={updateField} options={severityOptions} />
            <SelectField label="风险等级" name="risk_level" value={form.risk_level} onChange={updateField} options={riskLevelOptions} />
            <TextField label="厂商" name="affected_vendor" value={form.affected_vendor} onChange={updateField} placeholder="厂商" />
            <TextField label="产品" name="affected_product" value={form.affected_product} onChange={updateField} placeholder="产品或系统" />
            <TextField label="版本" name="affected_version" value={form.affected_version} onChange={updateField} placeholder="版本范围" />
            <SelectField label="车辆组件" name="vehicle_component" value={form.vehicle_component} onChange={updateField} options={vehicleComponentOptions} includeAll />
            <SelectField label="攻击面" name="attack_surface" value={form.attack_surface} onChange={updateField} options={attackSurfaceOptions} includeAll />
            <SelectField label="利用状态" name="exploit_status" value={form.exploit_status} onChange={updateField} options={exploitOptions} />
            <SelectField label="可信度" name="confidence" value={form.confidence} onChange={updateField} options={confidenceOptions} />
            <TextField label="风险分" name="risk_score" value={form.risk_score} onChange={updateField} placeholder="0-100" />
            <TextField label="标签" name="tags" value={form.tags} onChange={updateField} placeholder="逗号分隔，不要填写密钥" />
            <SelectField label="状态" name="status" value={form.status} onChange={updateField} options={statusOptions} />
            <label className="field field-wide">
              <span>摘要</span>
              <textarea value={form.summary} rows="6" placeholder="记录影响范围、触发条件和处置线索" onChange={(event) => updateField("summary", event.target.value)} />
            </label>
          </div>
          <Toolbar>
            <button className="primary-button" type="submit" disabled={saving}>{saving ? "提交中" : editingId ? "更新条目" : "提交条目"}</button>
            <button className="secondary-button" type="button" onClick={resetForm}>清空</button>
            {editingId ? <span className="table-message">正在编辑已有条目</span> : null}
            {formError ? <span className="inline-error">{formError}</span> : null}
            {success ? <span className="inline-success">{success}</span> : null}
          </Toolbar>
        </form>
      </section>

      <aside className="split-detail">
        <h3>已录入条目</h3>
        {loading ? <LoadingState title="正在加载手工条目" /> : null}
        {!loading && error ? <ErrorState message={error} onRetry={load} /> : null}
        {!loading && !error && !entries.length ? <EmptyDataState title="暂无手工录入" description="提交后会显示在这里。" /> : null}
        {!loading && !error && entries.length ? <ManualEntryList entries={entries} onEdit={startEdit} /> : null}
      </aside>
    </div>
  );
}

function ManualEntryList({ entries, onEdit }) {
  return (
    <div className="record-list">
      {entries.map((entry) => (
        <div className="record-item" key={entry.id}>
          <strong>{entry.title}</strong>
          <span>{categoryLabel(entry.category)} / {severityLabel(entry.severity)} / {entry.status}</span>
          <span>{entry.source_name} · {dateTimeLabel(entry.updated_at)}</span>
          <button className="text-button" type="button" onClick={() => onEdit(entry)}>编辑</button>
        </div>
      ))}
    </div>
  );
}

function TextField({ label, name, value, onChange, placeholder }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} placeholder={placeholder} onChange={(event) => onChange(name, event.target.value)} />
    </label>
  );
}

function SelectField({ label, name, value, onChange, options, includeAll = false }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(name, event.target.value)}>
        {includeAll ? <option value="">不指定</option> : null}
        {options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}
      </select>
    </label>
  );
}

function validateForm(value) {
  if (value.title.trim().length < 3) {
    return "标题至少需要 3 个字符。";
  }
  if (!value.summary.trim()) {
    return "摘要不能为空。";
  }
  if (!value.source_name.trim() && !value.source_url.trim()) {
    return "来源名称和来源 URL 至少填写一个。";
  }
  if (value.source_url && !/^https?:\/\/\S+$/i.test(value.source_url.trim())) {
    return "来源 URL 必须是 http 或 https 开头的完整地址。";
  }
  if (value.cve_id && !/^CVE-\d{4}-\d{4,}$/i.test(value.cve_id.trim())) {
    return "CVE 格式应为 CVE-YYYY-NNNN。";
  }
  if (value.cvss_score && !between(value.cvss_score, 0, 10)) {
    return "CVSS 分数必须在 0 到 10 之间。";
  }
  if (value.risk_score && !between(value.risk_score, 0, 100)) {
    return "风险分必须在 0 到 100 之间。";
  }
  if (/password|token|secret|api[_-]?key/i.test(`${value.title} ${value.summary} ${value.tags}`)) {
    return "标题、摘要或标签中不能包含未脱敏的凭证字段。";
  }
  return "";
}

function between(value, min, max) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= min && parsed <= max;
}

function formToPayload(value) {
  const payload = {
    category: value.category,
    title: value.title.trim(),
    summary: value.summary.trim(),
    severity: value.severity,
    exploit_status: value.exploit_status,
    confidence: value.confidence,
    risk_level: value.risk_level,
    tags: value.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
    status: value.status
  };

  [
    "source_name",
    "source_url",
    "cve_id",
    "cwe_id",
    "cvss_vector",
    "affected_vendor",
    "affected_product",
    "affected_version",
    "vehicle_component",
    "attack_surface"
  ].forEach((key) => {
    if (value[key]) {
      payload[key] = value[key].trim();
    }
  });

  if (value.cvss_score !== "") {
    payload.cvss_score = Number(value.cvss_score);
  }
  if (value.risk_score !== "") {
    payload.risk_score = Number(value.risk_score);
  }

  return payload;
}

function categoryLabel(value) {
  return categoryOptions.find(([key]) => key === value)?.[1] || value || "-";
}
