export const states = ['queued', 'baselining', 'reproduced', 'repairing', 'verifying', 'verified',
  'publishing', 'draft_pr_created', 'no_reproducible_bug', 'failed', 'cancelled'] as const;
export type State = typeof states[number];
export const terminal = (state: State) => ['draft_pr_created', 'no_reproducible_bug', 'failed', 'cancelled'].includes(state);
export interface Status { approved_repository: string | null; mode: 'offline' | 'live_configured';
  worker_available: boolean; database_ready: boolean; job_api_enabled: boolean;
  live_gemini_configured: boolean; live_github_configured: boolean }
export interface Job { id: string; repository: string; ref: string; sha: string | null; state: State;
  created_at: number; updated_at: number; version: number; failure_reason: string | null; cancellation_requested: boolean;
  repair_attempts: number; publication_attempts: number; execution_seconds: number; model_calls: number;
  limits: { repair_attempts: number; publication_attempts: number; execution_seconds: number } }
export interface JobPage { items: Job[]; next_cursor: string | null }
export interface Event { sequence: number; created_at: number; kind: string; data: Record<string, unknown> }
export interface EventPage { items: Event[]; next_cursor: number | null }
export interface Check { name: string; exit_code: number | null; passed: number; failed: number; command: string[] }
export interface Report { version: number; stage: string | null; paused: boolean; reason: string | null; next_run_at: number | null;
  cleanup_completed: boolean;
  detection: { verdict: string | null; evidence_available: boolean; node_id: string | null;
    expected: string | null; actual: string | null; message: string | null; traceback: string | null;
    observations: { exit_code: number | null; duration_seconds: number | null; image_id: string | null }[] };
  verifications: { round: number; status: string; reason: string | null; evidence_available: boolean;
    image_id: string; patch_digest: string; checks: Check[] }[];
  publication: { simulated: boolean; confirmed: boolean; draft: boolean; branch: string;
    commit_sha: string | null; pr_number: number | null; live_url: string | null; reason: string | null } | null }

export class APIError extends Error {
  constructor(public code: string, public status = 0) { super(messages[code] || 'The API response could not be used. Refresh to retry.'); }
}
const messages: Record<string, string> = {
  unauthorized: 'Operator token was rejected. Connect again with the local AUTH_TOKEN.',
  network: 'API unavailable or request timed out. Check the local API and retry.',
  auth_not_configured: 'Set the private server AUTH_TOKEN before connecting.',
  storage_unavailable: 'Job storage is unavailable. Check the API readiness and server setup.',
  invalid_input: 'The repository or ref was rejected. Check the approved repository and Git ref.',
  idempotency_conflict: 'This submission key belongs to different input. Review the existing job before starting another.',
  terminal_state_conflict: 'The job already finished. Refresh its recorded outcome.',
  unknown_job: 'This job is not in the current database. Refresh the jobs list.',
  invalid_api: 'The API URL must be http://127.0.0.1:8000 or http://localhost:8000.',
};
const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const string = (value: unknown) => typeof value === 'string' && value.length <= 4096;
const nullable = (value: unknown) => value === null || string(value);
const number = (value: unknown) => typeof value === 'number' && Number.isFinite(value);
const id = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{32}$/.test(value);
function validJob(value: unknown): value is Job {
  return object(value) && id(value.id) && string(value.repository) && string(value.ref) && nullable(value.sha)
    && states.includes(value.state as State) && number(value.created_at) && number(value.updated_at) && number(value.version)
    && nullable(value.failure_reason) && typeof value.cancellation_requested === 'boolean'
    && ['repair_attempts', 'publication_attempts', 'execution_seconds', 'model_calls'].every(key => number(value[key]))
    && object(value.limits) && ['repair_attempts', 'publication_attempts', 'execution_seconds'].every(key => number((value.limits as Record<string, unknown>)[key]));
}
function validStatus(value: unknown): value is Status {
  return object(value) && nullable(value.approved_repository) && ['offline', 'live_configured'].includes(value.mode as string)
    && ['worker_available', 'database_ready', 'job_api_enabled', 'live_gemini_configured', 'live_github_configured']
      .every(key => typeof value[key] === 'boolean');
}
function validReport(value: unknown): value is Report {
  if (!object(value) || !number(value.version) || !nullable(value.stage) || typeof value.paused !== 'boolean' || !nullable(value.reason)
      || !(value.next_run_at === null || number(value.next_run_at)) || typeof value.cleanup_completed !== 'boolean'
      || !object(value.detection) || !Array.isArray(value.verifications) || value.verifications.length > 10) return false;
  const detection = value.detection;
  if (!['verdict', 'node_id', 'expected', 'actual', 'message', 'traceback'].every(key => nullable(detection[key]))
      || typeof detection.evidence_available !== 'boolean' || !Array.isArray(detection.observations)
      || detection.observations.length > 2 || !detection.observations.every(run => object(run)
        && (run.exit_code === null || number(run.exit_code)) && (run.duration_seconds === null || number(run.duration_seconds))
        && nullable(run.image_id))) return false;
  for (const round of value.verifications) {
    if (!object(round) || !number(round.round) || !string(round.status) || !nullable(round.reason)
        || !string(round.image_id) || !string(round.patch_digest) || typeof round.evidence_available !== 'boolean'
        || !Array.isArray(round.checks) || round.checks.length > 4 || !round.checks.every(check => object(check)
          && string(check.name) && (check.exit_code === null || number(check.exit_code)) && number(check.passed)
          && number(check.failed) && Array.isArray(check.command) && check.command.length <= 32 && check.command.every(string))) return false;
  }
  const pr = value.publication;
  return pr === null || (object(pr) && ['simulated', 'confirmed', 'draft'].every(key => typeof pr[key] === 'boolean')
    && string(pr.branch) && nullable(pr.commit_sha) && nullable(pr.live_url) && nullable(pr.reason)
    && (pr.pr_number === null || (Number.isInteger(pr.pr_number) && Number(pr.pr_number) > 0)));
}

