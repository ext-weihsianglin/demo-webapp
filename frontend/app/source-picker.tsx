'use client';

import { useEffect, useState } from 'react';

export type Example = {
  snapshot_id: string;
  hostname: string;
  href: string;
  title: string;
  query: string;
  queries?: string[];
  query_record_count?: number;
  unusable_query_count?: number;
  query_scope?: string;
  query_records?: {query:string;href:string;usable:boolean}[];
  format: string;
  split: 'heldout';
  characters: number;
  content?: string;
};

export function SourcePicker({ mode, selected, onMode, onExample, onLoading }: {
  mode: 'custom' | 'examples';
  selected: Example | null;
  onMode: (mode: 'custom' | 'examples') => void;
  onExample: (id: string) => void;
  onLoading: (loading: boolean) => void;
}) {
  const [examples, setExamples] = useState<Example[]>([]);
  const [host, setHost] = useState('');
  const [message, setMessage] = useState('');
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (mode !== 'examples') return;
    const controller = new AbortController();
    onLoading(true);
    setMessage('Loading saved examples…');
    setFailed(false);
    fetch('/api/examples', { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('Saved examples are unavailable. Check the API connection.');
        return response.json();
      })
      .then(data => { setExamples(data.examples); setMessage(data.message); })
      .catch(error => { if (!controller.signal.aborted) { setFailed(true); setMessage(error.message); } })
      .finally(() => { if (!controller.signal.aborted) onLoading(false); });
    return () => controller.abort();
  }, [mode, attempt, onLoading]);

  const hosts = [...new Set(examples.map(example => example.hostname))].sort();
  const activeHost = selected?.hostname || host;
  return <div className="source-picker">
    <div className="source-modes" role="group" aria-label="Source type">
      <button type="button" aria-pressed={mode === 'custom'} onClick={() => onMode('custom')}>Your own page</button>
      <button type="button" aria-pressed={mode === 'examples'} onClick={() => onMode('examples')}>Held-out examples</button>
    </div>
    {mode === 'examples' && <>
      <p className="source-help" role="status">{message}</p>
      {failed && <button className="secondary" type="button" onClick={() => setAttempt(attempt + 1)}>Retry loading examples</button>}
      {examples.length > 0 && <div className="example-fields">
        <label htmlFor="example-host">Example host</label>
        <select id="example-host" value={activeHost} onChange={event => { setHost(event.target.value); onExample(''); }}>
          <option value="">Choose a host</option>
          {hosts.map(hostname => <option key={hostname}>{hostname}</option>)}
        </select>
        <label htmlFor="example-page">Saved page</label>
        <select id="example-page" value={selected?.snapshot_id || ''} disabled={!activeHost} onChange={event => onExample(event.target.value)}>
          <option value="">Choose a page</option>
          {examples.filter(example => example.hostname === activeHost).map(example => <option key={example.snapshot_id} value={example.snapshot_id}>{example.title}</option>)}
        </select>
      </div>}
      {selected && <div><p className="source-help"><strong>Held-out source</strong> · {selected.snapshot_id.slice(0, 12)}<br/>{selected.query_scope === 'host' ? `${selected.query_record_count} host prompt records loaded together · ${selected.queries?.length} distinct usable queries. Duplicates counted once. ${selected.unusable_query_count || 0} unusable records excluded from scoring.` : 'Legacy bundle: one query loaded. Rebuild the example bundle to include all host prompts.'} The queries may reference other pages on this host. Edit the set freely; the saved source stays unchanged.</p>{selected.query_records && <details><summary>Original host prompt provenance</summary><ol>{selected.query_records.map((record, i) => <li key={i}>{record.query || '[blank prompt]'}{!record.usable && ' · unusable'}<br/><span className="muted">{record.href}</span></li>)}</ol></details>}</div>}
    </>}
    {mode === 'custom' && <p className="source-help">Enter your target queries and paste a saved page below.</p>}
  </div>;
}
