import { request } from '@umijs/max';

/** 存活探针 GET /health */
export async function health(options?: { [key: string]: any }) {
  return request<{ status: string }>('/health', {
    method: 'GET',
    ...(options || {}),
  });
}

/** 就绪探针（含依赖检查） GET /ready */
export async function readiness(options?: { [key: string]: any }) {
  return request<{
    status: 'ready' | 'degraded';
    dependencies: Record<string, { status: string; detail: string }>;
  }>('/ready', {
    method: 'GET',
    ...(options || {}),
  });
}
