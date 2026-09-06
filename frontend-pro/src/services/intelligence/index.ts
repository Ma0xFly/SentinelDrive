import { request } from '@umijs/max';

/** 威胁情报列表 GET /intelligence */
export async function listIntelligence(
  params?: API.IntelligenceListParams,
  options?: { [key: string]: any },
) {
  return request<API.Page<API.IntelligenceListItem>>('/intelligence', {
    method: 'GET',
    params,
    ...(options || {}),
  });
}

/** 威胁情报详情 GET /intelligence/{intelligence_id} */
export async function getIntelligence(
  intelligenceId: string,
  options?: { [key: string]: any },
) {
  return request<API.IntelligenceDetail>(`/intelligence/${intelligenceId}`, {
    method: 'GET',
    ...(options || {}),
  });
}

/** 外部/AI 情报接入 POST /intelligence/ingest */
export async function ingestIntelligence(
  body: API.IntelligenceIngestParams,
  options?: { [key: string]: any },
) {
  return request<API.IntelligenceIngestResult>('/intelligence/ingest', {
    method: 'POST',
    data: body,
    ...(options || {}),
  });
}
