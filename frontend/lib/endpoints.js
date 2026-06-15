import { apiClient, saveDownload } from "./apiClient";

export const authApi = {
  login(payload) {
    return apiClient.request("/auth/login", { auth: false, body: payload });
  },
  currentUser() {
    return apiClient.request("/auth/me");
  },
  logout() {
    return apiClient.request("/auth/logout", { method: "POST" });
  }
};

export const intelligenceApi = {
  list(filters = {}) {
    return apiClient.request("/intelligence", { query: filters });
  },
  detail(id) {
    return apiClient.request(`/intelligence/${id}`);
  }
};

export const alertsApi = {
  list(filters = {}) {
    return apiClient.request("/alerts", { query: filters });
  },
  detail(id) {
    return apiClient.request(`/alerts/${id}`);
  },
  evaluate(payload = {}) {
    return apiClient.request("/alerts/evaluate", { body: payload });
  },
  updateStatus(id, payload) {
    return apiClient.request(`/alerts/${id}/status`, { method: "PATCH", body: payload });
  }
};

export const sourcesApi = {
  list(filters = {}) {
    return apiClient.request("/sources", { query: filters });
  },
  detail(id) {
    return apiClient.request(`/sources/${id}`);
  },
  jobs(filters = {}) {
    return apiClient.request("/sources/jobs", { query: filters });
  },
  pipelineStatus() {
    return apiClient.request("/sources/pipeline/status");
  },
  triggerPipeline(payload = {}) {
    return apiClient.request("/sources/pipeline/trigger", { body: payload });
  },
  updateStatus(id, payload) {
    return apiClient.request(`/sources/${id}/status`, { method: "PATCH", body: payload });
  }
};

export const manualEntriesApi = {
  list() {
    return apiClient.request("/manual-entries");
  },
  detail(id) {
    return apiClient.request(`/manual-entries/${id}`);
  },
  create(payload) {
    return apiClient.request("/manual-entries", { body: payload });
  },
  update(id, payload) {
    return apiClient.request(`/manual-entries/${id}`, { method: "PATCH", body: payload });
  }
};

export const usersApi = {
  list() {
    return apiClient.request("/users");
  },
  create(payload) {
    return apiClient.request("/users", { body: payload });
  },
  updateStatus(id, payload) {
    return apiClient.request(`/users/${id}/status`, { method: "PATCH", body: payload });
  }
};

export const exportsApi = {
  async intelligenceCsv(filters = {}) {
    return saveDownload(await apiClient.download("/exports/intelligence.csv", { query: filters }));
  },
  async intelligenceMarkdown(id) {
    return saveDownload(await apiClient.download(`/exports/intelligence/${id}/markdown`));
  },
  async alertsCsv(filters = {}) {
    return saveDownload(await apiClient.download("/exports/alerts.csv", { query: filters }));
  },
  async summaryPdf(filters = {}) {
    return saveDownload(await apiClient.download("/exports/summary.pdf", { query: filters }));
  }
};
