import { afterEach, expect, test, vi } from 'vitest';
import { API, APIError, livePRLink } from './api';
import { job, report, TOKEN } from './test-data';

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

test.each(['https://remote.example', 'http://127.0.0.1:8000?token=private', 'http://user:secret@localhost:8000',
  'http://localhost:8000/path', 'http://localhost:9000', 'file:///tmp/api'])('rejects unsafe API base %s', value => {
  expect(() => new API(value)).toThrow(APIError);
});

test('rejects malformed API responses', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: job.id, state: 'fake_success' }))));
  await expect(new API().job(job.id, TOKEN, new AbortController().signal)).rejects.toThrow('API response could not be used');
});

test('network timeout aborts the request without exposing the token', async () => {
  vi.useFakeTimers();
  let signal: AbortSignal;
  vi.stubGlobal('fetch', vi.fn((_url, init) => new Promise((_, reject) => {
    signal = init.signal;
    signal.addEventListener('abort', () => reject(new Error('private ' + TOKEN)));
  })));
  const waiting = new API().job(job.id, TOKEN, new AbortController().signal).catch(error => error);
  await vi.advanceTimersByTimeAsync(10001);
  const error = await waiting;
  expect(signal!.aborted).toBe(true);
  expect(error.message).toContain('timed out');
  expect(error.message).not.toContain(TOKEN);
});

test.each(['https://github.com/owner/repo/pull/3?token=private', 'https://github.com.evil/owner/repo/pull/3',
  'https://user:pass@github.com/owner/repo/pull/3', 'https://github.com/other/repo/pull/3'])('does not link unsafe PR %s', value => {
  expect(livePRLink({ ...report, publication: { simulated: false, confirmed: true, draft: true, branch: 'branch',
    commit_sha: 'b'.repeat(40), pr_number: 3, live_url: value, reason: null } }, 'owner/repo')).toBeNull();
});
