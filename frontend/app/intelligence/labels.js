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
