import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import App from './App';
import Dashboard from './Dashboard';
import JobDetail from './JobDetail';
import { API } from './api';
import type { Job, Report } from './api';
import { job, report, status, TOKEN } from './test-data';

const json = (value: unknown, code = 200) => new Response(JSON.stringify(value), { status: code });
let rows: Job[];
let evidence: Report;
let environment = status;
let submit: ((init: RequestInit) => Promise<Response>) | null;
let calls: { url: string; init: RequestInit }[];

beforeEach(() => {
  rows = []; evidence = structuredClone(report); environment = status; submit = null; calls = [];
  vi.stubGlobal('fetch', vi.fn(async (input: string, init: RequestInit) => {
    calls.push({ url: input, init });
    const url = new URL(input);
    if (url.pathname === '/api/status') return json(environment);
    if (url.pathname === '/api/jobs' && init.method === 'POST') {
      if (submit) return submit(init);
      rows = [structuredClone(job)]; return json(rows[0], 202);
    }
    if (url.pathname.endsWith('/cancel')) {
      rows = [{ ...rows[0], state: 'cancelled', cancellation_requested: true, version: 2 }];
      return json({ job: rows[0], execution_stop_confirmed: false, message: 'Cancellation recorded.' });
    }
    if (url.pathname === '/api/jobs') return json({ items: rows, next_cursor: null });
    if (url.pathname.endsWith('/report')) return json(evidence);
    if (url.pathname.endsWith('/events')) return json({ items: [], next_cursor: null });
    return json(rows[0]);
  }));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function connect() {
  render(<App />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Connect' })).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Operator token'), { target: { value: TOKEN } });
  fireEvent.click(screen.getByRole('button', { name: 'Connect' }));
  await screen.findByRole('button', { name: 'Create repair job' });
}

test('shows approved repository and offline worker status and keeps auth in memory', async () => {
  const local = vi.spyOn(Storage.prototype, 'setItem');
  await connect();
  expect(screen.getByText('Offline / simulated')).toBeInTheDocument();
  expect(screen.getByText('Available')).toBeInTheDocument();
  expect(screen.queryByDisplayValue(TOKEN)).not.toBeInTheDocument();
  expect(local).not.toHaveBeenCalled();
  const protectedCall = calls.find(value => value.url.includes('/api/jobs'))!;
  expect((protectedCall.init.headers as Record<string, string>).Authorization).toBe('Bearer ' + TOKEN);
  expect(protectedCall.init.credentials).toBe('omit');
  expect(calls.every(value => !value.url.includes(TOKEN))).toBe(true);
});

test('reports unavailable API honestly', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('private raw failure')));
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent('API unavailable');
  expect(screen.getByRole('button', { name: 'Connect' })).toBeDisabled();
  expect(screen.queryByText('private raw failure')).not.toBeInTheDocument();
});

