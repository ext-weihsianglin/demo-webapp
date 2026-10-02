"""Opt-in, source-grounded hypothetical suffixes; no network or migration actions."""
from copy import deepcopy
import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit

from preprocessing.blocks import blocks_to_text, blocks_to_markdown
from preprocessing.downstream import structure_chunks
from representations.url_path import normalize_path
from app.rewriting import validate_edits, RewriteFailure
from app.scoring import score_document, compare_scores, public_scores

POLICY = 'source-h1-suffix-v1'
LIMITS = ('Heading support is not semantic entailment or factual verification. Query coverage is lexical and may overstate relevance.',
          'P1 deltas are classifier effects, not measured citation uplift. Path similarity is query-to-path, not query-to-title.',
          'Routes, collisions, redirects and canonical/internal-link/sitemap changes require a separately authorized migration.')


def replace_suffix(href, slug):
    """Preserve every byte outside the final stem; reject ambiguous route shapes."""
    parts = urlsplit(href)
    normalized = normalize_path(href)
    if normalized['reason'] == 'invalid_or_unsupported_url_path' or parts.username or parts.password:
        raise ValueError('Invalid or ambiguous source URL')
    path = parts.path
    trailing = '/' if path.endswith('/') else ''
    core = path[:-1] if trailing else path
    parent, _, segment = core.rpartition('/')
    decoded = unquote(segment)
    if not segment or decoded in ('.', '..') or any(c in decoded for c in '/\\;'):
        raise ValueError('Root or ambiguous route has no replaceable suffix')
    # Preserve known document extensions; application/binary routes abstain.
    extension = ''
    if '.' in decoded:
        stem, dot, ext = decoded.rpartition('.')
        if not stem or ext.lower() not in ('html', 'htm', 'md'):
            raise ValueError('Unsupported route extension')
        extension = segment[segment.rfind('.'):]
        if not extension.startswith('.'):
            raise ValueError('Encoded extension is ambiguous')
    if not slug or len(slug.encode()) > 120 or not re.fullmatch(r'[^\W_]+(?:-[^\W_]+)*', slug, re.UNICODE):
        raise ValueError('Invalid descriptive suffix')
    new_path = parent + '/' + quote(slug, safe='-') + extension + trailing
    # Locate the path in the original URL so casing, empty ?/# and escapes survive.
    authority_end = href.find('/', href.find('://') + 3)
    if authority_end < 0:
        raise ValueError('Root URL has no suffix')
    return href[:authority_end] + new_path + href[authority_end + len(path):]


