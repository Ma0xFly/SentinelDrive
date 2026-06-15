"use client";

import { useState } from "react";
import { alertsApi, exportsApi, intelligenceApi, manualEntriesApi, sourcesApi, usersApi } from "../../lib/endpoints";
import { useApiResource } from "../../lib/dataHooks";
import { useAuth } from "./AuthProvider";
import { AdminOnly, EmptyDataState, ErrorState, LoadingState } from "./StateViews";

export function IntelligenceDataPanel() {
  const { data, error, loading, reload } = useApiResource(
    () => intelligenceApi.list({ sort: "recent", page: 1, limit: 5 }),
    []
  );

  if (loading) {
    return <LoadingState title="正在加载情报" description="读取最新情报列表。" />;
  }
  if (error) {
    return <ErrorState message={error} onRetry={reload} />;
  }
  if (!data?.items?.length) {
    return <EmptyDataState title="暂无情报记录" description="后端暂未返回情报数据。" />;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>标题</th>
            <th>来源</th>
            <th>风险</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={item.id}>
              <td>{item.title}</td>
              <td>{(item.source_names || []).join("、") || "未标注"}</td>
              <td>{riskLabel(item.risk_level)}</td>
              <td>{item.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AlertsDataPanel() {
  const { data, error, loading, reload } = useApiResource(
    () => alertsApi.list({ sort: "recent", page: 1, limit: 5 }),
    []
  );

  if (loading) {
    return <LoadingState title="正在加载告警" description="读取最新告警队列。" />;
  }
  if (error) {
    return <ErrorState message={error} onRetry={reload} />;
  }
  if (!data?.items?.length) {
    return <EmptyDataState title="暂无告警" description="当前没有符合条件的告警。" />;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>标题</th>
            <th>规则</th>
            <th>风险</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={item.id}>
              <td>{item.title}</td>
              <td>{item.triggering_rule}</td>
              <td>{riskLabel(item.risk_level)}</td>
              <td>{alertStatusLabel(item.status)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SourcesDataPanel() {
  const { data, error, loading, reload } = useApiResource(
    () => sourcesApi.list({ sort: "name", page: 1, limit: 5 }),
    []
  );

  if (loading) {
    return <LoadingState title="正在加载来源" description="读取来源状态和最近任务摘要。" />;
  }
  if (error) {
    return <ErrorState message={error} onRetry={reload} />;
  }
  if (!data?.items?.length) {
    return <EmptyDataState title="暂无来源" description="后端暂未返回来源配置。" />;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>来源</th>
            <th>类型</th>
            <th>状态</th>
            <th>失败次数</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={item.id}>
              <td>{item.name}</td>
              <td>{item.source_type}</td>
              <td>{sourceStatusLabel(item.status)}</td>
              <td>{item.failure_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ManualEntriesDataPanel() {
  const { data, error, loading, reload } = useApiResource(() => manualEntriesApi.list(), []);

  if (loading) {
    return <LoadingState title="正在加载手工条目" description="读取已录入的人工情报。" />;
  }
  if (error) {
    return <ErrorState message={error} onRetry={reload} />;
  }
  if (!data?.length) {
    return <EmptyDataState title="暂无手工录入" description="尚未提交人工情报记录。" />;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>标题</th>
            <th>类别</th>
            <th>来源</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr key={item.id}>
              <td>{item.title}</td>
              <td>{manualCategoryLabel(item.category)}</td>
              <td>{item.source_name}</td>
              <td>{manualStatusLabel(item.status)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function UserBasicsPanel() {
  const { isAdmin, user } = useAuth();
  const { data, error, loading, reload } = useApiResource(
    () => (isAdmin ? usersApi.list() : Promise.resolve([])),
    [isAdmin]
  );

  return (
    <>
      <dl className="detail-grid">
        <div>
          <dt>账号</dt>
          <dd>{user?.email}</dd>
        </div>
        <div>
          <dt>权限范围</dt>
          <dd>{isAdmin ? "管理员" : "操作员"}</dd>
        </div>
        <div>
          <dt>会话状态</dt>
          <dd>已登录</dd>
        </div>
        <div>
          <dt>最近登录</dt>
          <dd>{formatDate(user?.last_login_at)}</dd>
        </div>
      </dl>
      <div className="admin-action-row">
        <AdminOnly />
      </div>
      {isAdmin ? <UsersTable data={data} error={error} loading={loading} reload={reload} /> : null}
    </>
  );
}

function UsersTable({ data, error, loading, reload }) {
  if (loading) {
    return <LoadingState title="正在加载用户" description="读取管理员用户列表。" />;
  }
  if (error) {
    return <ErrorState message={error} onRetry={reload} />;
  }
  if (!data?.length) {
    return <EmptyDataState title="暂无用户列表" description="后端暂未返回用户记录。" />;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>邮箱</th>
            <th>名称</th>
            <th>管理员</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr key={item.id}>
              <td>{item.email}</td>
              <td>{item.display_name || "-"}</td>
              <td>{item.is_admin ? "是" : "否"}</td>
              <td>{item.is_active ? "启用" : "停用"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ExportActions({ type = "intelligence" }) {
  const [error, setError] = useState("");

  async function runDownload(download) {
    setError("");
    try {
      await download();
    } catch (requestError) {
      setError(requestError.message || "导出失败，请稍后重试。");
    }
  }

  return (
    <div className="export-actions">
      {type === "alerts" ? (
        <button className="secondary-button" type="button" onClick={() => runDownload(() => exportsApi.alertsCsv())}>
          导出告警 CSV
        </button>
      ) : (
        <button className="secondary-button" type="button" onClick={() => runDownload(() => exportsApi.intelligenceCsv())}>
          导出情报 CSV
        </button>
      )}
      <button className="secondary-button" type="button" onClick={() => runDownload(() => exportsApi.summaryPdf())}>
        导出摘要 PDF
      </button>
      {error ? <span className="inline-error">{error}</span> : null}
    </div>
  );
}

function formatDate(value) {
  if (!value) {
    return "暂无记录";
  }
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function riskLabel(value) {
  return {
    critical: "严重",
    high: "高",
    medium: "中",
    low: "低",
    info: "信息"
  }[value] || value || "未知";
}

function alertStatusLabel(value) {
  return {
    open: "未确认",
    acknowledged: "已确认",
    in_progress: "处理中",
    closed: "已关闭"
  }[value] || value || "未知";
}

function sourceStatusLabel(value) {
  return {
    enabled: "启用",
    disabled: "停用",
    error: "异常"
  }[value] || value || "未知";
}

function manualCategoryLabel(value) {
  return {
    vulnerability: "漏洞",
    advisory: "公告",
    incident: "事件",
    exposure: "暴露面",
    research_lead: "研究线索"
  }[value] || value || "未知";
}

function manualStatusLabel(value) {
  return {
    active: "有效",
    under_review: "复核中",
    resolved: "已解决",
    dismissed: "已忽略"
  }[value] || value || "未知";
}
