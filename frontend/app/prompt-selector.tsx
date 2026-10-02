'use client';
import { readApiResponse } from './api-client';
import { useEffect, useState } from 'react';

type Entry = {id:string;kind:string;prompt_hash:string;selected:boolean};
export function PromptSelector({model,value,onChange,disabled=false,refreshKey=0}: {model:string;value:string;onChange:(id:string)=>void;disabled?:boolean;refreshKey?:number}) {
  const [entries,setEntries]=useState<Entry[]>([]),[error,setError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    setEntries([]);setError('');
    if(!model)return;
    fetch(`/api/prompts?model=${encodeURIComponent(model)}`,{signal:controller.signal}).then(async r=>{
      if(!r.ok)throw new Error('Prompt registry unavailable');
      const data=await readApiResponse(r);
      setEntries(data.prompts);onChange(data.prompts.some((p:Entry)=>p.id===value)?value:data.selected_id);
    }).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    return ()=>controller.abort();
  },[model,onChange,refreshKey]);
  return <><label htmlFor="prompt-selector">Rewrite prompt</label><select id="prompt-selector" value={value} disabled={disabled||!entries.length} onChange={e=>onChange(e.target.value)}>
    {!entries.length&&<option value="">Loading compatible prompts…</option>}
    {entries.map(p=><option key={p.id} value={p.id}>{p.kind==='baseline'?'Baseline v7':'Experimental '+p.prompt_hash.slice(0,8)}{p.selected?' · selected default':''}</option>)}
  </select>{error&&<p role="alert" className="error">{error}</p>}<small className="source-help">Prompts are specific to {model}. Experimental prompts require review.</small></>;
}