def tokens(text):
    return set(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', text).casefold()))


def candidates(document, queries):
    href = document['source']['href']
    result = [{'proposed_href': href, 'keep_current': True, 'rationale': 'Explicit no-change option.', 'evidence': [], 'query_coverage': []}]
    # Only page-level H1s, in source order. Never use target query words to generate.
    for block in document['blocks']:
        if block['type'] != 'heading' or block.get('heading_level') != 1:
            continue
        words = re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', block['text']).casefold())
        if not 2 <= len(words) <= 12:
            continue
        try:
            proposed = replace_suffix(href, '-'.join(words))
        except ValueError:
            continue
        if proposed in {r['proposed_href'] for r in result}:
            continue
        result.append({'proposed_href': proposed, 'keep_current': False,
            'rationale': 'Descriptive suffix copied from the original retained page H1; human topic/route review required.',
            'evidence': [{'snapshot_id': document['snapshot_id'], 'block_id': block['block_id'], 'text': block['text']}],
            'query_coverage': [{'query': q, 'overlapping_terms': sorted(tokens(q) & tokens(block['text'])),
                                'status': 'lexical_overlap_only' if tokens(q) & tokens(block['text']) else 'no_lexical_evidence'} for q in queries]})
        if len(result) == 4:
            break
    return result


def body_view(document, proposal, allow_structure=False):
    """Reconstruct imported body edits from this source, never accept client metadata."""
    if proposal is None:
        return None
    if len({e.block_id for e in proposal.edits}) != len(proposal.edits):
        raise RewriteFailure('invalid_output', 'Duplicate body targets')
    chunk_ids = {c['chunk_id'] for c in document['chunks']}
    if any(e.chunk_id not in chunk_ids for e in proposal.edits):
        raise RewriteFailure('invalid_output', 'Unknown body chunk')
    for chunk in document['chunks']:
        validate_edits(proposal.model_copy(update={'edits': [e for e in proposal.edits if e.chunk_id == chunk['chunk_id']]}), document, chunk, allow_structure)
    result = deepcopy(document)
    by_id = {b['block_id']: b for b in result['blocks']}
    for edit in proposal.edits:
        by_id[edit.block_id]['text'] = edit.after
        by_id[edit.block_id].pop('inline_markdown', None)
        if edit.heading_level is not None:
            by_id[edit.block_id]['heading_level'] = edit.heading_level
    result['text'] = blocks_to_text(result['blocks'])
    result['markdown'] = blocks_to_markdown(result['blocks'])
    result['outline'], result['chunks'] = structure_chunks(result['snapshot_id'], result['selection']['method'], result['blocks'], 6000)
    result['chunk_ids'] = [c['chunk_id'] for c in result['chunks']]
    result['artifact_kind'] = 'proposed_content_based_on_source_snapshot'
    return result


def experiment(document, content, format, queries, *, body=None, scorer=score_document):
    queries = list(dict.fromkeys(q.strip() for q in queries))
    def score(doc, href=None):
        return scorer(doc, content, format, queries, explain=True, proposed_href=href)
    original = score(document)
    body_scores = score(body) if body is not None else None
    output = []
    for candidate in candidates(document, queries):
        href = candidate['proposed_href']
        path = score(document, href)
        combined = score(body, href) if body is not None else None
        comparison = compare_scores(original, path)
        # Mark URL terms editable only in this opt-in experiment's explanations.
        comparisons = {'path_vs_original': comparison,
                       'combined_vs_original': compare_scores(original, combined) if combined else {'status': 'unavailable', 'summary': 'Supply a body proposal for the combined scenario.'},
                       'combined_vs_body': compare_scores(body_scores, combined) if combined else {'status': 'unavailable', 'summary': 'No body proposal supplied.'}}
        for item in comparisons.values():
            explanation = item.get('explanation', {})
            for terms in [explanation.get('global_terms', []), explanation.get('aggregate_terms', []), *[q['terms'] for q in explanation.get('per_query', [])]]:
                for term in terms:
                    if term['family'] == 'fixed_url':
                        term['rewrite_role'] = 'editable'
        output.append({**candidate, 'normalized_path': normalize_path(href), 'path_only': public_scores(path), 'combined': public_scores(combined) if combined else None, 'comparisons': comparisons})
    eligible = [c for c in output if not c['keep_current'] and c['comparisons']['path_vs_original']['status'] == 'scored'
                and c['comparisons']['path_vs_original']['mean_delta'] > 1e-9
                and c['comparisons']['path_vs_original']['regression_count'] == 0]
    selected = max(eligible, key=lambda c: c['comparisons']['path_vs_original']['mean_delta']) if eligible else output[0]
    return {'policy': POLICY, 'snapshot_id': document['snapshot_id'], 'original_href': document['source']['href'],
            'source_metadata': deepcopy(document['source_metadata']), 'target_queries': queries,
            'original': public_scores(original), 'body_only': public_scores(body_scores) if body_scores else None,
            'body_comparison': compare_scores(original, body_scores) if body_scores else None,
            'body_fidelity': 'Imported edits checked mechanically; semantic/language fidelity not re-certified.' if body else 'No body proposal supplied.',
            'candidates': output, 'selected_href': selected['proposed_href'], 'limitations': list(LIMITS),
            'selection_rule': 'Positive path-only mean delta > 1e-9 with zero per-query regressions below -1e-9; highest mean, source-order ties; otherwise keep current.',
            'selection_reason': 'eligible_model_gain_requires_human_review' if eligible else 'keep_current_no_eligible_gain_or_scores_unavailable',
            'migration_recommendation': {'status': 'hypothetical_review_only', 'original_href': document['source']['href'], 'proposed_href': selected['proposed_href'],
                'required_separate_checks': ['route constraints and existence', 'collision checks', 'permanent redirects', 'canonical/internal links/sitemap updates', 'monitoring']}}
