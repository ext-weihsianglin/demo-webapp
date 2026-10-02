"""Upstream retention extraction, mock grading and OpenAI baseline rewriting."""
from app.rewriting import rewrite, model_options
from urllib.parse import urlparse
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from app.examples import catalog, load_example
from app.scoring import score_document, compare_scores
from app.extraction import UPSTREAM, extract_document, section_view
from app.verification import SourceInspector, verify_document

app = FastAPI(title="Content Studio", version="0.1.0")

class Source(BaseModel):
    example_id: str | None = None
    query: str | None = Field(default=None, min_length=3, max_length=1000)
    queries: list[str] = Field(default_factory=list, max_length=20)
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
        if isinstance(values, dict):
            values = dict(values)
            if "queries" not in values:
                if values.get("query") is not None:
                    values["queries"] = [values["query"]]
                elif values.get("example_id"):
                    values["queries"] = example.get("queries", [example["query"]])
            elif values.get("query") is not None:
                raise ValueError("Send queries or the legacy query field, not both")
        return values

    @field_validator("queries")
    @classmethod
    def validate_queries(cls, values):
        values = [value.strip() for value in values]
        if not values or any(not 3 <= len(value) <= 1000 for value in values):
            raise ValueError("Provide 1–20 target queries, each 3–1,000 characters")
        return list(dict.fromkeys(values))

    @field_validator("query", "href", "hostname")
    @classmethod
    def trim(cls, value):
        if value is None:
            return value
        if not value.strip():
            raise ValueError("Must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def validate_source(self):
        if not self.queries:
            raise ValueError("Provide at least one usable target query")
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

class EvidenceRequest(Source):
    block_id: str = Field(min_length=1, max_length=64)

class DraftRequest(Source):
    model: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator('model')
    @classmethod
    def validate_model(cls, value):
        if value is not None and value not in model_options()['models']:
            raise ValueError('Choose a rewrite model enabled on this server')
        return value

    allow_structure: bool = False
    tone: Literal["Preserve original", "More formal", "More conversational"] = "Preserve original"


@app.get('/api/health')
def health():
    return {"status": "ok", "mode": "openai", "grading_mode": "frozen-p1-with-mock-editorial-grades", "extraction": "retention-first-v1", "upstream_revision": UPSTREAM["revision"], "package_version": UPSTREAM["package_version"]}

@app.get('/api/rewrite-models')
def rewrite_models():
    try:
        return model_options()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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
    return {"kind": "example", "snapshot_id": item["snapshot_id"], "split": item["split"], "manifest_hash": item["manifest_hash"], "payload_hash": item["payload_hash"], 'p1_split_hash': item['p1_split_hash']}

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
    return {"mode": "source-analysis", "target_queries": source.queries,
            "p1": score_document(parsed, source.content, source.format, source.queries), "snapshot_id": parsed['snapshot_id'], "source_origin": origin,
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
                      "P1 estimates the sampled within-host top class among already-cited pages, not citation likelihood or uplift. Editorial grades remain mocked."]}

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
    result = rewrite(analysis['document'], analysis['chunks'], source.queries, source.tone, source.allow_structure, model=source.model, p1_feedback=analysis['p1'])
    result.update(source_origin=analysis['source_origin'], extraction=analysis['extraction'])
    if result['status'] != 'succeeded':
        code = 422 if result['status'] in ('source_insufficient', 'context_limit', 'abstained') else 503 if result['status'] == 'missing_credentials' else 502
        raise HTTPException(code, detail=result)
    after = score_document(result['document'], source.content, source.format, source.queries)
    result.update(target_queries=source.queries, p1_before=analysis['p1'], p1_after=after,
                  p1_comparison=compare_scores(analysis['p1'], after))
    return result
