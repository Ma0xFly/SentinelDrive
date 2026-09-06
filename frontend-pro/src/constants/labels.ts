/**
 * 业务枚举的中文标签与展示映射，语义与旧版前端保持一致。
 */

export type LabelOption = [value: string, label: string];

export const riskLevelOptions: LabelOption[] = [
  ['info', '信息'],
  ['low', '低'],
  ['medium', '中'],
  ['high', '高'],
  ['critical', '严重'],
];

export const severityOptions: LabelOption[] = [
  ['unknown', '未知'],
  ['low', '低'],
  ['medium', '中'],
  ['high', '高'],
  ['critical', '严重'],
];

export const vehicleComponentOptions: LabelOption[] = [
  ['app', '移动 App'],
  ['tbox', 'T-Box'],
  ['ivi', '车机 IVI'],
  ['ota', 'OTA'],
  ['v2x', 'V2X'],
  ['charging', '充电'],
  ['cloud_api', '云端 API'],
  ['bluetooth', '蓝牙'],
  ['wifi', 'Wi-Fi'],
  ['cellular', '蜂窝网络'],
  ['can', 'CAN 总线'],
  ['usb', 'USB'],
];

export const attackSurfaceOptions: LabelOption[] = vehicleComponentOptions;

export const intelligenceTypeOptions: LabelOption[] = [
  ['vulnerability', '漏洞'],
  ['exposure', '暴露面'],
  ['incident', '事件'],
  ['advisory', '公告'],
];

export const intelligenceSortOptions: LabelOption[] = [
  ['recent', '最近更新'],
  ['first_seen', '首次发现'],
  ['risk_score', '风险分'],
  ['severity', '严重度'],
];

export const alertStatusOptions: LabelOption[] = [
  ['open', '未确认'],
  ['acknowledged', '已确认'],
  ['closed', '已关闭'],
];

export const intelligenceStatusOptions: LabelOption[] = [
  ['active', '有效'],
  ['under_review', '复核中'],
  ['resolved', '已解决'],
  ['dismissed', '已忽略'],
];

export const sourceStatusOptions: LabelOption[] = [
  ['enabled', '启用'],
  ['disabled', '停用'],
  ['error', '异常'],
];

export const sourceTypeOptions: LabelOption[] = [
  ['api', 'API'],
  ['rss', 'RSS'],
  ['html', 'HTML'],
  ['pdf', 'PDF'],
  ['manual', '手工'],
  ['vendor', '厂商'],
];

export const jobStatusOptions: LabelOption[] = [
  ['queued', '排队'],
  ['running', '运行中'],
  ['success', '成功'],
  ['failed', '失败'],
];

export const manualCategoryOptions: LabelOption[] = [
  ['vulnerability', '漏洞'],
  ['advisory', '公告'],
  ['incident', '事件'],
  ['exposure', '暴露面'],
  ['research_lead', '研究线索'],
];

export const exploitStatusOptions: LabelOption[] = [
  ['unknown', '未知'],
  ['none_known', '未发现利用'],
  ['proof_of_concept', 'PoC'],
  ['exploited', '已利用'],
];

export const confidenceOptions: LabelOption[] = [
  ['low', '低'],
  ['medium', '中'],
  ['high', '高'],
];

/** 由选项数组构造 ProTable valueEnum */
export function optionsToValueEnum(
  options: LabelOption[],
): Record<string, { text: string }> {
  return Object.fromEntries(
    options.map(([value, label]) => [value, { text: label }]),
  );
}

export function labelFromOptions(
  options: LabelOption[],
  value?: string | null,
): string {
  if (!value) {
    return '-';
  }
  return options.find(([key]) => key === value)?.[1] || value;
}

/** 状态与风险等级的徽章色调，保持视觉克制 */
export const riskLevelColor: Record<string, string> = {
  info: 'default',
  low: 'blue',
  medium: 'orange',
  high: 'volcano',
  critical: 'red',
};

export const severityColor: Record<string, string> = riskLevelColor;

export const alertStatusColor: Record<string, string> = {
  open: 'orange',
  acknowledged: 'blue',
  closed: 'default',
};

export const sourceStatusColor: Record<string, string> = {
  enabled: 'success',
  disabled: 'default',
  error: 'error',
};

export const jobStatusColor: Record<string, string> = {
  queued: 'default',
  running: 'processing',
  success: 'success',
  failed: 'error',
};

/** 本地化时间显示（后端返回 ISO 8601） */
export function dateTimeLabel(value?: string | null): string {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}
