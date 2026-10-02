export type Fidelity = {
  status: string;
  reason: string;
  findings?: {block_id:string;verdict:string;category:string;reason:string;source_ids:string[]}[];
  telemetry?: {model?:string;latency_ms?:number};
};

export function FidelityAssessment({assessment}: {assessment:Fidelity}) {
  const flagged = assessment.findings?.filter(f => f.verdict !== 'supported') ?? [];
  const title = assessment.status === 'passed' ? 'No fidelity issues flagged'
    : assessment.status === 'rejected' ? 'Fidelity concerns — review this draft'
    : 'Fidelity assessment incomplete';
  return <section className="card p1-panel fidelity-assessment" aria-label="Fidelity assessment">
    <h2>{title}</h2>
    <p>The draft is retained for inspection and export. This automated assessment is advisory; review the source before using the changes.</p>
    {assessment.status === 'unavailable' && <p role="status">Assessment unavailable: {assessment.reason}. Any findings below cover only the edits reviewed.</p>}
    {flagged.map(f => <article key={f.block_id} className="change">
      <strong>{f.block_id} · {f.verdict} · {f.category}</strong><p>{f.reason}</p>
      <small>Source references: {f.source_ids.length ? f.source_ids.join(', ') : 'None identified by the reviewer'}</small>
    </article>)}
    {!!assessment.findings?.length && <details><summary>All assessed edits ({assessment.findings.length})</summary>
      {assessment.findings.map(f => <p key={f.block_id}><strong>{f.block_id} · {f.verdict}</strong> — {f.reason}</p>)}
    </details>}
    <small>{assessment.telemetry?.model ?? 'Automated reviewer'}{assessment.telemetry?.latency_ms !== undefined ? ` · ${(assessment.telemetry.latency_ms / 1000).toFixed(1)}s` : ''} · Human review required</small>
  </section>;
}
