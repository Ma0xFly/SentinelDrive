declare namespace API {
  interface SourceAttribution {
    id: string | null;
    source_id: string | null;
    raw_intelligence_id: string | null;
    source_name: string;
    source_url: string;
    external_id: string | null;
    first_seen_at: string | null;
    last_seen_at: string | null;
  }

  interface Alert {
    id: string;
    title: string;
    threat_intelligence_id: string;
    triggering_rule: string;
    risk_level: RiskLevel;
    triggered_at: ISODateTime;
    status: AlertStatus;
    notes: string | null;
    metadata: Record<string, any>;
    created_at: ISODateTime;
    updated_at: ISODateTime;
  }

  interface AlertIntelligenceSummary {
    id: string;
    title: string;
    summary: string | null;
    intelligence_type: IntelligenceType;
    cve_id: string | null;
    severity: Severity;
    affected_vendor: string | null;
    affected_product: string | null;
    vehicle_component: VehicleComponent | null;
    attack_surface: AttackSurface | null;
    risk_score: number | null;
    risk_level: RiskLevel;
    status: string;
    source_names: string[];
    source_urls: string[];
    first_seen_at: ISODateTime;
    last_seen_at: ISODateTime;
    sources: SourceAttribution[];
  }

  interface AlertDetail extends Alert {
    intelligence: AlertIntelligenceSummary | null;
  }

  interface AlertListParams {
    risk_level?: RiskLevel;
    status?: AlertStatus;
    triggering_rule?: string;
    intelligence_id?: string;
    sort?: 'recent' | 'risk_level';
    page?: number;
    limit?: number;
  }

  interface AlertStatusUpdateParams {
    status: AlertStatus;
    notes?: string | null;
  }

  interface AlertEvaluateParams {
    intelligence_id?: string | null;
    limit?: number;
  }

  interface AlertGenerationResult {
    created: number;
    alert_ids: string[];
  }
}
