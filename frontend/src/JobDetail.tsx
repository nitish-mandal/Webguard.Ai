import { livePRLink, terminal } from './api';
import type { Event, Job, Report, State } from './api';
import { date, label } from './format';

const messages: Record<State, string> = {
  queued: 'Queued. Waiting for an available worker.', baselining: 'Acquiring pinned source and checking the baseline in Docker.',
  reproduced: 'A matching assertion failure was reproduced twice.', repairing: 'Preparing a source patch for independent verification.',
  verifying: 'Checking the original test, existing suite and independent regressions in Docker.',
  verified: 'The exact patch is verified. Draft publication is still pending.', publishing: 'Reconciling the job branch and draft publication.',
  draft_pr_created: 'Draft publication recorded. Review the publication details below.',
  no_reproducible_bug: 'No reproducible bug in the configured suite. This does not establish that the repository is bug-free.',
  failed: 'Job failed. Review the failure reason and verification evidence.',
  cancelled: 'Cancellation recorded. This does not confirm execution has stopped or undo an accepted draft.',
};

export default function JobDetail({ job, report, events, moreEvents, busy, cancel, refresh }: {
  job: Job | null; report: Report | null; events: Event[]; moreEvents: boolean; busy: string;
  cancel: () => void; refresh: () => void;
}) {
  const prLink = report && job ? livePRLink(report, job.repository) : null;
  return <section className="card detail" aria-labelledby="detail-title"><h2 id="detail-title">{job ? 'Job evidence' : 'Select a job'}</h2>
    {!job ? <p>Your durable job history and evidence will appear here.</p> : <>
      <p className="job-id"><code>{job.id}</code></p>
      <p className="state-message" role="status" aria-live="polite" aria-atomic="true"><strong>{label(job.state)}.</strong> {messages[job.state]}</p>
      <dl className="facts"><div><dt>Current stage</dt><dd>{label(report?.stage || job.state)}</dd></div>
        <div><dt>Repair attempts</dt><dd>{job.repair_attempts} / {job.limits.repair_attempts}</dd></div>
        <div><dt>Publication attempts</dt><dd>{job.publication_attempts} / {job.limits.publication_attempts}</dd></div>
        <div><dt>Reserved execution</dt><dd>{job.execution_seconds} / {job.limits.execution_seconds} seconds</dd></div></dl>
      <p className="small">Repository: {job.repository} · ref: {job.ref}<br />Pinned commit: <code>{job.sha || 'Not pinned yet'}</code></p>
      {job.failure_reason && <p className="error">Failure reason: {label(job.failure_reason)}{job.failure_reason === 'verification' ? '. The proposal did not pass verification.' : ''}</p>}
      {report?.paused && <p className="warning">Processing paused: {label(report.reason || 'operator review required')}. Fix the blocker and resume using the local worker command.</p>}
      {report?.reason && !report.paused && <p className="warning">Worker retry: {label(report.reason)}{report.next_run_at ? `; next eligible at ${date(report.next_run_at)}` : ''}.</p>}
      {!terminal(job.state) && <button className="danger" disabled={!!busy} onClick={cancel}>{busy === 'cancel' ? 'Requesting cancellation…' : 'Cancel job'}</button>}
      {job.cancellation_requested && <p>Cancellation requested. Working copy cleanup: {report?.cleanup_completed ? 'recorded' : 'pending'}.
        Refresh evidence for later reconciliation; executor stop is not confirmed by this response.</p>}
      {!report && <p role="status">Loading evidence…</p>}
      {report && <>
        <section className="evidence-block" aria-labelledby="failure-title"><h3 id="failure-title">Failure evidence</h3>
          {report.detection.verdict ? <><p>Detection: <strong>{label(report.detection.verdict)}</strong></p>
            {report.detection.node_id && <p>Failing test: <code>{report.detection.node_id}</code></p>}
            {report.detection.expected !== null && <dl className="comparison"><div><dt>Expected</dt><dd><code>{report.detection.expected}</code></dd></div>
              <div><dt>Actual</dt><dd><code>{report.detection.actual}</code></dd></div></dl>}
            {report.detection.observations.map((run, index) => <p className="small" key={index}>Baseline {index + 1}: exit {run.exit_code ?? 'unavailable'}
              {run.duration_seconds !== null ? ` · ${run.duration_seconds.toFixed(2)} seconds` : ''}</p>)}
            {!report.detection.evidence_available && <p>Evidence excerpt unavailable. Stored classification is shown above.</p>}
            {report.detection.traceback && <details><summary>Read traceback excerpt (untrusted repository text)</summary><pre>{report.detection.traceback}</pre></details>}
          </> : <p>No baseline evidence recorded yet.</p>}</section>
        <section className="evidence-block" aria-labelledby="verification-title"><h3 id="verification-title">Verification</h3>
          {!report.verifications.length ? <p>No verification result recorded yet.</p> : report.verifications.map(round => <div key={round.round}>
            <p><strong>Round {round.round}: {label(round.status)}</strong>{round.reason ? ` · ${label(round.reason)}` : ''}</p>
            <p className="small">Patch: <code>{round.patch_digest}</code><br />Image: <code>{round.image_id}</code></p>
            <div className="table-wrap"><table><caption>Recorded checks for round {round.round}</caption><thead><tr><th scope="col">Check</th><th scope="col">Exit</th><th scope="col">Passed</th><th scope="col">Failed</th></tr></thead>
              <tbody>{round.checks.map(check => <tr key={check.name}><th scope="row">{label(check.name)}</th><td>{check.exit_code ?? '—'}</td><td>{check.passed}</td><td>{check.failed}</td></tr>)}</tbody></table></div>
            {!!round.checks.length && <p className="small">The unpatched baseline regression is a required failing control.</p>}
            {!!round.checks.length && <details><summary>Recorded check commands</summary>{round.checks.map(check =>
              <pre key={check.name}>{label(check.name)}: exit {check.exit_code ?? 'unavailable'}{'\n'}{check.command.join(' ')}</pre>)}</details>}
          </div>)}</section>
        <section className="evidence-block" aria-labelledby="publication-title"><h3 id="publication-title">Draft publication</h3>
          {!report.publication ? <p>No draft recorded. Verification alone is not publication.</p> : <>
            <p><strong>{report.publication.simulated ? 'SIMULATED OFFLINE DRAFT' : 'Live draft publication'}</strong></p>
            <p>{report.publication.confirmed ? 'Recorded and reconciled' : 'Publication incomplete or observed after interruption'}
              {report.publication.pr_number ? ` · draft #${report.publication.pr_number}` : ''}.</p>
            {report.publication.simulated && <p>No GitHub PR was created. This is a simulated record.</p>}
            <p className="small">Branch: <code>{report.publication.branch}</code><br />Commit: <code>{report.publication.commit_sha || 'Not recorded'}</code></p>
            {report.publication.reason && <p>Publication reason: {label(report.publication.reason)}</p>}
            {prLink && <a className="pr-link" href={prLink} target="_blank" rel="noopener noreferrer">Open GitHub draft PR #{report.publication.pr_number}</a>}
          </>}</section>
      </>}
      <details className="evidence-block"><summary>Ordered job events ({events.length} received)</summary>
        <ol className="events">{events.map(value => <li key={value.sequence}><time>{date(value.created_at)}</time>
          <strong>{label(value.kind)}</strong>{value.kind === 'worker_stage' && typeof value.data.stage === 'string' ? `: ${label(value.data.stage)}` : ''}</li>)}</ol>
        {moreEvents && <button disabled={!!busy} onClick={refresh}>Load more events</button>}
        <p className="small">Up to 200 received events are kept in this view; the server retains the ordered history.</p>
      </details>
    </>}
  </section>;
}
