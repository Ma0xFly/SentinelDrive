import { request } from '@umijs/max';

/** 数据源状态列表 GET /sources */
export async function listSources(
  params?: API.SourceListParams,
  options?: { [key: string]: any },
) {
  return request<API.Page<API.Source>>('/sources', {
    method: 'GET',
    params,
    ...(options || {}),
  });
}

/** 采集任务日志 GET /sources/jobs */
export async function listJobLogs(
  params?: API.JobLogListParams,
  options?: { [key: string]: any },
) {
  return request<API.Page<API.JobLog>>('/sources/jobs', {
    method: 'GET',
    params,
    ...(options || {}),
  });
}

/** 管道运行状态 GET /sources/pipeline/status */
export async function getPipelineStatus(options?: {
  [key: string]: any;
}) {
  return request<API.PipelineStatus>('/sources/pipeline/status', {
    method: 'GET',
    ...(options || {}),
  });
}

/** 手动触发采集管道 POST /sources/pipeline/trigger */
export async function triggerPipeline(
  body?: API.PipelineTriggerParams,
  options?: { [key: string]: any },
) {
  return request<API.PipelineTriggerResult>('/sources/pipeline/trigger', {
    method: 'POST',
    data: body ?? {},
    ...(options || {}),
  });
}

/** 数据源详情 GET /sources/{source_id} */
export async function getSource(
  sourceId: string,
  options?: { [key: string]: any },
) {
  return request<API.Source>(`/sources/${sourceId}`, {
    method: 'GET',
    ...(options || {}),
  });
}

/** 更新数据源状态 PATCH /sources/{source_id}/status */
export async function updateSourceStatus(
  sourceId: string,
  body: API.SourceStatusUpdateParams,
  options?: { [key: string]: any },
) {
  return request<API.SourceStatus>(`/sources/${sourceId}/status`, {
    method: 'PATCH',
    data: body,
    ...(options || {}),
  });
}
