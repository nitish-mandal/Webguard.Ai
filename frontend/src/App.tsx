import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { API, APIError } from './api';
import type { JobPage, Status } from './api';
import Dashboard from './Dashboard';
import { errorMessage } from './format';

export default function App() {
  const [api] = useState(() => { try { return new API(); } catch { return null; } });
  const [status, setStatus] = useState<Status | null>(null);
  const [session, setSession] = useState<{ token: string; jobs: JobPage } | null>(null);
  const [operator, setOperator] = useState('');
  const [error, setError] = useState(api ? '' : new APIError('invalid_api').message);
  const [connecting, setConnecting] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const request = useRef<AbortController | null>(null);
  const lock = useRef(false);
  useEffect(() => {
    if (!api) return;
    const controller = new AbortController();
    api.status(controller.signal).then(value => { setStatus(value); setError(''); }).catch(reason => {
      if (!controller.signal.aborted) setError(errorMessage(reason));
    });
    return () => controller.abort();
  }, [api, refresh]);
  useEffect(() => {
    const close = () => { request.current?.abort(); setSession(null); setOperator(''); };
    window.addEventListener('pagehide', close);
    return () => { window.removeEventListener('pagehide', close); request.current?.abort(); };
  }, []);
  async function connect(event: FormEvent) {
    event.preventDefault();
    if (!api || lock.current) return;
    lock.current = true; setConnecting(true); setError('');
    const controller = new AbortController(); request.current = controller;
    try {
      const jobs = await api.jobs(operator, controller.signal);
      if (!controller.signal.aborted) { setSession({ token: operator, jobs }); setOperator(''); }
    } catch (reason) { if (!controller.signal.aborted) setError(errorMessage(reason)); }
    finally { lock.current = false; setConnecting(false); }
  }
  function disconnect(message = '') { setSession(null); setOperator(''); setError(message); }
  return <main>
    <a className="skip" href="#workspace">Skip to workspace</a>
    <header className="masthead"><div><p className="overline">LOCAL REPAIR CONTROL</p><h1>WebGuard<span>AI</span></h1></div>
      <p>Reproduce. Verify. Review.<br /><span className="muted">One approved repository, evidence at every stage.</span></p></header>
    <div className="environment" aria-label="Server environment">
      <div><span className="overline">Approved repository</span><strong>{status?.approved_repository || 'Waiting for API'}</strong></div>
      <div><span className="overline">Provider mode</span><strong>{status ? status.mode === 'offline' ? 'Offline / simulated' : 'Live configured' : 'Unknown'}</strong></div>
      <div><span className="overline">Worker</span><strong className={status?.worker_available ? 'ready' : 'muted'}>
        {status ? status.worker_available ? 'Available' : 'Unavailable' : 'Checking'}</strong></div>
    </div>
    <div id="workspace" tabIndex={-1}>
      {session && api ? <Dashboard api={api} token={session.token} initial={session.jobs} status={status}
        updateStatus={setStatus} disconnect={disconnect} /> : <section className="connect card" aria-labelledby="connect-title">
        <div><p className="overline">OPERATOR ACCESS</p><h2 id="connect-title">Connect to your workspace</h2>
          <p id="auth-help">Enter the local server AUTH_TOKEN. It stays in memory until you disconnect or close this page.
            Never enter a Gemini or GitHub key here.</p>
          {!status?.worker_available && <p>Jobs can be saved while the worker is unavailable. Start the worker to process them.</p>}
          <p className="muted">Database: {status ? status.database_ready ? 'ready' : 'not ready' : 'checking'}.
            Worker availability is separate from Docker readiness.</p></div>
        <form onSubmit={connect} aria-busy={connecting}>
          <label htmlFor="operator-token">Operator token</label>
          <input id="operator-token" type="password" autoComplete="off" spellCheck={false} required minLength={32} maxLength={256}
            aria-describedby="auth-help" value={operator} onChange={event => setOperator(event.target.value)} />
          <div className="actions"><button className="primary" disabled={!api || !status?.job_api_enabled || connecting}>
            {connecting ? 'Connecting…' : 'Connect'}</button>
            <button type="button" disabled={!api || connecting} onClick={() => setRefresh(value => value + 1)}>Check API</button></div>
        </form>
      </section>}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
    <footer>Approved repositories only. Original tests stay intact. Drafts require operator review; merging is manual.</footer>
  </main>;
}
