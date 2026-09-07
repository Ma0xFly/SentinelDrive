declare namespace API {
  interface StatsTotals {
    total_intelligence: number;
    new_last_24_hours: number;
    new_last_7_days: number;
  }

  interface StatsTrendPoint {
    date: string;
    count: number;
  }

  interface StatsAlerts {
    total: number;
    by_status: Record<string, number>;
    trend: StatsTrendPoint[];
  }

  interface StatsSourceTop {
    id: string;
    name: string;
    intelligence_count: number;
  }

  interface StatsSources {
    enabled: number;
    top: StatsSourceTop[];
  }

  interface StatsOverview {
    totals: StatsTotals;
    by_intelligence_type: Record<string, number>;
    by_severity: Record<string, number>;
    by_risk_level: Record<string, number>;
    by_processing_status: Record<string, number>;
    trend: StatsTrendPoint[];
    alerts: StatsAlerts;
    sources: StatsSources;
  }
}
