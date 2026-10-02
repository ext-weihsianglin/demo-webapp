'use client';
import { FeatureHelp } from './feature-help';

type TermMeta = {
  term: string;
  raw_feature: string;
  label: string;
  kind: 'value' | 'missing_indicator';
  family: string;
  rewrite_role: 'editable' | 'fixed' | 'diagnostic';
};
type ExplanationTerm = TermMeta & {
  raw_before: number | null;
  raw_after: number | null;
  raw_delta: number | null;
  raw_missing_before: boolean;
  raw_missing_after: boolean;
  imputed_before: number;
  imputed_after: number;
  standardized_before: number;
  standardized_after: number;
  contribution_before: number;
  contribution_after: number;
  delta_log_odds: number;
};
type QueryExplanation = {
  query_index: number;
  query: string;
  before_logit: number;
  after_logit: number;
  delta_logit: number;
  terms: ExplanationTerm[];
};
type AggregateTerm = TermMeta & {
  mean_delta_log_odds: number;
  max_abs_delta_log_odds: number;
  positive_query_count: number;
  negative_query_count: number;
};
type P1Explanation = {
  version: string;
  model_sha256: string;
  feature_version: string;
  serving_policy: string;
  space: 'log_odds';
  intercept: number;
  interpretation: string;
  global_terms: (TermMeta & { coefficient: number })[];
  per_query: QueryExplanation[];
  aggregate_terms: AggregateTerm[];
};

export type P1Scores = {
  status: string;
  summary?: string;
  query_count: number;
  unique_query_count: number;
  mean_score?: number;
  min_score?: number;
  interpretation: string;
  feature_version: string;
  embedding?: { model: string; dimensions: number; calls: number; input_tokens: number; cached_requests: number; missing_requests: number };
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
  explanation?: P1Explanation;
  explanation_status?: string;
  explanation_summary?: string;
};

const score = (number: number) => (100 * number).toFixed(2);
const delta = (number: number) => `${number > 0 ? '+' : ''}${score(number)}`;
const signed = (number: number, digits = 4) => `${number > 0 ? '+' : ''}${number.toFixed(digits)}`;
const value = (number: number | null, digits = 4) => number === null ? 'Missing' : number.toFixed(digits);

function EffectBars({ terms, field, weights }: { terms: ExplanationTerm[]; weights: Map<string, number>; field: 'delta_log_odds' | 'contribution_before' | 'contribution_after' }) {
  const changed = terms.filter(term => Math.abs(term[field]) > 1e-12)
    .sort((left, right) => Math.abs(right[field]) - Math.abs(left[field]));
  const top = changed.slice(0, 12);
  const rest = changed.slice(12).reduce((sum, term) => sum + term[field], 0);
  const rows = top.map(term => ({ term: term.term, label: term.label, amount: term[field], meta: term as TermMeta | undefined }));
  if (Math.abs(rest) > 1e-12) rows.push({ term: 'other', label: 'Other changed features', amount: rest, meta: undefined });
  const scale = Math.max(...rows.map(row => Math.abs(row.amount)), 1e-12);
  if (!rows.length) return <p className="source-help">No transformed feature contribution changed.</p>;
  return <div className="effect-bars">{rows.map(row => <div className="effect-row" key={row.term}>
    <div>{row.meta ? <FeatureHelp term={row.term} label={row.label} rawFeature={row.meta.raw_feature} missing={row.meta.kind === 'missing_indicator'} weight={weights.get(row.term)} /> : <span title="Sum of remaining contributions; there is no single model weight for this group.">{row.label}</span>}</div>
    <div className="effect-track" aria-hidden="true"><i className={row.amount >= 0 ? 'positive' : 'negative'} style={{ width: `${50 * Math.abs(row.amount) / scale}%` }} /></div>
    <strong className={row.amount < 0 ? 'p1-regression' : ''}>{signed(row.amount)}</strong>
  </div>)}</div>;
}

function groupedTerms(terms: ExplanationTerm[]) {
  const groups = new Map<string, ExplanationTerm[]>();
  for (const term of terms) groups.set(term.raw_feature, [...(groups.get(term.raw_feature) || []), term]);
  return [...groups.values()].sort((left, right) =>
    Math.max(...right.map(term => Math.abs(term.delta_log_odds))) - Math.max(...left.map(term => Math.abs(term.delta_log_odds))));
}

