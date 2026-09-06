declare namespace API {
  interface SyncState {
    id: string;
    status: JobStatus;
    cursor: string | null;
    last_run_at: string | null;
    next_run_at: string | null;
    consecutive_failures: number;
    metadata: Record<string, any>;
    created_at: ISODateTime;
    updated_at: ISODateTime;
  }

  interface SourceJobSummary {
    total: number;
    success: number;
    failed: number;
    skipped: number;
    retried: number;
    items_seen: number;
    items_created: number;
    items_updated: number;
    latest_job_id: string | null;
    latest_job_status: JobStatus | null;
    latest_run_status: string | null;
    latest_started_at: string | null;
    latest_finished_at: string | null;
    latest_attempts: number | null;
    latest_retried: boolean;
    latest_skipped: boolean;
    latest_metadata: Record<string, any>;
  }

  interface Source {
    id: string;
    name: string;
    source_type: SourceType;
    status: SourceStatus;
    enabled: boolean;
    base_url: string | null;
    config: Record<string, any>;
    last_success_at: string | null;
    last_error_at: string | null;
    last_error_message: string | null;
    failure_count: number;
    sync_state: SyncState | null;
    recent_jobs: SourceJobSummary;
    created_at: ISODateTime;
    updated_at: ISODateTime;
  }

  interface SourceListParams {
    status?: SourceStatus;
    source_type?: SourceType;
    q?: string;
    sort?: 'name' | 'recent' | 'failures';
    page?: number;
    limit?: number;
  }

  interface JobLog {
    id: string;
    job_name: string;
    source_id: string | null;
    source_name: string | null;
    source_type: SourceType | null;
    status: JobStatus;
    run_status: string | null;
    started_at: string | null;
    finished_at: string | null;
    items_seen: number;
    items_created: number;
    items_updated: number;
    error_message: string | null;
    attempts: number | null;
    retried: boolean;
    skipped: boolean;
    metadata: Record<string, any>;
    created_at: ISODateTime;
    updated_at: ISODateTime;
  }

  interface JobLogListParams {
    source_id?: string;
    status?: JobStatus;
    job_name?: string;
    run_status?: string;
    retried?: boolean;
    skipped?: boolean;
    sort?: 'recent' | 'started';
    page?: number;
    limit?: number;
  }

  interface PipelineJob {
    id: string;
    job_name: string;
    source_id: string | null;
    source_name: string | null;
    source_type: SourceType | null;
    status: JobStatus;
    run_status: string | null;
    celery_task_id: string | null;
    celery_status: string | null;
    started_at: string | null;
    finished_at: string | null;
    items_seen: number;
    items_created: number;
    items_updated: number;
    error_message: string | null;
    metadata: Record<string, any>;
    created_at: ISODateTime;
    updated_at: ISODateTime;
  }

  interface PipelineFailure {
    category: string;
    id: string;
    source_id: string | null;
    source_name: string | null;
    source_url: string | null;
    status: string;
    stage: string | null;
    error_message: string | null;
    occurred_at: string | null;
    metadata: Record<string, any>;
  }

  interface PipelineStatus {
    pending_raw_rows: number;
    failed_raw_rows: number;
    scoring_pending_intelligence_rows: number;
    open_alerts: number;
    latest_pipeline_job: PipelineJob | null;
    latest_source_job: PipelineJob | null;
    recent_failures: PipelineFailure[];
  }

  interface PipelineTriggerParams {
    normalization_limit?: number;
    scoring_limit?: number;
    alert_limit?: number;
  }

  interface PipelineTriggerResult {
    job_id: string;
    celery_task_id: string;
    task_name: string;
    status: string;
    message: string;
  }

  interface SourceStatusUpdateParams {
    status: SourceStatus;
    reason?: string | null;
  }
}
