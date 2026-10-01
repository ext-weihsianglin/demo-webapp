"""Upstream retention extraction with mock grading and draft generation."""
from copy import deepcopy
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from app.examples import catalog, load_example
from app.extraction import UPSTREAM, extract_document, section_view
from preprocessing.blocks import blocks_to_markdown
from app.verification import SourceInspector, verify_document

app = FastAPI(title="Content Studio", version="0.1.0")

class Source(BaseModel):
    example_id: str | None = None
    query: str = Field(min_length=3, max_length=1000)
    href: str = Field(max_length=2048)
    hostname: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=20, max_length=8000000)
    format: str = "html"

    @model_validator(mode="before")
    @classmethod
    def resolve_example(cls, values):
        if isinstance(values, dict) and values.get("example_id"):
            example = load_example(values["example_id"])
            values = dict(values)
            for key in ("href", "hostname", "content", "format"):
                if key in values and values[key] != example[key]:
                    raise ValueError("Example source is read-only. Switch to your own page to edit it.")
                values[key] = example[key]
        return values

    @field_validator("query", "href", "hostname")
    @classmethod
    def trim(cls, value):
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def validate_source(self):
        parsed = urlparse(self.href)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Page URL must be an HTTP or HTTPS URL")
        if parsed.hostname.lower().removeprefix("www.") != self.hostname.lower().removeprefix("www."):
            raise ValueError("Hostname must match the page URL")
        if self.format not in ("html", "markdown", "text"):
            raise ValueError("Choose HTML, Markdown or text")
        if not self.example_id and len(self.content) > 200000:
            raise ValueError("Custom snapshots must be at most 200,000 characters")
        if len(self.content.strip()) < 20:
            raise ValueError("Add at least 20 characters of source content")
        return self

class DraftRequest(Source):
    allow_structure: bool = False
    tone: str = "Preserve original"

class EvidenceRequest(Source):
    block_id: str = Field(min_length=1, max_length=64)


@app.get('/api/health')
def health():
    return {"status": "ok", "mode": "mock", "extraction": "retention-first-v1", "upstream_revision": UPSTREAM["revision"], "package_version": UPSTREAM["package_version"]}

@app.get('/api/examples')
def examples():
    return catalog()

@app.get('/api/examples/{snapshot_id}')
def example(snapshot_id: str):
    return load_example(snapshot_id)

def source_origin(source):
    if not source.example_id:
        return {"kind": "custom"}
    item = load_example(source.example_id)
    return {"kind": "example", "snapshot_id": item["snapshot_id"], "split": item["split"], "manifest_hash": item["manifest_hash"], "payload_hash": item["payload_hash"]}

@app.post('/api/analyze')
def analyze(source: Source):
    parsed, chunks = extract_document(source.content, source.format, source.href, source.hostname)
    sections = [section_view(block) for block in parsed['blocks']]
    facts = [{"source_id": block['block_id'], "text": block['text'], "status": "Source statement · unverified"}
             for block in parsed['blocks'] if block['text'] and block['type'] in ('paragraph', 'table', 'quote', 'list_item')]
    headings = [block for block in parsed['blocks'] if block['type'] == 'heading']
    structure = 38 if len(headings) < 2 else 76
    metadata = parsed['source_metadata']
    display_title = metadata.get('title') or next((block['text'] for block in headings if block['heading_level'] == 1), 'Untitled page')
    origin = source_origin(source)
    if source.example_id:
        if parsed['snapshot_id'] != source.example_id:
            # The example catalog must use the same exact payload + URL identity.
            raise HTTPException(503, "Example identity does not match the parsed snapshot.")
        parsed['raw_payload_reference'] = origin
    return {"mode": "mock", "snapshot_id": parsed['snapshot_id'], "source_origin": origin,
            "extraction": {"engine": "content-optimization-system", "upstream_revision": UPSTREAM['revision'], "package_version": UPSTREAM['package_version'], **parsed['selection']},
            "document": parsed, "chunks": chunks,
            "verification": verify_document(source.content, source.format, parsed, chunks, facts),
            "metadata": {"title": display_title, "description": metadata.get('description') or '',
                         "href": source.href, "hostname": source.hostname, "format": source.format},
            "sections": sections, "factoids": facts,
            "grades": [{"name": "Query alignment", "score": 58, "detail": "Mock: make the target question easier to locate."},
                       {"name": "Answer clarity", "score": 64, "detail": "Mock: lead with a concise, source-backed answer."},
                       {"name": "Structural integrity", "score": structure, "detail": "Demo heading-count heuristic; production grader not connected."}],
            "structure_recommended": structure < 50,
            "word_count": len(parsed['text'].split()),
            "notes": ["Extraction uses the pinned upstream retention-first parser.",
                      "Factoids are source statements, not independently verified facts.",
                      "Grading and rewriting remain mocked; no citation uplift is predicted."]}

@app.post('/api/evidence')
def evidence(source: EvidenceRequest):
    parsed, _ = extract_document(source.content, source.format, source.href, source.hostname)
    block = next((block for block in parsed['blocks'] if block['block_id'] == source.block_id), None)
    if block is None:
        raise HTTPException(404, 'Block not found in this source snapshot.')
    return {"snapshot_id": parsed['snapshot_id'], "block_id": block['block_id'],
            **SourceInspector(source.content, source.format).inspect(block, include_preview=True)}

@app.post('/api/draft')
def draft(source: DraftRequest):
    analysis = analyze(source)
    blocks = deepcopy(analysis['document']['blocks'])
    if not blocks:
        raise HTTPException(422, 'No retained source content is available for a draft.')
    title = source.query.strip().rstrip('?')
    if source.tone == 'More formal':
        title = 'A guide to: ' + title[0].lower() + title[1:]
    elif source.tone == 'More conversational':
        title = "Let’s explore: " + title[0].lower() + title[1:]
    changes = []
    replaced = False
    for block in blocks:
        text = block['text']
        if block['type'] == 'heading' and block['heading_level'] == 1 and not replaced:
            changes.append({"before": text, "after": title, "reason": "Align the page title with the target question.", "source_id": block['block_id']})
            block['text'] = title
            block.pop('inline_markdown', None)
            replaced = True
    markdown = blocks_to_markdown(blocks)
    if not replaced:
        markdown = '# ' + title + '\n\n' + markdown
        changes.append({"before": '(No page heading)', "after": title, "reason": "Proposed heading for the draft; review before applying.", "source_id": "metadata"})
    if source.allow_structure and analysis['structure_recommended']:
        heading, separator, body = markdown.partition('\n\n')
        markdown = heading + '\n\n## At a glance' + (separator + body if separator else '')
        changes.append({"before": '(No section heading)', "after": 'At a glance', "reason": "Optional grouping because the mock structural score is low.", "source_id": "structure"})
    return {"mode": "mock", "markdown": markdown, "changes": changes,
            "source_origin": analysis['source_origin'], "snapshot_id": analysis['snapshot_id'],
            "extraction": analysis['extraction'],
            "summary": "Deterministic preview: title and optional heading edits only. Body claims are retained verbatim. Connect the optimizer to generate substantive rewrites.",
            "preservation": ["Source statements retained", "No new product claims", "Original CSS and assets untouched"],
            "review_items": [*analysis['extraction']['quality_flags'], "Verify source claims before publication.", "This export is a Markdown content proposal, not a restyled or patched HTML page."]}
