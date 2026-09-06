declare namespace API {
  interface ManualEntry {
    id: string;
    raw_intelligence_id: string | null;
    category: ManualEntryCategory;
    intelligence_type: IntelligenceType;
    title: string;
    summary: string | null;
    source_name: string;
    source_url: string;
    cve_id: string | null;
    cwe_id: string | null;
    cvss_score: number | null;
    cvss_vector: string | null;
    severity: Severity;
    affected_vendor: string | null;
    affected_product: string | null;
    affected_version: string | null;
    vehicle_component: VehicleComponent | null;
    attack_surface: AttackSurface | null;
    exploit_status: ExploitStatus;
    confidence: ConfidenceLevel;
    risk_score: number | null;
    risk_level: RiskLevel;
    status: string;
    tags: string[];
    dedup_key: string;
    first_seen_at: ISODateTime;
    last_seen_at: ISODateTime;
    created_at: ISODateTime;
    updated_at: ISODateTime;
  }

  interface ManualEntryCreateParams {
    category: ManualEntryCategory;
    title: string;
    summary: string;
    source_name?: string | null;
    source_url?: string | null;
    cve_id?: string | null;
    cwe_id?: string | null;
    cvss_score?: number | null;
    cvss_vector?: string | null;
    severity?: Severity;
    affected_vendor?: string | null;
    affected_product?: string | null;
    affected_version?: string | null;
    vehicle_component?: VehicleComponent | null;
    attack_surface?: AttackSurface | null;
    exploit_status?: ExploitStatus;
    confidence?: ConfidenceLevel;
    risk_score?: number | null;
    risk_level?: RiskLevel;
    tags?: string[];
    status?: ManualEntryStatus | null;
  }

  type ManualEntryUpdateParams = Partial<ManualEntryCreateParams>;
}
