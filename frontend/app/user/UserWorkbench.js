"use client";

import { useCallback, useEffect, useState } from "react";
import { usersApi } from "../../lib/endpoints";
import { useAuth } from "../components/AuthProvider";
import { EmptyDataState, ErrorState, LoadingState } from "../components/StateViews";
import { Toolbar } from "../components/WorkbenchShell";
import { dateTimeLabel } from "../intelligence/labels";

const emptyUserForm = {
  email: "",
  password: "",
  display_name: "",
  is_admin: false
};

export function UserWorkbench() {
  const { isAdmin, user } = useAuth();
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(emptyUserForm);
  const [loading, setLoading] = useState(isAdmin);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!isAdmin) {
      setUsers([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      setUsers(await usersApi.list());
    } catch (requestError) {
      setError(requestError.message || "用户列表加载失败。");
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    load();
  }, [load]);

  function updateField(name, value) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function createUser(event) {
    event.preventDefault();
    setFormError("");
    setSuccess("");
    const validation = validateUserForm(form);
    if (validation) {
      setFormError(validation);
      return;
    }
    setSaving(true);
    try {
      await usersApi.create({
        email: form.email.trim(),
        password: form.password,
        display_name: form.display_name.trim() || null,
        is_admin: form.is_admin
      });
      setSuccess("用户已创建。");
      setForm(emptyUserForm);
      await load();
    } catch (requestError) {
      setFormError(requestError.message || "用户创建失败。");
    } finally {
      setSaving(false);
    }
  }

  async function updateStatus(id, isActive) {
    setError("");
    try {
      await usersApi.updateStatus(id, { is_active: isActive });
      await load();
    } catch (requestError) {
      setError(requestError.message || "用户状态更新失败。");
    }
  }

  return (
    <div className="split-workbench">
      <section className="split-primary">
        <div className="detail-summary">
          <div>
            <h2>{user?.display_name || user?.email}</h2>
            <p>当前账号：{user?.email}</p>
          </div>
          <div className="risk-panel">
            <span>权限</span>
            <strong>{isAdmin ? "管理员" : "操作员"}</strong>
            <em>{user?.is_active ? "启用" : "停用"}</em>
          </div>
        </div>
        <dl className="detail-grid">
          <div><dt>用户 ID</dt><dd>{user?.id}</dd></div>
          <div><dt>最近登录</dt><dd>{dateTimeLabel(user?.last_login_at)}</dd></div>
          <div><dt>创建时间</dt><dd>{dateTimeLabel(user?.created_at)}</dd></div>
          <div><dt>更新时间</dt><dd>{dateTimeLabel(user?.updated_at)}</dd></div>
        </dl>
      </section>

      <aside className="split-detail">
        <h3>用户管理</h3>
        {!isAdmin ? <EmptyDataState title="仅管理员可管理用户" description="当前账号可以查看自己的基础信息，不能创建或停用用户。" /> : null}
        {isAdmin ? (
          <>
            <form className="stack-form" onSubmit={createUser}>
              <label className="field">
                <span>邮箱</span>
                <input value={form.email} placeholder="user@example.test" onChange={(event) => updateField("email", event.target.value)} />
              </label>
              <label className="field">
                <span>显示名</span>
                <input value={form.display_name} placeholder="可选" onChange={(event) => updateField("display_name", event.target.value)} />
              </label>
              <label className="field">
                <span>初始密码</span>
                <input value={form.password} type="password" placeholder="至少 8 位，不会回显保存" onChange={(event) => updateField("password", event.target.value)} />
              </label>
              <label className="checkbox-field">
                <input checked={form.is_admin} type="checkbox" onChange={(event) => updateField("is_admin", event.target.checked)} />
                <span>设为管理员</span>
              </label>
              <button className="primary-button" type="submit" disabled={saving}>{saving ? "创建中" : "创建用户"}</button>
              {formError ? <span className="inline-error">{formError}</span> : null}
              {success ? <span className="inline-success">{success}</span> : null}
            </form>

            <Toolbar>
              <button className="secondary-button" type="button" onClick={load}>刷新用户</button>
            </Toolbar>
            {loading ? <LoadingState title="正在加载用户" /> : null}
            {!loading && error ? <ErrorState message={error} onRetry={load} /> : null}
            {!loading && !error && !users.length ? <EmptyDataState title="暂无用户" description="创建后会显示在这里。" /> : null}
            {!loading && !error && users.length ? <UsersList users={users} onStatus={updateStatus} currentUserId={user?.id} /> : null}
          </>
        ) : null}
      </aside>
    </div>
  );
}

function UsersList({ users, onStatus, currentUserId }) {
  return (
    <div className="record-list">
      {users.map((item) => (
        <div className="record-item" key={item.id}>
          <strong>{item.email}</strong>
          <span>{item.display_name || "无显示名"} / {item.is_admin ? "管理员" : "操作员"}</span>
          <span>{item.is_active ? "启用" : "停用"} · 最近登录 {dateTimeLabel(item.last_login_at)}</span>
          <button
            className="text-button"
            type="button"
            disabled={item.id === currentUserId}
            onClick={() => onStatus(item.id, !item.is_active)}
          >
            {item.is_active ? "停用" : "启用"}
          </button>
        </div>
      ))}
    </div>
  );
}

function validateUserForm(value) {
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.email.trim())) {
    return "请输入有效邮箱。";
  }
  if (value.password.length < 8) {
    return "初始密码至少 8 位。";
  }
  return "";
}
