import { request } from '@umijs/max';

/**
 * 导出文件下载统一返回 Blob 与文件名。
 * 响应为 text/csv、text/markdown 或 application/pdf，不经 JSON 错误处理。
 */
export interface ExportDownload {
  blob: Blob;
  filename: string;
}

function filenameFromDisposition(disposition: string | null): string | null {
  if (!disposition) {
    return null;
  }
  const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  return match?.[1] || null;
}

async function download(
  path: string,
  fallbackName: string,
  options?: { [key: string]: any },
): Promise<ExportDownload> {
  const response = await request<Response>(path, {
    method: 'GET',
    responseType: 'blob',
    getResponse: true,
    skipErrorHandler: true,
    ...(options || {}),
  });
  const res = (response as any).response ?? response;
  const blob =
    res instanceof Blob ? res : ((response as any).data as Blob);
  const disposition =
    (res as Response)?.headers?.get?.('content-disposition') ?? null;
  return {
    blob,
    filename: filenameFromDisposition(disposition) || fallbackName,
  };
}

/** 威胁情报 CSV 导出 GET /exports/intelligence.csv */
export async function exportIntelligenceCsv(options?: {
  [key: string]: any;
}) {
  return download('/exports/intelligence.csv', 'intelligence.csv', options);
}

/** 告警 CSV 导出 GET /exports/alerts.csv */
export async function exportAlertsCsv(options?: { [key: string]: any }) {
  return download('/exports/alerts.csv', 'alerts.csv', options);
}

/** 情报 Markdown 导出 GET /exports/intelligence/{intelligence_id}/markdown */
export async function exportIntelligenceMarkdown(
  intelligenceId: string,
  options?: { [key: string]: any },
) {
  return download(
    `/exports/intelligence/${intelligenceId}/markdown`,
    `intelligence-${intelligenceId}.md`,
    options,
  );
}

/** 汇总 PDF 导出 GET /exports/summary.pdf */
export async function exportSummaryPdf(options?: { [key: string]: any }) {
  return download('/exports/summary.pdf', 'sentineldrive-summary.pdf', options);
}
