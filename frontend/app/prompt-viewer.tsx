'use client';
import {useEffect,useState} from 'react';
import {readApiResponse} from './api-client';
export type PromptMessages = {system:string;user:string;model:string;prompt_id:string;kind:string};
export function PromptMessagesView({messages}: {messages:PromptMessages}) {
  return <div className="prompt-messages">
    <p>{messages.model} · {messages.prompt_id}</p>
    <p>{messages.kind==='sent'?'Exact system instructions and user message sent for this draft.':'Preview uses the current page, queries, settings and displayed P1 feedback. Generation recomputes feedback; the returned draft records the exact messages sent.'}</p>
    <details open><summary>System prompt</summary><pre>{messages.system}</pre></details>
    <details><summary>User prompt · page and query context</summary><pre>{messages.user}</pre></details>
  </div>;
}
export function PromptViewer({request,disabled}: {request:object;disabled:boolean}) {
  const [open,setOpen]=useState(false),[messages,setMessages]=useState<PromptMessages|null>(null),[error,setError]=useState('');
  const key=JSON.stringify(request);
  useEffect(()=>{
    setMessages(null);setError('');
    if(!open||disabled)return;
    const controller=new AbortController();
    fetch('/api/prompt-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:key,signal:controller.signal})
      .then(readApiResponse).then(data=>{if(!controller.signal.aborted)setMessages(data);})
      .catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    return ()=>controller.abort();
  },[key,open,disabled]);
  return <section className="prompt-viewer"><button className="secondary" type="button" disabled={disabled} aria-expanded={open} onClick={()=>setOpen(!open)}>{open?'Hide selected prompts':'View selected system and user prompts'}</button>
    {open&&<>{error?<p role="alert">{error}</p>:messages?<PromptMessagesView messages={messages}/>:<p role="status">Preparing prompt preview…</p>}</>}
  </section>;
}
