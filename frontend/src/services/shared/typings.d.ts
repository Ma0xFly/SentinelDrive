declare namespace API {
  /** 后端枚举值（与 backend/app/db/types.py 对齐） */
  type Severity = 'unknown' | 'low' | 'medium' | 'high' | 'critical';
  type RiskLevel = 'info' | 'low' | 'medium' | 'high' | 'critical';
  type IntelligenceType = 'vulnerability' | 'exposure' | 'incident' | 'advisory';
  type AlertStatus = 'open' | 'acknowledged' | 'closed';
  type ExploitStatus = 'unknown' | 'none_known' | 'proof_of_concept' | 'exploited';
  type ConfidenceLevel = 'low' | 'medium' | 'high';
  type AttackSurface =
    | 'app'
    | 'tbox'
    | 'ivi'
    | 'ota'
    | 'v2x'
    | 'charging'
    | 'cloud_api'
    | 'bluetooth'
    | 'wifi'
    | 'cellular'
    | 'can'
    | 'usb';
  type VehicleComponent =
    | 'app'
    | 'tbox'
    | 'ivi'
    | 'ota'
    | 'v2x'
    | 'charging'
    | 'cloud_api'
    | 'bluetooth'
    | 'wifi'
    | 'cellular'
    | 'can'
    | 'usb';
  type SourceStatus = 'enabled' | 'disabled' | 'error';
  type SourceType = 'api' | 'rss' | 'html' | 'pdf' | 'manual' | 'vendor';
  type JobStatus = 'queued' | 'running' | 'success' | 'failed';
  type ManualEntryCategory = 'vulnerability' | 'advisory' | 'incident' | 'exposure' | 'research_lead';
  type ManualEntryStatus = 'active' | 'under_review' | 'resolved' | 'dismissed';

  /** 分页列表通用结构 */
  interface Page<T> {
    items: T[];
    page: number;
    limit: number;
    total: number;
    has_next: boolean;
  }

  /** 时间字段统一为 ISO 8601 字符串 */
  type ISODateTime = string;
}
