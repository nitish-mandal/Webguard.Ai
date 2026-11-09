import type { Job, Report, Status } from './api';
export const TOKEN = 'local-ui-fixture-operator-' + 'x'.repeat(32);
export const job: Job = { id: 'a'.repeat(32), repository: 'demo-repository', ref: 'main', sha: 'b'.repeat(40),
  state: 'queued', created_at: 1000, updated_at: 1000, version: 1, failure_reason: null, cancellation_requested: false,
  repair_attempts: 0, publication_attempts: 0, execution_seconds: 0, model_calls: 0,
  limits: { repair_attempts: 3, publication_attempts: 3, execution_seconds: 120 } };
export const status: Status = { approved_repository: 'demo-repository', mode: 'offline', worker_available: true,
  database_ready: true, job_api_enabled: true, live_gemini_configured: false, live_github_configured: false };
export const report: Report = { version: 1, stage: 'source', paused: false, reason: null, next_run_at: null,
  cleanup_completed: false, detection: { verdict: null, evidence_available: false, node_id: null,
    expected: null, actual: null, message: null, traceback: null, observations: [] }, verifications: [], publication: null };
