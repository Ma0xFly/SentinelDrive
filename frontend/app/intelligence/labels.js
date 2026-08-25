export const riskLevelOptions = [
  ["info", "信息"],
  ["low", "低"],
  ["medium", "中"],
  ["high", "高"],
  ["critical", "严重"]
];

export const vehicleComponentOptions = [
  ["app", "移动 App"],
  ["tbox", "T-Box"],
  ["ivi", "车机 IVI"],
  ["ota", "OTA"],
  ["v2x", "V2X"],
  ["charging", "充电"],
  ["cloud_api", "云端 API"],
  ["bluetooth", "蓝牙"],
  ["wifi", "Wi-Fi"],
  ["cellular", "蜂窝网络"],
  ["can", "CAN 总线"],
  ["usb", "USB"]
];

export const attackSurfaceOptions = vehicleComponentOptions;

export const intelligenceTypeOptions = [
  ["vulnerability", "漏洞"],
  ["exposure", "暴露面"],
  ["incident", "事件"],
  ["advisory", "公告"]
];

export const sortOptions = [
  ["recent", "最近更新"],
  ["first_seen", "首次发现"],
  ["risk_score", "风险分"],
  ["severity", "严重度"]
];

export const alertStatusOptions = [
  ["open", "未确认"],
  ["acknowledged", "已确认"],
  ["closed", "已关闭"]
];

export const intelligenceStatusOptions = [
  ["active", "有效"],
  ["under_review", "复核中"],
  ["resolved", "已解决"],
  ["dismissed", "已忽略"]
];

export const sourceStatusOptions = [
  ["enabled", "启用"],
  ["disabled", "停用"],
  ["error", "异常"]
];

export const sourceTypeOptions = [
  ["api", "API"],
  ["rss", "RSS"],
  ["html", "HTML"],
  ["pdf", "PDF"],
  ["manual", "手工"],
  ["vendor", "厂商"]
];

export const jobStatusOptions = [
  ["queued", "排队"],
  ["running", "运行中"],
  ["success", "成功"],
  ["failed", "失败"]
];

export const manualCategoryOptions = [
  ["vulnerability", "漏洞"],
  ["advisory", "公告"],
  ["incident", "事件"],
  ["exposure", "暴露面"],
  ["research_lead", "研究线索"]
];

export const exploitStatusOptions = [
  ["unknown", "未知"],
  ["none_known", "未发现利用"],
  ["proof_of_concept", "PoC"],
  ["exploited", "已利用"]
];

export const confidenceOptions = [
  ["low", "低"],
  ["medium", "中"],
  ["high", "高"]
];

export function labelFromOptions(options, value) {
  return options.find(([key]) => key === value)?.[1] || value || "-";
}

export function riskLabel(value) {
  return labelFromOptions(riskLevelOptions, value);
}

export function severityLabel(value) {
  return {
    unknown: "未知",
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重"
  }[value] || value || "-";
}

export const severityOptions = [
  ["unknown", "未知"],
  ["low", "低"],
  ["medium", "中"],
  ["high", "高"],
  ["critical", "严重"]
];

export function alertStatusLabel(value) {
  return labelFromOptions(alertStatusOptions, value);
}

export function intelligenceStatusLabel(value) {
  return labelFromOptions(intelligenceStatusOptions, value);
}

export function sourceStatusLabel(value) {
  return labelFromOptions(sourceStatusOptions, value);
}

export function sourceTypeLabel(value) {
  return labelFromOptions(sourceTypeOptions, value);
}

export function jobStatusLabel(value) {
  return labelFromOptions(jobStatusOptions, value);
}

export function manualCategoryLabel(value) {
  return labelFromOptions(manualCategoryOptions, value);
}

export function exploitStatusLabel(value) {
  return labelFromOptions(exploitStatusOptions, value);
}

export function confidenceLabel(value) {
  return labelFromOptions(confidenceOptions, value);
}

export function dateTimeLabel(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

export function numberLabel(value, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return `${value}${suffix}`;
}
