'use client';

export type P1Scores = {
  status: string;
  summary?: string;
  query_count: number;
  unique_query_count: number;
  mean_score?: number;
  min_score?: number;
  interpretation: string;
  per_query: { query_index: number; query: string; score: number }[];
};
export type P1Comparison = {
  status: string;
  summary?: string;
  mean_before?: number;
  mean_after?: number;
  mean_delta?: number;
  regression_count?: number;
  improvement_count?: number;
  per_query?: { query_index: number; query: string; before: number; after: number; delta: number }[];
};
const score = (value: number) => (100 * value).toFixed(2);
const delta = (value: number) => `${value > 0 ? '+' : ''}${score(value)}`;

export function P1Panel({ scores, comparison }: { scores: P1Scores; comparison?: P1Comparison }) {
  const compared = comparison?.status === 'scored';
  return <section className="card p1-panel" aria-label="P1 scores across target queries">
    <div className="section-heading"><h2>P1 · all target queries</h2><span className="muted">Frozen v2 classifier</span></div>
    <p className="source-help">{scores.query_count} distinct usable target queries. Each query has equal weight.</p>
    {scores.status !== 'scored' ? <p role="status">{scores.summary}</p> : <>
      <p className="p1-aggregate">{compared ? <>Mean: <strong>{score(comparison.mean_before!)} → {score(comparison.mean_after!)}</strong> ({delta(comparison.mean_delta!)} points) · {comparison.regression_count} regressions · {comparison.improvement_count} improvements</> : <>Mean score: <strong>{score(scores.mean_score!)}</strong> / 100 · Lowest: {score(scores.min_score!)}</>}</p>
      {comparison && !compared && <p role="status">{comparison.summary}</p>}
      <div className="p1-table-wrap"><table className="p1-table"><thead><tr><th>Target query</th><th>{compared ? 'Before' : 'P1 score / 100'}</th>{compared && <><th>After</th><th>Change</th></>}</tr></thead><tbody>
        {compared ? comparison.per_query!.map(row => <tr key={row.query_index}><td>{row.query_index + 1}. {row.query}</td><td>{score(row.before)}</td><td>{score(row.after)}</td><td className={row.delta < -1e-9 ? 'p1-regression' : ''}>{delta(row.delta)}{row.delta < -1e-9 && ' · regression'}</td></tr>) : scores.per_query.map(row => <tr key={row.query_index}><td>{row.query_index + 1}. {row.query}</td><td>{score(row.score)}</td></tr>)}
      </tbody></table></div>
    </>}
    <p className="source-help">{scores.interpretation}</p>
  </section>;
}
