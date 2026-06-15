const DEFAULT_API_BASE_URL = "/api";
const TOKEN_STORAGE_KEY = "sentineldrive.access_token";
export const SESSION_EXPIRED_EVENT = "sentineldrive:session-expired";

const STATUS_MESSAGES = {
  400: "请求参数不正确，请检查后重试。",
  401: "登录状态已过期，请重新登录。",
  403: "当前账号没有执行此操作的权限。",
  404: "请求的资源不存在。",
  409: "请求与现有数据冲突，请检查后重试。",
  422: "提交内容未通过校验，请检查字段后重试。"
};

const SENSITIVE_PATTERN = /(password|token|secret|api[_-]?key|authorization|bearer)\b/i;

export class ApiError extends Error {
  constructor(message, { status = null, code = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL;
}

export function getStoredToken() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function storeToken(token) {
  if (typeof window !== "undefined" && token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  }
}

export function clearStoredToken() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export function buildQuery(params = {}) {
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (isEmptyParam(value)) {
      return;
    }

    if (Array.isArray(value)) {
      value.filter((item) => !isEmptyParam(item)).forEach((item) => query.append(key, String(item)));
      return;
    }

    query.set(key, String(value));
  });

  return query.toString();
}

function isEmptyParam(value) {
  return value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
}

export function createApiClient(baseUrl = getApiBaseUrl()) {
  return {
    baseUrl,
    buildUrl(path, query = {}) {
      const normalizedBase = baseUrl.replace(/\/$/, "");
      const normalizedPath = path.startsWith("/") ? path : `/${path}`;
      const queryString = buildQuery(query);
      return `${normalizedBase}${normalizedPath}${queryString ? `?${queryString}` : ""}`;
    },

    async request(path, options = {}) {
      const {
        auth = true,
        body,
        headers = {},
        method = body === undefined ? "GET" : "POST",
        query,
        signal,
        token
      } = options;
      const requestHeaders = buildHeaders({ auth, body, headers, token });

      let response;
      try {
        response = await fetch(this.buildUrl(path, query), {
          body: serializeBody(body),
          headers: requestHeaders,
          method,
          signal
        });
      } catch (error) {
        throw new ApiError("无法连接后端服务，请检查网络或服务状态。");
      }

      if (!response.ok) {
        throw await normalizeApiError(response, { notifySessionExpired: auth });
      }

      if (response.status === 204) {
        return null;
      }

      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        return response.json();
      }

      return response.text();
    },

    async download(path, options = {}) {
      const { auth = true, body, headers = {}, method = "GET", query, token } = options;
      let response;
      try {
        response = await fetch(this.buildUrl(path, query), {
          body: serializeBody(body),
          headers: buildHeaders({ auth, body, headers, token }),
          method
        });
      } catch (error) {
        throw new ApiError("无法连接后端服务，请检查网络或服务状态。");
      }

      if (!response.ok) {
        throw await normalizeApiError(response, { notifySessionExpired: auth });
      }

      return {
        blob: await response.blob(),
        filename: filenameFromDisposition(response.headers.get("content-disposition")) || options.filename || "sentineldrive-export"
      };
    }
  };
}

function buildHeaders({ auth, body, headers, token }) {
  const requestHeaders = {
    Accept: "application/json",
    ...headers
  };
  const bearerToken = token || (auth ? getStoredToken() : null);

  if (body !== undefined && !(body instanceof FormData) && !requestHeaders["Content-Type"]) {
    requestHeaders["Content-Type"] = "application/json";
  }
  if (auth && bearerToken) {
    requestHeaders.Authorization = `Bearer ${bearerToken}`;
  }

  return requestHeaders;
}

function serializeBody(body) {
  if (body === undefined || body instanceof FormData || typeof body === "string") {
    return body;
  }
  return JSON.stringify(body);
}

async function normalizeApiError(response, { notifySessionExpired = true } = {}) {
  const payload = await safeResponsePayload(response);
  const { message, code } = extractError(payload, response.status);

  if (response.status === 401) {
    clearStoredToken();
    if (notifySessionExpired && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
    }
  }

  return new ApiError(message, { status: response.status, code });
}

async function safeResponsePayload(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  try {
    return await response.json();
  } catch (error) {
    return null;
  }
}

function extractError(payload, status) {
  const candidates = [
    payload?.detail?.error,
    payload?.error,
    payload?.detail
  ];

  for (const candidate of candidates) {
    if (!candidate) {
      continue;
    }
    if (typeof candidate === "object" && typeof candidate.message === "string") {
      return {
        code: typeof candidate.code === "string" ? candidate.code : null,
        message: safeUserMessage(candidate.message, status)
      };
    }
    if (typeof candidate === "string") {
      return { code: null, message: safeUserMessage(candidate, status) };
    }
  }

  return { code: null, message: STATUS_MESSAGES[status] || "请求失败，请稍后重试。" };
}

function safeUserMessage(message, status) {
  const trimmed = message.trim();
  if (!trimmed || SENSITIVE_PATTERN.test(trimmed) || trimmed.length > 180) {
    return STATUS_MESSAGES[status] || "请求失败，请稍后重试。";
  }
  return trimmed;
}

function filenameFromDisposition(disposition) {
  if (!disposition) {
    return null;
  }
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] || null;
}

export function saveDownload({ blob, filename }) {
  if (typeof window === "undefined") {
    return;
  }
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export const apiClient = createApiClient();
