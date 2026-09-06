import { request } from '@umijs/max';

/** 告警列表 GET /alerts */
export async function listAlerts(
  params?: API.AlertListParams,
  options?: { [key: string]: any },
) {
  return request<API.Page<API.Alert>>('/alerts', {
    method: 'GET',
    params,
    ...(options || {}),
  });
}

/** 告警详情 GET /alerts/{alert_id} */
export async function getAlert(
  alertId: string,
  options?: { [key: string]: any },
) {
  return request<API.AlertDetail>(`/alerts/${alertId}`, {
    method: 'GET',
    ...(options || {}),
  });
}

/** 更新告警状态 PATCH /alerts/{alert_id}/status */
export async function updateAlertStatus(
  alertId: string,
  body: API.AlertStatusUpdateParams,
  options?: { [key: string]: any },
) {
  return request<API.AlertDetail>(`/alerts/${alertId}/status`, {
    method: 'PATCH',
    data: body,
    ...(options || {}),
  });
}

/** 触发告警评估 POST /alerts/evaluate */
export async function evaluateAlerts(
  body?: API.AlertEvaluateParams,
  options?: { [key: string]: any },
) {
  return request<API.AlertGenerationResult>('/alerts/evaluate', {
    method: 'POST',
    data: body ?? {},
    ...(options || {}),
  });
}
