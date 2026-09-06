import { request } from '@umijs/max';

/** 手工录入列表（后端返回全量数组） GET /manual-entries */
export async function listManualEntries(options?: { [key: string]: any }) {
  return request<API.ManualEntry[]>('/manual-entries', {
    method: 'GET',
    ...(options || {}),
  });
}

/** 新建手工录入 POST /manual-entries */
export async function createManualEntry(
  body: API.ManualEntryCreateParams,
  options?: { [key: string]: any },
) {
  return request<API.ManualEntry>('/manual-entries', {
    method: 'POST',
    data: body,
    ...(options || {}),
  });
}

/** 手工录入详情 GET /manual-entries/{entry_id} */
export async function getManualEntry(
  entryId: string,
  options?: { [key: string]: any },
) {
  return request<API.ManualEntry>(`/manual-entries/${entryId}`, {
    method: 'GET',
    ...(options || {}),
  });
}

/** 更新手工录入 PATCH /manual-entries/{entry_id} */
export async function updateManualEntry(
  entryId: string,
  body: API.ManualEntryUpdateParams,
  options?: { [key: string]: any },
) {
  return request<API.ManualEntry>(`/manual-entries/${entryId}`, {
    method: 'PATCH',
    data: body,
    ...(options || {}),
  });
}
