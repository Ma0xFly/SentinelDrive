from enum import Enum


class DatabaseEnum(str, Enum):
    pass


def enum_values(enum_type: type[DatabaseEnum]) -> list[str]:
    return [member.value for member in enum_type]


class AlertStatus(DatabaseEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CLOSED = "closed"


class AttackSurface(DatabaseEnum):
    APP = "app"
    TBOX = "tbox"
    IVI = "ivi"
    OTA = "ota"
    V2X = "v2x"
    CHARGING = "charging"
    CLOUD_API = "cloud_api"
    BLUETOOTH = "bluetooth"
    WIFI = "wifi"
    CELLULAR = "cellular"
    CAN = "can"
    USB = "usb"


class AuditAction(DatabaseEnum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    MANUAL_ENTRY = "manual_entry"
    STATUS_CHANGE = "status_change"
    USER_CHANGE = "user_change"
    ALERT_CLOSURE = "alert_closure"


class ConfidenceLevel(DatabaseEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExportFormat(DatabaseEnum):
    CSV = "csv"
    MARKDOWN = "markdown"
    PDF = "pdf"


class ExportStatus(DatabaseEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExploitStatus(DatabaseEnum):
    UNKNOWN = "unknown"
    NONE_KNOWN = "none_known"
    PROOF_OF_CONCEPT = "proof_of_concept"
    EXPLOITED = "exploited"


class IntelligenceType(DatabaseEnum):
    VULNERABILITY = "vulnerability"
    EXPOSURE = "exposure"
    INCIDENT = "incident"
    ADVISORY = "advisory"


class JobStatus(DatabaseEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ProcessingStatus(DatabaseEnum):
    PENDING = "pending"
    COLLECTED = "collected"
    PROCESSING = "processing"
    NORMALIZED = "normalized"
    FAILED = "failed"
    SKIPPED = "skipped"


class RiskLevel(DatabaseEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(DatabaseEnum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SourceStatus(DatabaseEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class SourceType(DatabaseEnum):
    API = "api"
    RSS = "rss"
    HTML = "html"
    PDF = "pdf"
    MANUAL = "manual"
    VENDOR = "vendor"


class VehicleComponent(DatabaseEnum):
    APP = "app"
    TBOX = "tbox"
    IVI = "ivi"
    OTA = "ota"
    V2X = "v2x"
    CHARGING = "charging"
    CLOUD_API = "cloud_api"
    BLUETOOTH = "bluetooth"
    WIFI = "wifi"
    CELLULAR = "cellular"
    CAN = "can"
    USB = "usb"
