declare namespace API {
  interface IntelligenceBase {
    id: string;
    title: string;
    summary: string | null;
    intelligence_type: IntelligenceType;
    source_names: string[];
    source_urls: string[];
    canonical_source_url: string | null;
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
    first_seen_at: ISODateTime;
    last_seen_at: ISODateTime;
    created_at: ISODateTime;
    updated_at: ISODateTime;
    metadata: Record<string, any>;
    score_metadata: Record<string, any>;
    score_explanation: string | null;
    sources: SourceAttribution[];
    related_alert_count: number;
  }

  type IntelligenceListItem = IntelligenceBase;

  interface RelatedAlert {
    id: string;
    title: string;
    risk_level: RiskLevel;
    status: AlertStatus;
    triggered_at: ISODateTime;
  }

  interface IntelligenceDetail extends IntelligenceBase {
    raw_intelligence_id: string | null;
    external_ids: Record<string, any>;
    dedup_key: string;
    normalized_text_hash: string | null;
    related_alerts: RelatedAlert[];
  }

  interface IntelligenceListParams {
    q?: string;
    cve?: string;
    vendor?: string;
    product?: string;
    vehicle_component?: VehicleComponent;
    attack_surface?: AttackSurface;
    risk_level?: RiskLevel;
    intelligence_type?: IntelligenceType;
    tag?: string;
    source?: string;
    status?: string;
    sort?: 'recent' | 'first_seen' | 'risk_score' | 'severity';
    page?: number;
    limit?: number;
  }

  interface IntelligenceIngestParams {
    source_name: string;
    source_url: string;
    platform?: string | null;
    title: string;
    summary: string;
    description?: string | null;
    external_id?: string | null;
    cve_id?: string | null;
    cnvd_id?: string | null;
    vendor_advisory_id?: string | null;
    affected_vendor?: string | null;
    affected_products?: string[];
    components?: string[];
    attack_surfaces?: string[];
    severity?: Severity;
    external_score?: number | null;
    published_at?: string | null;
    collected_at?: string | null;
    dedup_key?: string | null;
    content_hash?: string | null;
    raw_payload?: Record<string, any> | null;
    tags?: string[];
  }

  interface IntelligenceIngestResult {
    id: string;
    raw_intelligence_id: string | null;
    status: string;
    duplicate: boolean;
    dedup_key: string;
    title: string;
    cve_id: string | null;
    source_name: string;
    source_url: string;
    message: string;
  }
}