test('rejected auth returns a safe error without exposing raw server messages', async () => {
  const original = globalThis.fetch;
  vi.stubGlobal('fetch', vi.fn((url: string, init: RequestInit) => url.includes('/api/jobs')
    ? Promise.resolve(json({ error: { code: 'unauthorized', message: 'secret=' + TOKEN } }, 401))
    : original(url, init)));
  render(<App />);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Connect' })).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Operator token'), { target: { value: TOKEN } });
  fireEvent.click(screen.getByRole('button', { name: 'Connect' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Operator token was rejected');
  expect(screen.queryByRole('button', { name: 'Create repair job' })).not.toBeInTheDocument();
  expect(screen.queryByText('secret=' + TOKEN)).not.toBeInTheDocument();
});

test('double submission clicks create only one request and keep a stable payload/key', async () => {
  let release!: (value: Response) => void;
  submit = () => new Promise(resolve => { release = resolve; });
  await connect();
  const button = screen.getByRole('button', { name: 'Create repair job' });
  fireEvent.click(button); fireEvent.click(button);
  const submissions = calls.filter(value => value.init.method === 'POST');
  expect(submissions).toHaveLength(1);
  expect(JSON.parse(submissions[0].init.body as string)).toEqual({ repository: 'demo-repository', ref: 'main' });
  expect((submissions[0].init.headers as Record<string, string>)['Idempotency-Key']).toMatch(/^[a-f0-9-]{36}$/);
  rows = [job];
  await act(async () => release(json(job, 202)));
  expect(await screen.findByRole('button', { name: 'Job accepted' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Start another job' })).toBeEnabled();
});

test('uncertain acceptance retries the same key and cannot change its payload', async () => {
  let tries = 0;
  submit = async () => { if (++tries === 1) throw new Error('connection lost'); rows = [job]; return json(job, 202); };
  await connect();
  fireEvent.click(screen.getByRole('button', { name: 'Create repair job' }));
  const retry = await screen.findByRole('button', { name: 'Retry same submission' });
  await waitFor(() => expect(retry).toBeEnabled());
  expect(screen.getByLabelText('Approved Git ref')).toBeDisabled();
  fireEvent.click(retry);
  await screen.findByRole('button', { name: 'Job accepted' });
  const posted = calls.filter(value => value.init.method === 'POST');
  expect(posted).toHaveLength(2);
  expect(posted[0].init.body).toBe(posted[1].init.body);
  expect(posted[0].init.headers).toEqual(posted[1].init.headers);
});

test('worker unavailable still permits durable queuing and explains the blocker', async () => {
  environment = { ...status, worker_available: false };
  await connect();
  expect(screen.getByRole('button', { name: 'Create repair job' })).toBeEnabled();
  expect(screen.getByText(/Submissions are saved/)).toBeInTheDocument();
});

test('cancellation is durable without claiming the executor has stopped', async () => {
  rows = [job];
  await connect();
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel job' }));
  expect(await screen.findByText(/Execution stop has not been confirmed/)).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Cancel job' })).not.toBeInTheDocument());
  expect(calls.filter(value => value.url.endsWith('/cancel'))).toHaveLength(1);
});

test('bounded polling stops at terminal state and leaves no background requests', async () => {
  vi.useFakeTimers(); rows = [job];
  render(<Dashboard api={new API()} token={TOKEN} initial={{ items: rows, next_cursor: null }} status={status}
    updateStatus={vi.fn()} disconnect={vi.fn()} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  const details = () => calls.filter(value => value.url.endsWith('/' + job.id)).length;
  expect(details()).toBe(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
  expect(details()).toBe(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(details()).toBe(3);
  rows = [{ ...job, state: 'no_reproducible_bug', version: 2 }];
  await act(async () => { await vi.advanceTimersByTimeAsync(4000); });
  expect(screen.getByText(/does not establish that the repository is bug-free/)).toBeInTheDocument();
  const stopped = calls.length;
  await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
  expect(calls).toHaveLength(stopped);
});

test('page close and unmount abort requests and cancel polling timers', async () => {
  vi.useFakeTimers(); rows = [job];
  const mounted = render(<Dashboard api={new API()} token={TOKEN} initial={{ items: rows, next_cursor: null }} status={status}
    updateStatus={vi.fn()} disconnect={vi.fn()} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  fireEvent(window, new Event('pagehide'));
  const count = calls.length;
  await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
  expect(calls).toHaveLength(count);
  mounted.unmount();
  expect(vi.getTimerCount()).toBe(0);
});

test('finished selected jobs stop polling even while another recent job stays active', async () => {
  vi.useFakeTimers();
  rows = [{ ...job, state: 'no_reproducible_bug' }, { ...job, id: 'c'.repeat(32), state: 'queued' }];
  render(<Dashboard api={new API()} token={TOKEN} initial={{ items: rows, next_cursor: null }} status={status}
    updateStatus={vi.fn()} disconnect={vi.fn()} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  const details = () => calls.filter(value => value.url.endsWith('/' + job.id)).length;
  expect(details()).toBe(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(7000); });
  expect(details()).toBe(1);
  expect(calls.filter(value => value.url.includes('limit=10')).length).toBeGreaterThan(1);
});

test('failed verification and paused retries show stored reasons', () => {
  render(<JobDetail job={{ ...job, state: 'failed', failure_reason: 'verification' }}
    report={{ ...report, paused: true, reason: 'verification_blocked', verifications: [{ round: 1,
      status: 'failed', reason: 'tests_failed', image_id: 'sha256:' + 'c'.repeat(64), patch_digest: 'd'.repeat(64),
      evidence_available: true, checks: [{ name: 'suite', exit_code: 1, passed: 1, failed: 1, command: ['python', '-m', 'pytest'] }] }] }}
    events={[]} moreEvents={false} busy="" refresh={vi.fn()} cancel={vi.fn()} />);
  expect(screen.getByText(/proposal did not pass verification/)).toBeInTheDocument();
  expect(screen.getByText(/Processing paused/)).toBeInTheDocument();
  expect(screen.getByRole('table')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Cancel job' })).not.toBeInTheDocument();
});

test('simulated draft is explicit and untrusted repository text is never interpreted as HTML', () => {
  const malicious = '<img src=x onerror=alert(1)> @everyone';
  render(<JobDetail job={{ ...job, state: 'draft_pr_created' }} report={{ ...report,
    detection: { ...report.detection, verdict: 'reproduced', node_id: malicious, traceback: malicious, expected: '[10, 20]', actual: '[10]' },
    publication: { simulated: true, confirmed: true, draft: true, branch: 'webguard/jobs/a',
      commit_sha: 'b'.repeat(40), pr_number: 1, live_url: 'https://github.com/owner/repo/pull/1', reason: null } }}
    events={[]} moreEvents={false} busy="" refresh={vi.fn()} cancel={vi.fn()} />);
  expect(screen.getByText('SIMULATED OFFLINE DRAFT')).toBeInTheDocument();
  expect(screen.getByText('[10, 20]')).toBeInTheDocument();
  expect(screen.getByText('[10]')).toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(document.querySelector('img')).toBeNull();
});

test('only an exact validated live PR URL becomes an accessible link', () => {
  const live = { ...report, publication: { simulated: false, confirmed: true, draft: true,
    branch: 'webguard/jobs/a', commit_sha: 'b'.repeat(40), pr_number: 4, live_url: 'https://github.com/owner/repo/pull/4', reason: null } };
  const props = { job: { ...job, repository: 'owner/repo', state: 'draft_pr_created' as const },
    report: live, events: [], moreEvents: false, busy: '', refresh: vi.fn(), cancel: vi.fn() };
  const mounted = render(<JobDetail {...props} />);
  expect(screen.getByRole('link', { name: /Open GitHub draft PR/ })).toHaveAttribute('href', live.publication.live_url);
  mounted.rerender(<JobDetail {...props} report={{ ...live, publication: { ...live.publication, live_url: 'javascript:alert(1)' } }} />);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

test('disconnect clears the authenticated workspace', async () => {
  await connect();
  fireEvent.click(screen.getByRole('button', { name: 'Disconnect' }));
  expect(screen.getByLabelText('Operator token')).toHaveValue('');
  expect(screen.queryByRole('button', { name: 'Create repair job' })).not.toBeInTheDocument();
});
