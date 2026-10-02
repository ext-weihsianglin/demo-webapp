export type DraftWarnings = {
  validation_warnings?: {code:string;message:string;block_id:string|null}[];
  unapplied_edits?: {block_id:string;before:string|null;proposal:unknown;reason:string}[];
  raw_model_output?: string;
};

export function DraftReview({draft}: {draft:DraftWarnings}) {
  return <section className="card draft-review" aria-label="Draft validation review">
    <h2>{draft.validation_warnings?.length ? 'Draft retained — review warnings' : 'Draft validation'}</h2>
    <p>Warnings do not discard the model response. The page preview and Markdown export include only the edits listed under “What changed.” Proposals that could not be applied remain below.</p>
    {draft.validation_warnings?.map((w,i)=><p key={i}><strong>{w.block_id ? `${w.block_id} · ` : ''}{w.code}</strong> — {w.message}</p>)}
    {draft.unapplied_edits?.map((edit,i)=><details key={i}><summary>{edit.block_id} · Not applied to preview</summary>
      <p>{edit.reason}</p>{edit.before!==null&&<><h3>Original text</h3><pre>{edit.before}</pre></>}
      <h3>Model proposal</h3><pre>{JSON.stringify(edit.proposal,null,2)}</pre>
    </details>)}
    {draft.raw_model_output&&<details><summary>Original model response (including unapplied proposals)</summary><pre>{draft.raw_model_output}</pre></details>}
  </section>;
}
