"""Independent source comparisons; these checks do not establish factual truth."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import re

from bs4 import BeautifulSoup, Tag


def normalized(text):
    return " ".join(text.split())


def source_representation_text(node):
    """Account for explicit source breaks and image alt attributes without generation."""
    copy = deepcopy(node)
    for ignored in copy.find_all(['script', 'style', 'template', 'noscript', 'head', 'title', 'meta', 'link']):
        ignored.decompose()
    for br in copy.find_all('br'):
        br.replace_with('\n')
    for image in copy.find_all('img'):
        image.replace_with(image.get('alt', ''))
    return copy.get_text()


def resolve_path(soup, path):
    """Resolve upstream tag/index paths against the original parsed source DOM."""
    if not isinstance(path, str) or not path.startswith('/'):
        return None
    node = soup
    for part in path[1:].split('/'):
        match = re.fullmatch(r'([a-zA-Z][\w:-]*)\[([1-9]\d*)\]', part)
        if not match:
            return None
        children = node.find_all(match[1], recursive=False)
        index = int(match[2]) - 1
        if index >= len(children):
            return None
        node = children[index]
    return node


class SourceInspector:
    def __init__(self, content, format):
        self.content, self.format = content, format
        self.soup = BeautifulSoup(content, 'html.parser') if format == 'html' else None
        self.lines = content.splitlines(keepends=True)

    def inspect(self, block, *, include_preview=False):
        locator = block.get('source_locator') or {}
        result = {'status': 'unresolved', 'locator_resolved': False, 'review_hints': [],
                  'scope': 'Source presence and mapping only; not factual verification.'}
        node = None
        fragment = ''
        source_text = ''
        if self.soup is not None:
            node = resolve_path(self.soup, locator.get('dom_path'))
            if node is not None:
                fragment = str(node)
                source_text = node.get('alt', '') if block['type'] == 'image' else node.get_text()
                result['preview_kind'] = 'Serialized original-source DOM element; HTML formatting may be normalized.'
        elif 'text_range' in locator:
            start, end = locator['text_range']
            if 0 <= start <= end <= len(self.content):
                fragment = source_text = self.content[start:end]
                result['preview_kind'] = 'Original source characters; end-exclusive range.'
                result['locator_resolved'] = True
        elif 'line_range' in locator:
            start, end = locator['line_range']
            if 0 <= start < end <= len(self.lines):
                fragment = source_text = ''.join(self.lines[start:end])
                result['preview_kind'] = 'Original source lines; zero-based, end-exclusive range.'
                result['locator_resolved'] = True

        result['locator_resolved'] = result['locator_resolved'] or node is not None
        if result['locator_resolved']:
            text = block.get('text', '')
            if not text:
                result['status'] = 'structure_only'
            elif block['type'] == 'table' and node is not None:
                rows = [row for row in node.find_all('tr') if row.find_parent('table') is node]
                cells = [cell for row in rows for cell in row.find_all(['th', 'td'], recursive=False)]
                expected = block['table']['cells']
                caption = node.find('caption', recursive=False)
                matches = len(cells) == len(expected) and all(normalized(source_representation_text(cell)) == parsed['text'] for cell, parsed in zip(cells, expected))
                matches = matches and normalized(source_representation_text(caption) if caption else '') == block['table']['caption']
                result['status'] = 'table_cells_match' if matches else 'text_mismatch'
                if any(str(cell.get(key, 1)) != str(parsed[key]) for cell, parsed in zip(cells, expected) for key in ('rowspan', 'colspan')):
                    result['review_hints'].append('Table span attributes were normalized; compare original attributes.')
            elif text in source_text:
                result['status'] = 'text_match'
            elif normalized(text) in normalized(source_text):
                result['status'] = 'normalized_text_match'
            elif node is not None and normalized(text) in normalized(source_representation_text(node)):
                result['status'] = 'source_representation_match'
                result['review_hints'].append('Matches source after interpreting line breaks / image alt text and normalizing whitespace.')
            elif self.format == 'markdown':
                result['status'] = 'source_range_only'
                result['review_hints'].append('Markdown formatting differs from parsed text; inspect the source range.')
            else:
                result['status'] = 'text_mismatch'

        if block.get('mapping_status') in ('ambiguous', 'unavailable'):
            result['review_hints'].append('A unique source location is not established.')
        if node is not None:
            for ancestor in [node, *node.parents]:
                if not isinstance(ancestor, Tag):
                    continue
                if ancestor.has_attr('hidden') or ancestor.get('aria-hidden', '').lower() == 'true' or re.search(r'(display\s*:\s*none|visibility\s*:\s*hidden)', ancestor.get('style', ''), re.I):
                    result['review_hints'].append('Hidden-source attribute found; rendered visibility is not computed.')
                    break
            for ancestor in [node, *node.parents]:
                if not isinstance(ancestor, Tag):
                    continue
                if ancestor.name in ('html', 'body', '[document]'):
                    continue
                markers = ' '.join([ancestor.name, ancestor.get('id', ''), *ancestor.get('class', [])])
                if ancestor.name in ('nav', 'footer', 'aside', 'form') or re.search(r'\b(cookie|consent|sidebar|breadcrumb|social|share|related|pagination)\b', markers, re.I):
                    result['review_hints'].append('Possible boilerplate context; relevance requires review.')
                    break
        if re.fullmatch(r'(skip to (?:content|main content)|accept all(?: cookies)?|cookie settings|share this(?: article)?|subscribe(?: now)?|privacy policy|terms(?: of (?:use|service))?)', block.get('text', '').strip(), re.I):
            result['review_hints'].append('Boilerplate-like wording; this is a heuristic, not a removal decision.')
        if include_preview:
            result.update(source_fragment=fragment[:4000], source_text=source_text[:4000],
                          preview_truncated=len(fragment) > 4000 or len(source_text) > 4000,
                          source_locator=block.get('source_locator'), parsed_text=block.get('text', ''))
            if not result['locator_resolved'] and self.soup is not None and block.get('text'):
                candidates = []
                tags = {'heading': [f"h{block.get('heading_level')}"], 'paragraph': ['p', 'div', 'li', 'span', 'a'],
                        'code': ['pre'], 'image': ['img']}.get(block['type'], [])
                for candidate in self.soup.find_all(tags):
                    candidate_text = candidate.get('alt', '') if block['type'] == 'image' else source_representation_text(candidate)
                    if normalized(candidate_text) == normalized(block['text']):
                        html = str(candidate)
                        candidates.append({'fragment': html[:1500], 'truncated': len(html) > 1500})
                        if len(candidates) == 3:
                            break
                result['possible_source_matches'] = candidates
                if candidates:
                    result['review_hints'].append('Matching text exists in the source; these candidates do not establish a unique mapping.')
        return result


def verify_document(content, format, parsed, chunks, facts):
    inspector = SourceInspector(content, format)
    blocks = parsed['blocks']
    by_id = {block['block_id']: block for block in blocks}
    evidence = {block['block_id']: inspector.inspect(block) for block in blocks}
    counts = Counter(item['status'] for item in evidence.values())
    partition = [identity for chunk in chunks for identity in chunk['block_ids']]
    owners = {identity: chunk['chunk_id'] for chunk in chunks for identity in chunk['block_ids']}
    checks = [
        {'name': 'Every retained block occurs once in chunk order', 'passed': partition == [block['block_id'] for block in blocks]},
        {'name': 'Nested groups stay in the same chunk', 'passed': all(block['parent_id'] in owners and owners.get(block['block_id']) == owners[block['parent_id']] for block in blocks if block['parent_id'])},
        {'name': 'Chunk text agrees with referenced blocks', 'passed': all(chunk['text'] == '\n\n'.join(by_id[identity]['text'] for identity in chunk['block_ids'] if by_id.get(identity, {}).get('text')) for chunk in chunks)},
        {'name': 'Chunk character counts agree with Markdown', 'passed': all(chunk['characters'] == len(chunk['markdown']) for chunk in chunks)},
        {'name': 'Factoid passages exactly copy their source blocks', 'passed': all(fact['source_id'] in by_id and fact['text'] == by_id[fact['source_id']]['text'] for fact in facts)},
        {'name': 'Snapshot identity matches exact payload and URL', 'passed': parsed['snapshot_id'] == hashlib.sha256(json.dumps([hashlib.sha256(content.encode()).hexdigest(), parsed['source']['href']], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()},
    ]
    if inspector.soup is not None:
        metadata = parsed['source_metadata']
        expected = {}
        for meta in inspector.soup.find_all('meta'):
            key = meta.get('name') or meta.get('property')
            if key and meta.has_attr('content'):
                expected.setdefault(key.lower(), []).append(meta['content'])
        title = inspector.soup.title.get_text(' ', strip=True) if inspector.soup.title else ''
        checks.append({'name': 'Title and meta-tag values match the saved source', 'passed': metadata['title'] == title and metadata['metadata'] == expected and metadata['description'] == next(iter(expected.get('description', [])), None)})
        source_jsonld = [node for node in inspector.soup.find_all('script') if node.get('type', '').split(';')[0].strip().lower() == 'application/ld+json']
        jsonld_matches = len(source_jsonld) == len(metadata['jsonld']) and all((node := resolve_path(inspector.soup, entry['source_locator']['dom_path'])) is not None and node.get_text() == entry['raw'] for entry in metadata['jsonld'])
        checks.append({'name': 'JSON-LD raw values resolve to source script elements', 'passed': jsonld_matches})
    return {'version': 'source-audit-v1', 'scope': 'Mechanical source and consistency checks. Not proof of factual truth, completeness, relevance or rendered visibility.',
            'summary': {'total_blocks': len(blocks), 'text_blocks': sum(bool(block['text']) for block in blocks),
                        'containers': sum(not block['text'] and block['type'] in ('list', 'list_item', 'quote') for block in blocks),
                        'source_status_counts': dict(counts), 'ambiguous_mappings': sum(block['mapping_status'] == 'ambiguous' for block in blocks),
                        'unavailable_mappings': sum(block['mapping_status'] == 'unavailable' for block in blocks),
                        'boilerplate_hints': sum(any('boilerplate' in hint.lower() for hint in item['review_hints']) for item in evidence.values()),
                        'oversized_chunks': sum(chunk['oversized'] for chunk in chunks)},
            'checks': checks, 'blocks': evidence}