function QueryReceipt({ query, weights }: { query: QueryExplanation; weights: Map<string, number> }) {
  return <div className="query-receipt">
    <p className="source-help">Feature effects add to <strong>{signed(query.delta_logit)}</strong> log odds. Probability changes are shown only for the complete model output. Weight +/− badges show the fixed coefficient sign; bars show the contribution. Click a feature name for its definition and weight.</p>
    <EffectBars terms={query.terms} weights={weights} field="delta_log_odds" />
    <details className="p1-detail"><summary>Feature values and exact rewrite effects</summary>
      <div className="p1-table-wrap"><table className="p1-table feature-table"><thead><tr><th>Feature</th><th>Raw before / after</th><th>Imputed before / after</th><th>Standardized before / after</th><th>Weight</th><th>Contribution before / after</th><th>Rewrite effect</th></tr></thead><tbody>
        {groupedTerms(query.terms).flatMap(group => group.map((term, index) => <tr key={term.term} className={term.kind === 'missing_indicator' ? 'missing-term' : ''}>
          <td title={term.term}><FeatureHelp term={term.term} label={index ? '↳ Missing state' : term.label} rawFeature={term.raw_feature} missing={term.kind === 'missing_indicator'} weight={weights.get(term.term)} /><small>{term.family} · {term.rewrite_role}</small></td>
          <td>{value(term.raw_before)} / {value(term.raw_after)}<small>Δ {value(term.raw_delta)}</small></td>
          <td>{value(term.imputed_before)} / {value(term.imputed_after)}</td>
          <td>{value(term.standardized_before)} / {value(term.standardized_after)}</td>
          <td>{signed(weights.get(term.term)!)}</td>
          <td>{signed(term.contribution_before)} / {signed(term.contribution_after)}</td>
          <td className={term.delta_log_odds < 0 ? 'p1-regression' : ''}>{signed(term.delta_log_odds)}</td>
        </tr>))}
      </tbody></table></div>
    </details>
    <details className="p1-detail"><summary>Explain original score</summary><EffectBars terms={query.terms} weights={weights} field="contribution_before" /></details>
    <details className="p1-detail"><summary>Explain rewritten score</summary><EffectBars terms={query.terms} weights={weights} field="contribution_after" /></details>
  </div>;
}

function CrossQueryView({ explanation }: { explanation: P1Explanation }) {
  const queries = new Map(explanation.per_query.map(query => [query.query_index, query]));
  const terms = explanation.aggregate_terms.filter(term => term.max_abs_delta_log_odds > 1e-12)
    .sort((left, right) => right.max_abs_delta_log_odds - left.max_abs_delta_log_odds);
  const scale = Math.max(...terms.map(term => term.max_abs_delta_log_odds), 1e-12);
  return <details className="p1-aggregate-detail"><summary>Across-query rewrite effects</summary>
    <p className="source-help">Each query cell is an exact log-odds effect. Signed means summarize them without hiding cancellation; this is not a decomposition of mean probability.</p>
    <div className="p1-table-wrap"><table className="p1-table heatmap"><thead><tr><th>Feature</th>{explanation.per_query.map(query => <th key={query.query_index} title={query.query}>Q{query.query_index + 1}</th>)}<th>Mean</th><th>Queries + / −</th></tr></thead><tbody>
      {terms.map(term => <tr key={term.term}><td><FeatureHelp term={term.term} label={term.label} rawFeature={term.raw_feature} missing={term.kind === 'missing_indicator'} weight={explanation.global_terms.find(item => item.term === term.term)?.coefficient} /></td>{[...queries.values()].map(query => {
        const effect = query.terms.find(item => item.term === term.term)!.delta_log_odds;
        const alpha = .08 + .42 * Math.abs(effect) / scale;
        return <td key={query.query_index} title={`${query.query}: ${signed(effect)}`} style={{ backgroundColor: effect >= 0 ? `rgba(79,128,95,${alpha})` : `rgba(181,92,80,${alpha})` }}>{signed(effect)}</td>;
      })}<td>{signed(term.mean_delta_log_odds)}</td><td>{term.positive_query_count} / {term.negative_query_count}</td></tr>)}
    </tbody></table></div>
  </details>;
}

