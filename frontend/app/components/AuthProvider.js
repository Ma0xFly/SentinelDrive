"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { clearStoredToken, getStoredToken, SESSION_EXPIRED_EVENT, storeToken } from "../../lib/apiClient";
import { authApi } from "../../lib/endpoints";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("checking");
  const [error, setError] = useState("");

  const clearSession = useCallback((message = "") => {
    clearStoredToken();
    setToken(null);
    setUser(null);
    setError(message);
    setStatus("unauthenticated");
  }, []);

  const refreshUser = useCallback(async () => {
    setStatus("checking");
    try {
      const currentUser = await authApi.currentUser();
      setUser(currentUser);
      setError("");
      setStatus("authenticated");
      return currentUser;
    } catch (requestError) {
      clearSession(requestError.message || "登录状态已过期，请重新登录。");
      return null;
    }
  }, [clearSession]);

  useEffect(() => {
    const storedToken = getStoredToken();
    if (!storedToken) {
      setStatus("unauthenticated");
      return;
    }
    setToken(storedToken);
    refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    function handleExpired() {
      clearSession("登录状态已过期，请重新登录。");
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, handleExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleExpired);
  }, [clearSession]);

  const login = useCallback(async ({ email, password }) => {
    setStatus("checking");
    setError("");
    try {
      const response = await authApi.login({ email, password });
      storeToken(response.access_token);
      setToken(response.access_token);
      const currentUser = await authApi.currentUser();
      setUser(currentUser);
      setStatus("authenticated");
      return { ok: true };
    } catch (requestError) {
      clearSession(requestError.message || "登录失败，请检查邮箱和密码。");
      return { ok: false, message: requestError.message };
    }
  }, [clearSession]);

  const logout = useCallback(async () => {
    try {
      if (getStoredToken()) {
        await authApi.logout();
      }
    } catch (requestError) {
      // Stateless tokens are cleared locally even if the audit-only logout call fails.
    } finally {
      clearSession("");
    }
  }, [clearSession]);

  const value = useMemo(() => ({
    clearSession,
    error,
    isAdmin: Boolean(user?.is_admin),
    isAuthenticated: status === "authenticated",
    login,
    logout,
    refreshUser,
    status,
    token,
    user
  }), [clearSession, error, login, logout, refreshUser, status, token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
