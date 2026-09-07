import { request } from '@umijs/max';

/** 态势总览统计 GET /stats/overview */
export async function getStatsOverview(options?: { [key: string]: any }) {
  return request<API.StatsOverview>('/stats/overview', {
    method: 'GET',
    ...(options || {}),
  });
}
