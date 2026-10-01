'use client';

import { useEffect, useState } from 'react';

export type Example = {
  snapshot_id: string;
  hostname: string;
  href: string;
  title: string;
  query: string;
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
      {selected && <p className="source-help"><strong>Held-out source</strong> · {selected.snapshot_id.slice(0, 12)}<br/>Try the original query or enter your own. The saved source stays unchanged.</p>}
    </>}
    {mode === 'custom' && <p className="source-help">Enter your own target query and paste a saved page below.</p>}
  </div>;
}