function GlobalWeights({ explanation }: { explanation: P1Explanation }) {
  const groups = [
    ['Semantic similarity', (term: TermMeta) => term.kind === 'value' && term.family === 'semantic_similarity'],
    ['Prompt context', (term: TermMeta) => term.kind === 'value' && term.family === 'prompt_context'],
    ['Document context', (term: TermMeta) => term.kind === 'value' && term.family === 'document_context'],
    ['Fixed URL and metadata', (term: TermMeta) => term.kind === 'value' && (term.family === 'fixed_url' || term.family === 'fixed_metadata')],
    ['Source diagnostics', (term: TermMeta) => term.kind === 'value' && term.family === 'source_context'],
    ['Missingness indicators', (term: TermMeta) => term.kind === 'missing_indicator'],
  ] as const;
  const scale = Math.max(...explanation.global_terms.map(term => Math.abs(term.coefficient)), 1e-12);
  return <details className="p1-aggregate-detail"><summary>How the frozen model is weighted</summary>
    <p className="source-help">Standardized model weights describe the fitted classifier. They are not rewrite importance or editing recommendations.</p>
    {groups.map(([label, includes]) => {
      const terms = explanation.global_terms.filter(includes).sort((left, right) => Math.abs(right.coefficient) - Math.abs(left.coefficient));
      return terms.length > 0 && <section className="weight-group" key={label}><h4>{label}</h4><div className="effect-bars">{terms.map(term => <div className="effect-row" key={term.term}><div><FeatureHelp term={term.term} label={term.label} rawFeature={term.raw_feature} missing={term.kind === 'missing_indicator'} weight={term.coefficient} /><small>{term.rewrite_role}</small></div><div className="effect-track" aria-hidden="true"><i className={term.coefficient >= 0 ? 'positive' : 'negative'} style={{ width: `${50 * Math.abs(term.coefficient) / scale}%` }} /></div><strong className={term.coefficient < 0 ? 'p1-regression' : ''}>{signed(term.coefficient)}</strong></div>)}</div></section>;
    })}
  </details>;
}

export function P1Panel({ scores, comparison }: { scores: P1Scores; comparison?: P1Comparison }) {
  const compared = comparison?.status === 'scored';
  const explanation = comparison?.explanation;
  const weights = new Map(explanation?.global_terms.map(term => [term.term, term.coefficient]));
  const defaultQuery = compared ? [...comparison.per_query!].sort((left, right) =>
    (left.delta < 0 ? 0 : 1) - (right.delta < 0 ? 0 : 1) || Math.abs(right.delta) - Math.abs(left.delta))[0]?.query_index : undefined;
  const explanations = new Map(explanation?.per_query.map(query => [query.query_index, query]));
  return <section className="card p1-panel" aria-label="P1 scores across target queries">
    <div className="section-heading"><h2>P1 · all target queries</h2><span className="muted">{scores.feature_version} classifier</span></div>
    <p className="source-help">{scores.query_count} distinct usable target queries. Each query has equal weight.</p>
    {scores.status !== 'scored' ? <p role="status">{scores.summary}</p> : <>
      <p className="p1-aggregate">{compared ? <>Mean: <strong>{score(comparison.mean_before!)} → {score(comparison.mean_after!)}</strong> ({delta(comparison.mean_delta!)} points) · {comparison.regression_count} regressions · {comparison.improvement_count} improvements</> : <>Mean score: <strong>{score(scores.mean_score!)}</strong> / 100 · Lowest: {score(scores.min_score!)}</>}</p>
      {comparison && !compared && <p role="status">{comparison.summary}</p>}
      {compared ? <div className="p1-explanations"><div className="query-score-head"><span>Target query</span><span>Before</span><span>After</span><span>Change</span></div>{comparison.per_query!.map(row => <details className="query-explanation" key={row.query_index} open={row.query_index === defaultQuery}><summary><span>{row.query_index + 1}. {row.query}</span><span>{score(row.before)}</span><span>{score(row.after)}</span><span className={row.delta < -1e-9 ? 'p1-regression' : ''}>{delta(row.delta)}{row.delta < -1e-9 && ' · regression'}</span></summary>{explanations.get(row.query_index) && <QueryReceipt query={explanations.get(row.query_index)!} weights={weights} />}</details>)}{explanation && <><CrossQueryView explanation={explanation} /><GlobalWeights explanation={explanation} /></>}{comparison.explanation_status === 'unavailable' && <p role="status">{comparison.explanation_summary}</p>}</div> : <div className="p1-table-wrap"><table className="p1-table"><thead><tr><th>Target query</th><th>P1 score / 100</th></tr></thead><tbody>{scores.per_query.map(row => <tr key={row.query_index}><td>{row.query_index + 1}. {row.query}</td><td>{score(row.score)}</td></tr>)}</tbody></table></div>}
    </>}
    <p className="source-help">{scores.interpretation}</p>
    {explanation && <p className="source-help">{explanation.interpretation}</p>}
    {scores.embedding && <p className="source-help">{scores.embedding.model} · {scores.embedding.dimensions} dimensions · {scores.embedding.cached_requests} cached inputs · {scores.embedding.calls} embedding calls · {scores.embedding.input_tokens} reported tokens</p>}
  </section>;
}
