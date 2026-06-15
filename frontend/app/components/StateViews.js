"use client";

import { useState } from "react";
import { getApiBaseUrl } from "../../lib/apiClient";
import { useAuth } from "./AuthProvider";

export function LoadingState({ title = "正在加载", description = "正在从后端读取数据。" }) {
  return (
    <div className="state-box state-loading" role="status" aria-live="polite">
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}

export function ErrorState({ title = "请求失败", message, onRetry }) {
  return (
    <div className="state-box state-error" role="alert">
      <strong>{title}</strong>
      <span>{message || "操作未完成，请稍后重试。"}</span>
      {onRetry ? <button className="secondary-button" type="button" onClick={onRetry}>重试</button> : null}
    </div>
  );
}

export function EmptyDataState({ title = "暂无数据", description = "当前筛选条件下没有可显示的记录。" }) {
  return (
    <div className="state-box">
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}

export function SessionExpiredState() {
  return (
    <div className="state-box state-error" role="alert">
      <strong>登录状态已过期</strong>
      <span>请重新登录后继续操作。</span>
    </div>
  );
}

export function AdminOnly({ children, fallback = "仅管理员可用" }) {
  const { isAdmin } = useAuth();

  if (isAdmin) {
    return children;
  }

  return (
    <button className="secondary-button" type="button" disabled title={fallback}>
      {fallback}
    </button>
  );
}

export function LoginScreen() {
  const { error, login, status } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState("");
  const submitting = status === "checking";

  async function handleSubmit(event) {
    event.preventDefault();
    setLocalError("");

    if (!email.trim() || !password) {
      setLocalError("请输入邮箱和密码。");
      return;
    }

    const result = await login({ email: email.trim(), password });
    if (!result.ok) {
      setLocalError(result.message || "登录失败，请检查邮箱和密码。");
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <div>
          <div className="brand-name login-brand">SentinelDrive</div>
          <p className="login-subtitle">车联网威胁情报工作台</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>邮箱</span>
            <input
              autoComplete="email"
              inputMode="email"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="admin@example.test"
              type="email"
              value={email}
            />
          </label>
          <label className="field">
            <span>密码</span>
            <input
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
              placeholder="输入登录密码"
              type="password"
              value={password}
            />
          </label>

          {localError || error ? <ErrorState message={localError || error} title="无法登录" /> : null}

          <button className="primary-button" type="submit" disabled={submitting}>
            {submitting ? "正在登录" : "登录工作台"}
          </button>
        </form>

        <div className="login-meta">API 基址：{getApiBaseUrl()}</div>
      </section>
    </main>
  );
}
