"""Research-only P1 minus explicit per-edit fidelity deductions."""
VERSION = 'p1-fidelity-penalty-v1'


def policy(unsupported=0.05, uncertain=0.02):
    return {'version':VERSION,'unsupported_per_edit':unsupported,'uncertain_per_edit':uncertain,
            'formula':'raw_p1 - sum(per_edit_penalties)',
            'aggregation':'one strongest verdict per edited block; no division by edit count',
            'scope':'research_only','ordinary_draft_policy':'whole_proposal_fidelity_gate'}


def components(raw_p1, findings, changes, config):
    violations={}
    weights={'unsupported':config['unsupported_per_edit'],'uncertain':config['uncertain_per_edit']}
    for finding in findings:
        if finding['verdict'] in weights:
            violations[finding['block_id']]={**finding,'penalty':weights[finding['verdict']]}
    # Rewriter self-reported concerns remain feedback even if the judge misses them.
    for change in changes:
        flags=change.get('review_flags',[])
        verdict='unsupported' if 'unsupported_addition' in flags else 'uncertain' if 'missing_evidence' in flags else None
        if verdict:
            bid=change['source_id']
            current=violations.get(bid)
            if current is None or (verdict=='unsupported' and current['verdict']=='uncertain'):
                violations[bid]={'block_id':bid,'verdict':verdict,'category':'rewriter_self_report',
                    'reason':'Rewriter flagged '+', '.join(f for f in flags if f in ('unsupported_addition','missing_evidence')),
                    'source_ids':[e['block_id'] for e in change['evidence']], 'penalty':weights[verdict]}
    deductions=list(violations.values())
    penalty=sum(f['penalty'] for f in deductions)
    return {'raw_p1':raw_p1,'fidelity_penalty':penalty,'reward':raw_p1-penalty,
            'unsupported_edits':sum(f['verdict']=='unsupported' for f in deductions),
            'uncertain_edits':sum(f['verdict']=='uncertain' for f in deductions),
            'factual_violations':deductions,'policy':config}
