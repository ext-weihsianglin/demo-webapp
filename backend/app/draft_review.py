"""Recover model output for studio review without weakening research acceptance.

Only mechanically valid edits enter the page preview. Every other proposal stays
visible as escaped text, including incomplete or malformed provider output.
"""
import json
from copy import deepcopy
from pydantic import ValidationError
from preprocessing.blocks import blocks_to_markdown, blocks_to_text
from preprocessing.downstream import structure_chunks
from app.language_guard import compare_language
from app.rewriting import (ProviderEdit, ProviderProposal, Proposal, assemble_proposal,
                           editable, validate_edits, RewriteFailure)


def review_response(raw, document, chunks, allow_structure, *, completed=True):
    warnings, unapplied, edits = [], [], []
    conflicting = set()
    blocks = {b['block_id']: b for b in document['blocks']}
    chunk_map = {c['chunk_id']: c for c in chunks}
    def warn(code, message, block_id=None):
        warnings.append({'code': code, 'message': message, 'block_id': block_id})
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result and result[key] != value:
                conflicting.add(key)
            result[key] = value
        return result
    if not completed:
        warn('incomplete_output', 'Provider output was incomplete; recovered proposals require review.')
    try:
        payload = json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, TypeError):
        payload = None
        warn('invalid_json', 'The response could not be parsed. Original model output is retained below.')
    summary = 'Model response retained for human review.'
    flags = []
    if isinstance(payload, dict):
        if isinstance(payload.get('summary'), str):
            summary = payload['summary']
        flags = payload.get('review_flags', [])
        flags = [f for f in flags if isinstance(f, str)] if isinstance(flags, list) else []
        if set(payload) != {'status', 'summary', 'review_flags', 'blocks'}:
            warn('invalid_envelope', 'Response envelope does not match the requested format.')
        if payload.get('status') != 'proposed':
            warn('model_abstained', 'The model did not mark this response as a proposed rewrite.')
    values = payload.get('blocks') if isinstance(payload, dict) else None
    if not isinstance(values, dict):
        warn('invalid_blocks', 'No keyed edit list could be recovered. Inspect the original model output.')
        values = {}
    expected = {b['block_id'] for b in document['blocks'] if editable(b, document)}
    if set(values) != expected:
        warn('editable_key_set_mismatch', 'Missing or unexpected block IDs; valid individual edits are still reviewed.')
    if conflicting:
        warn('conflicting_duplicate_key', 'Conflicting JSON keys; ambiguous edits are retained without applying them.')
    for identity, value in values.items():
        if value is None:
            continue
        try:
            if identity in conflicting or conflicting - set(values):
                raise RewriteFailure('conflicting_duplicate_key', 'Ambiguous duplicate keys in the response.')
            if not isinstance(value, dict) or 'block_id' in value:
                raise RewriteFailure('invalid_output', 'Edit identity must appear only as its object key.')
            provider_edit = ProviderEdit.model_validate({**value, 'block_id': identity})
            proposal = assemble_proposal(ProviderProposal(status='proposed', summary=summary,
                review_flags=flags, edits=[provider_edit]), document, chunks)
            edit = proposal.edits[0]
            validate_edits(Proposal(status='proposed', summary=summary, review_flags=flags, edits=[edit]),
                           document, chunk_map[edit.chunk_id], allow_structure, research_fidelity=True)
            language = compare_language(edit.before, edit.after)
            if language['status'] in ('changed', 'unverified'):
                edit.review_flags.append('language_changed' if language['status'] == 'changed' else 'language_preservation_unverified')
            for flag in dict.fromkeys(edit.review_flags):
                warn(flag, 'Model or automated review flagged this edit: ' + flag, identity)
            if edit.after.strip() != edit.before.strip() or (edit.heading_level is not None and edit.heading_level != blocks[identity]['heading_level']):
                edits.append(edit)
        except (RewriteFailure, ValidationError, KeyError, TypeError) as exc:
            message = exc.message if isinstance(exc, RewriteFailure) else 'Edit fields do not match the requested format.'
            # Historical validators describe whole-request rejection; this path retains it.
            message = message.replace('No draft applied.', 'This edit is not applied to the preview.')
            warn('edit_not_applied', message, identity)
            unapplied.append({'block_id': identity, 'before': blocks.get(identity, {}).get('text'),
                             'proposal': value, 'reason': message})
    for flag in flags:
        warn(flag, 'Proposal-level review flag: ' + flag)
    if not edits:
        warn('no_applied_edits', 'No edits were applied to the page preview. The original source and model response remain available.')
    result = deepcopy(document)
    by_id = {b['block_id']: b for b in result['blocks']}
    for edit in edits:
        block = by_id[edit.block_id]
        block['text'] = edit.after
        block.pop('inline_markdown', None)
        block.pop('inline_nodes', None)
        if edit.heading_level is not None:
            block['heading_level'] = edit.heading_level
    result['text'] = blocks_to_text(result['blocks'])
    result['markdown'] = blocks_to_markdown(result['blocks'])
    result['outline'], result['chunks'] = structure_chunks(result['snapshot_id'], result['selection']['method'], result['blocks'], 6000)
    result['chunk_ids'] = [chunk['chunk_id'] for chunk in result['chunks']]
    result['artifact_kind'] = 'proposed_content_based_on_source_snapshot'
    return {'summary': summary, 'document': result, 'markdown': result['markdown'],
            'changes': [{**e.model_dump(), 'source_id': e.block_id} for e in edits],
            'validation_warnings': warnings, 'unapplied_edits': unapplied, 'raw_model_output': raw,
            'review_items': ['Draft validation is advisory. Unapplied proposals remain available for inspection.'],
            'preservation': ['Original snapshot remains intact', 'Only edits with valid source references and edit boundaries enter the page preview']}
