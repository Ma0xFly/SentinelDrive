"use client";

import Link from "next/link";
import { getApiBaseUrl } from "../../lib/apiClient";
import { useAuth } from "./AuthProvider";
import { LoadingState, LoginScreen, SessionExpiredState } from "./StateViews";

const navigationItems = [
  { href: "/", label: "情报列表" },
  { href: "/alerts", label: "告警" },
  { href: "/sources", label: "来源管理" },
  { href: "/manual-entry", label: "手工录入" },
  { href: "/user", label: "用户基础" }
];

export function WorkbenchShell({ active = "/", title, eyebrow, actions, children }) {
  const { error, logout, status, user } = useAuth();
  const sessionExpired = error === "登录状态已过期，请重新登录。";

  if (status === "checking") {
    return <LoadingState title="正在校验登录状态" description="请稍候，工作台正在确认当前会话。" />;
  }

  if (status !== "authenticated") {
    return (
      <>
        {sessionExpired ? <SessionExpiredState /> : null}
        <LoginScreen />
      </>
    );
  }

  return (
    <div className="workbench-shell">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand-block">
          <span className="brand-mark" aria-hidden="true">SD</span>
          <div>
            <div className="brand-name">SentinelDrive</div>
            <div className="brand-subtitle">车联网威胁情报</div>
          </div>
        </div>

        <nav className="nav-list" aria-label="工作台页面">
          {navigationItems.map((item) => (
            <Link
              className={`nav-link${item.href === active ? " nav-link-active" : ""}`}
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="status-dot" aria-hidden="true" />
          <span>接口：{getApiBaseUrl()}</span>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <div className="eyebrow">{eyebrow}</div>
            <h1>{title}</h1>
          </div>
          <div className="topbar-actions">
            <div className="user-chip">
              <span>{user?.display_name || user?.email}</span>
              <small>{user?.is_admin ? "管理员" : "操作员"}</small>
            </div>
            {actions}
            <button className="secondary-button" type="button" onClick={logout}>退出</button>
          </div>
        </header>
        <main className="content-area">{children}</main>
      </div>
    </div>
  );
}

export function PageSection({ title, description, children }) {
  return (
    <section className="page-section">
      <div className="section-header">
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

export function Toolbar({ children }) {
  return <div className="toolbar">{children}</div>;
}

export function MetricStrip({ items }) {
  return (
    <div className="metric-strip">
      {items.map((item) => (
        <div className="metric-item" key={item.label}>
          <span className="metric-label">{item.label}</span>
          <strong>{item.value}</strong>
          <span className={`metric-tone metric-${item.tone || "neutral"}`}>{item.note}</span>
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}
