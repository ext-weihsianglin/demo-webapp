'use client';
import { useState } from 'react';
import { readApiResponse } from './api-client';
import { P1Panel, type P1Scores, type P1Comparison } from './p1-scores';

type Report = {
 original_href: string; snapshot_id: string; selected_href: string; limitations: string[]; body_fidelity: string;
 original: P1Scores; body_only: P1Scores | null; body_comparison: P1Comparison | null;
 candidates: {proposed_href:string;keep_current:boolean;rationale:string;evidence:{snapshot_id:string;block_id:string;text:string}[];normalized_path:{text:string;status:string;reason:string|null};query_coverage:{query:string;status:string;overlapping_terms:string[]}[];path_only:P1Scores;combined:P1Scores|null;comparisons:{path_vs_original:P1Comparison;combined_vs_original:P1Comparison;combined_vs_body:P1Comparison}}[];
};
export function URLProposals({source, bodyProposal, allowStructure=false}: {source:object;bodyProposal?:object;allowStructure?:boolean}) {
 const [enabled,setEnabled]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[report,setReport]=useState<Report|null>(null);
 async function run(){setBusy(true);setReport(null);setError('');try{
  const response=await fetch('/api/url-proposals',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...source,opt_in:true,body_proposal:bodyProposal,allow_structure:allowStructure})});
  setReport(await readApiResponse(response));
 }catch(e){setError(e instanceof Error?e.message:'URL experiment failed.');}finally{setBusy(false);}}
 function download(){if(!report)return;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='hypothetical-url-recommendations.json';a.click();URL.revokeObjectURL(url);}
 return <section className="card"><h2>Hypothetical URL suffix experiment</h2><label className="check-label"><input type="checkbox" checked={enabled} disabled={busy} onChange={e=>{setEnabled(e.target.checked);setReport(null);}}/><span>Opt in to source-grounded URL proposals</span></label>
 {enabled&&<><p>Preserves the original snapshot and canonical metadata. Source H1s supply alternatives; host queries do not supply new keywords. No proposed URL is fetched, published or redirected.</p><button className="secondary" disabled={busy} onClick={()=>void run()}>{busy?'Scoring proposals…':'Compare hypothetical URLs'}</button>{error&&<p role="alert">{error}</p>}
 {report&&<><p>Original URL: <code>{report.original_href}</code><br/>Source snapshot: <code>{report.snapshot_id}</code><br/>Model selection: <code>{report.selected_href}</code></p><p>{report.body_fidelity}</p>{report.limitations.map(item=><p className="source-help" key={item}>{item}</p>)}<button className="secondary" onClick={download}>Export migration recommendations</button>
 {report.body_only&&<details><summary>Body-only vs original</summary><P1Panel scores={report.original} comparison={report.body_comparison!}/></details>}
 {report.candidates.map(candidate=><details key={candidate.proposed_href}><summary>{candidate.keep_current?'Keep current URL':candidate.proposed_href}</summary><p>Proposed URL: <code>{candidate.proposed_href}</code></p><p>{candidate.rationale}</p><p className="source-help">Canonical path input: {candidate.normalized_path.text || candidate.normalized_path.reason} · {candidate.normalized_path.status}</p>{candidate.evidence.map(row=><p className="source-help" key={row.block_id}>Original H1: {row.text}<br/>Source: {row.snapshot_id} / {row.block_id}</p>)}{candidate.query_coverage.map(row=><p key={row.query}>{row.query}: {row.status} ({row.overlapping_terms.join(', ')||'none'})</p>)}{!candidate.combined&&<p className="source-help">Body-only and combined scenarios require an imported body proposal.</p>}<h3>Path-only vs original</h3><P1Panel scores={candidate.path_only} comparison={candidate.comparisons.path_vs_original}/>{candidate.combined&&<><h3>Combined vs original</h3><P1Panel scores={candidate.combined} comparison={candidate.comparisons.combined_vs_original}/><h3>Combined vs body-only</h3><P1Panel scores={candidate.combined} comparison={candidate.comparisons.combined_vs_body}/></>}</details>)}</>}
 </>}
 </section>;
}