export function livePRLink(report: Report, repository: string): string | null {
  const pr = report.publication;
  if (!pr || pr.simulated || !pr.confirmed || !pr.draft || !pr.pr_number || !pr.live_url
      || !/^[a-z0-9][a-z0-9-]*\/[a-z0-9][a-z0-9_.-]*$/.test(repository)) return null;
  const expected = `https://github.com/${repository}/pull/${pr.pr_number}`;
  return pr.live_url === expected ? expected : null;
}

export class API {
  private base: string;
  constructor(base = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000') {
    let url: URL;
    try { url = new URL(base); } catch { throw new APIError('invalid_api'); }
    if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname) || url.port !== '8000'
        || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new APIError('invalid_api');
    this.base = url.origin;
  }
  private async request<T>(path: string, token: string | null, signal: AbortSignal, validate: (value: unknown) => value is T,
      method = 'GET', body?: object, key?: string): Promise<T> {
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) controller.abort();
    const timer = setTimeout(abort, 10000);
    try {
      const response = await fetch(this.base + path, { method, signal: controller.signal, redirect: 'error',
        credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer',
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(body ? { 'Content-Type': 'application/json' } : {}), ...(key ? { 'Idempotency-Key': key } : {}) },
        ...(body ? { body: JSON.stringify(body) } : {}) });
      const value: unknown = await response.json();
      if (!response.ok) throw new APIError(object(value) && object(value.error) && typeof value.error.code === 'string'
        ? value.error.code : 'invalid_response', response.status);
      if (!validate(value)) throw new APIError('invalid_response');
      return value;
    } catch (error) {
      if (signal.aborted) throw new DOMException('Request cancelled', 'AbortError');
      throw error instanceof APIError ? error : new APIError('network');
    } finally { clearTimeout(timer); signal.removeEventListener('abort', abort); }
  }
  status(signal: AbortSignal) { return this.request('/api/status', null, signal, validStatus); }
  jobs(token: string, signal: AbortSignal, cursor?: string) {
    return this.request('/api/jobs?limit=10&order=desc' + (cursor ? '&cursor=' + encodeURIComponent(cursor) : ''), token, signal,
      (v): v is JobPage => object(v) && Array.isArray(v.items) && v.items.length <= 10 && v.items.every(validJob) && nullable(v.next_cursor));
  }
  job(jobId: string, token: string, signal: AbortSignal) { return this.request('/api/jobs/' + jobId, token, signal, validJob); }
  report(jobId: string, token: string, signal: AbortSignal) { return this.request('/api/jobs/' + jobId + '/report', token, signal, validReport); }
  events(jobId: string, token: string, signal: AbortSignal, after = 0) {
    return this.request(`/api/jobs/${jobId}/events?limit=50&after=${after}`, token, signal,
      (v): v is EventPage => object(v) && Array.isArray(v.items) && v.items.length <= 50
        && v.items.every(e => object(e) && number(e.sequence) && number(e.created_at) && string(e.kind) && object(e.data))
        && (v.next_cursor === null || number(v.next_cursor)));
  }
  create(token: string, signal: AbortSignal, payload: { repository: string; ref: string }, key: string) {
    return this.request('/api/jobs', token, signal, validJob, 'POST', payload, key);
  }
  cancel(jobId: string, token: string, signal: AbortSignal) {
    return this.request('/api/jobs/' + jobId + '/cancel', token, signal,
      (v): v is { job: Job; execution_stop_confirmed: false; message: string } => object(v) && validJob(v.job)
        && v.execution_stop_confirmed === false && string(v.message), 'POST', {});
  }
}
