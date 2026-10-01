'use client';

import { useState } from 'react';
import type { ParsedBlock } from './extraction-view';

export type BlockCheck = {status:string; locator_resolved:boolean; review_hints:string[]};
export type Verification = {
  scope:string;
  summary:{total_blocks:number;text_blocks:number;containers:number;ambiguous_mappings:number;unavailable_mappings:number;boilerplate_hints:number;oversized_chunks:number;source_status_counts:Record<string,number>};
  checks:{name:string;passed:boolean}[];
  blocks:Record<string,BlockCheck>;
};
type Evidence = BlockCheck & {preview_kind?:string;source_fragment:string;source_text:string;parsed_text:string;preview_truncated:boolean;possible_source_matches?:{fragment:string;truncated:boolean}[]};

export const statusLabels:Record<string,string> = {
  text_match:'Text found at source location',normalized_text_match:'Text matches after whitespace normalization',
  source_representation_match:'Text matches source breaks / alt text',table_cells_match:'Table cells match source',
  structure_only:'Structural container; no own text',source_range_only:'Source range found; formatting needs review',
  unresolved:'Source location unresolved',text_mismatch:'Source comparison needs review',
};

export function SourceEvidence({blockId, source, check}:{blockId:string;source:object;check?:BlockCheck}) {
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[data,setData]=useState<Evidence|null>(null),[error,setError]=useState('');
  async function load(){
    setBusy(true);setError('');
    try{
      const response=await fetch('/api/evidence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...source,block_id:blockId})});
      const result=await response.json();
      if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Source comparison is unavailable.');
      setData(result);
    }catch(error){setError(error instanceof Error?error.message:'Source comparison is unavailable.');}
    finally{setBusy(false);}
  }
  return <div className="source-evidence">
    {check&&<p className={'evidence-label '+(check.status==='unresolved'||check.status==='text_mismatch'?'needs-review':'')}>{statusLabels[check.status]||check.status}</p>}
    {check?.review_hints.map(hint=><p className="review-hint" key={hint}>{hint}</p>)}
    <button className="text-button" type="button" aria-expanded={open} disabled={busy} onClick={()=>{setOpen(!open);if(!open&&!data)void load();}}>{busy?'Loading source…':open?'Hide source comparison':'Compare with source'}</button>
    {open&&<div className="evidence-content">
      {error&&<p role="alert">{error} <button type="button" onClick={()=>void load()}>Retry</button></p>}
      {data&&<>
        <p className="source-help">{data.preview_kind||'A unique source location has not been established.'}</p>
        <div className="source-comparison"><div><strong>Parsed text</strong><pre>{data.parsed_text||'(Container with no own text)'}</pre></div><div><strong>Source element / range</strong><pre>{data.source_fragment||'(No resolved source location)'}</pre></div></div>
        {data.preview_truncated&&<p className="source-help">Source preview is capped at 4,000 characters. Download the original snapshot for the full source.</p>}
        {data.possible_source_matches?.length? <details><summary>Possible source matches · unique mapping not established</summary>{data.possible_source_matches.map((candidate,index)=><pre key={index}>{candidate.fragment}{candidate.truncated?'\n(Preview truncated)':''}</pre>)}</details>:null}
      </>}
    </div>}
  </div>;
}

export function VerificationSummary({verification}:{verification:Verification}){
  const summary=verification.summary,failed=verification.checks.filter(check=>!check.passed);
  return <section className="verification-summary card">
    <div className="section-heading"><h2>Extraction checks</h2><span className="muted">{failed.length?`${failed.length} failed checks`:'Consistency checks passed'}</span></div>
    <div className="verification-counts"><div><strong>{summary.text_blocks}</strong><span>blocks with text</span><small>{summary.containers} list / quote containers have no own text</small></div><div><strong>{summary.ambiguous_mappings+summary.unavailable_mappings}</strong><span>mappings need review</span><small>{summary.ambiguous_mappings} ambiguous · {summary.unavailable_mappings} unavailable</small></div><div><strong>{summary.boilerplate_hints}</strong><span>boilerplate review hints</span><small>Heuristics; content remains retained</small></div></div>
    <details><summary>Inspect mechanical checks and limits</summary><ul>{verification.checks.map(check=><li key={check.name}>{check.passed?'Pass':'Review'} · {check.name}</li>)}</ul><p>{verification.scope}</p><p>{summary.oversized_chunks} oversized chunks are retained in full; chunk size is measured in characters.</p></details>
  </section>;
}

export function SourceStatements({facts,verification,source}:{facts:{source_id:string;text:string}[];verification:Verification;source:object}){
  return <><p className="tab-explanation">These are copied source passages, often whole paragraphs or tables. They are not atomic facts or independently verified claims.</p>{facts.map(fact=><div className="fact" key={fact.source_id}><span className="fact-tag">{fact.source_id} · Unverified source passage</span><p>{fact.text}</p><SourceEvidence blockId={fact.source_id} source={source} check={verification.blocks[fact.source_id]}/></div>)}</>;
}

export function MetadataView({metadata}:{metadata:Record<string,unknown>}){
  const fields=['title','language','direction','description','canonical','metadata','jsonld'];
  function display(key:string){const value=metadata[key];return <div className="metadata" key={key}><strong>{key}</strong><pre>{value===null||value===''?'Not present':typeof value==='string'?value:JSON.stringify(value,null,2)}</pre></div>;}
  return <><p className="tab-explanation">Source fields are copied from the snapshot. JSON-LD is parsed from its original raw string; resolved URLs and parsed JSON fields are transformations, not externally verified information.</p><h3 className="metadata-group">Source fields</h3>{fields.map(display)}<h3 className="metadata-group">Computed inventory and heuristic diagnostics</h3><p className="tab-explanation">Counts, heading lists and warnings are derived. Visibility attributes are recorded; rendered visibility is unknown.</p>{Object.keys(metadata).filter(key=>!fields.includes(key)).map(display)}</>;
}

export function ReviewTools({analysis,sourceContent,format,onDraftTools}:{analysis:object;sourceContent:string;format:string;onDraftTools:()=>void}){
  function download(body:string,name:string,type:string){const url=URL.createObjectURL(new Blob([body],{type}));const link=document.createElement('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url);}
  return <section className="card review-tools"><h2>Verify against the source</h2><p>Use Compare with source on a block or passage. Review ambiguous mappings, hidden attributes and boilerplate hints before trusting the representation.</p><p>Chunk heading paths are inferred from heading levels and order. They do not establish the original page layout or logical grouping.</p><details><summary>Original snapshot · escaped text</summary><pre>{sourceContent.slice(0,8000)}</pre>{sourceContent.length>8000&&<p>Preview capped at 8,000 characters. The download preserves the full snapshot.</p>}</details><button className="secondary wide" onClick={()=>download(sourceContent,`source-snapshot.${format==='html'?'html':format==='markdown'?'md':'txt'}`,'text/plain')}>Download original snapshot</button><button className="secondary wide" onClick={()=>download(JSON.stringify(analysis,null,2),'extraction-review.json','application/json')}>Export extraction report</button><button className="text-button" onClick={onDraftTools}>Open draft tools</button></section>;
}

export function blockMatchesReviewFilter(block:ParsedBlock, check:BlockCheck|undefined, filter:string){
  if(filter==='text')return Boolean(block.text);
  if(filter==='mapping')return block.mapping_status==='ambiguous'||block.mapping_status==='unavailable'||check?.status==='text_mismatch';
  if(filter==='boilerplate')return check?.review_hints.some(hint=>hint.toLowerCase().includes('boilerplate'));
  if(filter==='hidden')return check?.review_hints.some(hint=>hint.startsWith('Hidden-source'));
  return true;
}
