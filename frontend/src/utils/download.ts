import type { ExportDownload } from '@/services/exports';

/**
 * 触发浏览器下载导出文件。
 */
export function saveDownload({ blob, filename }: ExportDownload): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
