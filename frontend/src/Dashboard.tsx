import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { API, APIError, terminal } from './api';
import type { Event, Job, JobPage, Report, Status } from './api';
import { date, errorMessage, label } from './format';
import JobDetail from './JobDetail';

export default function Dashboard({ api, token, initial, status, updateStatus, disconnect }: {
  api: API; token: string; initial: JobPage; status: Status | null;
  updateStatus: (value: Status) => void; disconnect: (message?: string) => void;
}) {
  const [jobs, setJobs] = useState(initial.items);
  const jobsRef = useRef(initial.items);
  const [cursor, setCursor] = useState(initial.next_cursor);
  const expanded = useRef(false);
  const [selected, setSelected] = useState<string | null>(initial.items[0]?.id || null);
  const [report, setReport] = useState<Report | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const eventCursor = useRef(0);
  const [moreEvents, setMoreEvents] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState('');
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [ref, setRef] = useState('main');
  const [submission, setSubmission] = useState<{ key: string; payload: { repository: string; ref: string }; accepted: boolean } | null>(null);
  const mutating = useRef(false);
  const action = useRef<AbortController | null>(null);
  const [polling, setPolling] = useState(false);
  const job = jobs.find(value => value.id === selected) || null;
  const callbacks = useRef({ updateStatus, disconnect });
  callbacks.current = { updateStatus, disconnect };
  function merge(values: Job[]) {
    const combined = new Map(jobsRef.current.map(value => [value.id, value]));
    for (const value of values) if (!combined.has(value.id) || combined.get(value.id)!.version <= value.version) combined.set(value.id, value);
    const next = [...combined.values()].sort((a, b) => b.created_at - a.created_at || b.id.localeCompare(a.id)).slice(0, 50);
    jobsRef.current = next; setJobs(next);
  }
  function failure(reason: unknown) {
    if (reason instanceof APIError && reason.status === 401) callbacks.current.disconnect(reason.message);
    else setError(errorMessage(reason));
  }
  useEffect(() => { eventCursor.current = 0; setEvents([]); setMoreEvents(false); setReport(null); }, [selected]);
  useEffect(() => {
    let closed = false, attempt = 0, selectedFinished = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    const close = () => { closed = true; controller.abort(); clearTimeout(timer); };
    window.addEventListener('pagehide', close);
    async function tick() {
      setLoading(true);
      try {
        const [environment, page] = await Promise.all([api.status(controller.signal), api.jobs(token, controller.signal)]);
        if (closed) return;
        callbacks.current.updateStatus(environment); merge(page.items);
        if (!expanded.current) setCursor(page.next_cursor);
        if (selected && !selectedFinished) {
          const [current, firstEvidence] = await Promise.all([api.job(selected, token, controller.signal), api.report(selected, token, controller.signal)]);
          const evidence = terminal(current.state) && firstEvidence.version < current.version
            ? await api.report(selected, token, controller.signal) : firstEvidence;
          if (closed) return;
          merge([current]); setReport(previous => previous && previous.version > evidence.version ? previous : evidence);
          for (let index = 0; index < 2; index++) {
            const history = await api.events(selected, token, controller.signal, eventCursor.current);
            if (closed) return;
            if (history.items.length) {
              eventCursor.current = history.items.at(-1)!.sequence;
              setEvents(previous => [...new Map([...previous, ...history.items].map(value => [value.sequence, value])).values()].slice(-200));
            }
            setMoreEvents(history.next_cursor !== null);
            if (history.next_cursor === null) break;
          }
          selectedFinished = terminal(current.state);
        }
        setError('');
      } catch (reason) { if (!closed) failure(reason); }
      finally {
        if (!closed) {
          setLoading(false);
          const active = jobsRef.current.some(value => !terminal(value.state));
          setPolling(active);
          if (active) timer = setTimeout(tick, Math.min(1000 * 2 ** attempt++, 10000));
        }
      }
    }
    tick();
    return () => { close(); window.removeEventListener('pagehide', close); };
  }, [api, token, selected, refresh]);
  useEffect(() => {
    const close = () => action.current?.abort();
    window.addEventListener('pagehide', close);
    return () => { close(); window.removeEventListener('pagehide', close); };
  }, []);

  async function mutate(kind: string, operation: (signal: AbortSignal) => Promise<void>) {
    if (mutating.current) return;
    mutating.current = true; setBusy(kind); setError('');
    const controller = new AbortController(); action.current = controller;
    try { await operation(controller.signal); }
    catch (reason) { if (!controller.signal.aborted) failure(reason); }
    finally { mutating.current = false; if (!controller.signal.aborted) setBusy(''); }
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (submission?.accepted || !status?.approved_repository || mutating.current) return;
    const intent = submission || { key: crypto.randomUUID(), payload: { repository: status.approved_repository, ref }, accepted: false };
    setSubmission(intent);
    void mutate('submit', async signal => {
      const accepted = await api.create(token, signal, intent.payload, intent.key);
      if (signal.aborted) return;
      merge([accepted]); setSelected(accepted.id); setSubmission({ ...intent, accepted: true });
      setNotice('Job accepted durably. The worker will process it independently.'); setRefresh(value => value + 1);
    });
  }
  return <>
    <div className="toolbar"><p>Operator connected <span className="muted">· token kept in memory</span></p>
      <div className="actions"><button disabled={!!busy} onClick={() => setRefresh(value => value + 1)}>Refresh</button>
        <button onClick={() => disconnect()}>Disconnect</button></div></div>
    {!status?.worker_available && <p className="warning" role="status">Worker unavailable. Submissions are saved, but cannot process until a worker starts.</p>}
    {status?.mode === 'live_configured' && <p className="warning">Live providers are configured. External calls/publication may occur under server flags.
      Gemini: {status.live_gemini_configured ? 'live configured' : 'offline fake'}; GitHub: {status.live_github_configured ? 'live configured' : 'simulated'}.</p>}
    <section className="card submit" aria-labelledby="submit-title"><div><p className="overline">NEW REPAIR JOB</p><h2 id="submit-title">Run an evidence-led repair</h2>
      <p>Only <strong>{status?.approved_repository}</strong> is accepted. Test execution runs in Docker.</p></div>
      <form onSubmit={submit} aria-busy={busy === 'submit'}><label htmlFor="target-ref">Approved Git ref</label>
        <input id="target-ref" value={ref} onChange={event => setRef(event.target.value)} required maxLength={200}
          disabled={!!submission || !!busy} pattern="[A-Za-z0-9][A-Za-z0-9_.\/\-]*" />
        <button className="primary" disabled={!!busy || !status?.job_api_enabled || !!submission?.accepted}>
          {busy === 'submit' ? 'Submitting…' : submission?.accepted ? 'Job accepted' : submission ? 'Retry same submission' : 'Create repair job'}</button>
        {submission && <p className="small">Submission key: <code>{submission.key}</code><br />
          {submission.accepted ? 'Recorded. Start another only for a new logical job.' : 'Keep this key. Retry reuses the payload and key; reloading clears this in-memory request.'}</p>}
        {submission?.accepted && <button type="button" onClick={() => { setSubmission(null); setNotice(''); }}>Start another job</button>}
      </form></section>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p role="status" className="notice">{notice}</p>}
    <div className="workspace-grid">
      <section className="card jobs" aria-labelledby="jobs-title"><div className="section-title"><h2 id="jobs-title">Recent jobs</h2><span>{jobs.length} loaded</span></div>
        {loading && !jobs.length ? <p role="status">Loading jobs…</p> : !jobs.length ? <p>No jobs yet. Create the first approved repair job.</p> :
          <ul className="job-list">{jobs.map(value => <li key={value.id}><button className={value.id === selected ? 'selected job-button' : 'job-button'}
            aria-pressed={value.id === selected} onClick={() => setSelected(value.id)} aria-label={`Open job ${value.id}`}>
            <span className={'badge state-' + value.state}>{label(value.state)}</span><code>{value.id.slice(0, 12)}</code>
            <small>{value.ref} · {date(value.created_at)}</small></button></li>)}</ul>}
        {cursor && jobs.length < 50 && <button disabled={!!busy} onClick={() => void mutate('list', async signal => {
          const page = await api.jobs(token, signal, cursor); if (!signal.aborted) { expanded.current = true; merge(page.items); setCursor(page.next_cursor); }
        })}>Load older jobs</button>}
        <p className="small">{polling ? 'Active jobs refresh with backoff, up to 10 seconds.' : 'Automatic polling stopped. Refresh to check for new jobs.'}</p>
      </section>
      <JobDetail job={job} report={report} events={events} moreEvents={moreEvents} busy={busy}
        refresh={() => setRefresh(value => value + 1)} cancel={() => job && void mutate('cancel', async signal => {
          const value = await api.cancel(job.id, token, signal); if (signal.aborted) return;
          merge([value.job]); setNotice('Cancellation recorded. Execution stop has not been confirmed; an accepted draft may remain.'); setRefresh(value => value + 1);
        })} />
    </div>
  </>;
}
