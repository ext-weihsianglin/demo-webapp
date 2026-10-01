"""Mock workflow adapters. No remote fetching or LLM calls."""
import hashlib
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator, model_validator

app = FastAPI(title="Content Studio", version="0.1.0")

class Source(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    href: str = Field(max_length=2048)
    hostname: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=20, max_length=200000)
    format: str = "html"

    @field_validator("query", "href", "hostname", "content")
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
        if self.format not in ("html", "markdown"):
            raise ValueError("Choose HTML or Markdown")
        if len(self.content.strip()) < 20:
            raise ValueError("Add at least 20 characters of source content")
        return self

class DraftRequest(Source):
    allow_structure: bool = False
    tone: str = "Preserve original"


def extract(content: str, format: str):
    # Deliberately independent of the query and citation labels.
    metadata = {}
    sections = []
    if format == "html":
        soup = BeautifulSoup(content, "html.parser")
        metadata = {"title": soup.title.get_text(' ', strip=True) if soup.title else "Untitled page",
                    "description": next((m.get('content', '') for m in soup.find_all('meta') if m.get('name') == 'description'), '')}
        for el in soup.select('script, style, nav, footer, header, noscript'):
            el.decompose()
        body = soup.find('main') or soup.find('article') or soup
        for el in body.find_all(['h1', 'h2', 'h3', 'p', 'li', 'table']):
            if el.find_parent(['li', 'table']):
                continue
            text = el.get_text(' ', strip=True)
            if text:
                sections.append({"id": f"block-{len(sections)+1}", "kind": el.name, "text": text})
        if not sections and body.get_text(' ', strip=True):
            sections = [{"id": "block-1", "kind": "p", "text": body.get_text(' ', strip=True)}]
    else:
        for line in content.splitlines():
            if line.strip():
                heading = re.match(r'^(#{1,3})\s+', line)
                sections.append({"id": f"block-{len(sections)+1}", "kind": f'h{len(heading[1])}' if heading else 'p', "text": re.sub(r'^#{1,6}\s+', '', line).strip()})
        metadata['title'] = next((s['text'] for s in sections if s['kind'] == 'h1'), 'Untitled page')
    facts = [{"source_id": s['id'], "text": s['text'], "status": "Source statement · unverified"} for s in sections if s['kind'] in ('p', 'li', 'table')]
    return metadata, sections, facts

@app.get('/api/health')
def health():
    return {"status": "ok", "mode": "mock"}

@app.post('/api/analyze')
def analyze(source: Source):
    metadata, sections, facts = extract(source.content, source.format)
    headings = [s for s in sections if s['kind'].startswith('h')]
    structure = 38 if len(headings) < 2 else 76
    return {"mode": "mock", "snapshot_id": hashlib.sha256((source.href + source.content).encode()).hexdigest()[:16],
            "metadata": {**metadata, "href": source.href, "hostname": source.hostname, "format": source.format},
            "sections": sections, "factoids": facts,
            "grades": [{"name": "Query alignment", "score": 58, "detail": "Mock: make the target question easier to locate."},
                       {"name": "Answer clarity", "score": 64, "detail": "Mock: lead with a concise, source-backed answer."},
                       {"name": "Structural integrity", "score": structure, "detail": "Demo heading-count heuristic; production grader not connected."}],
            "structure_recommended": structure < 50,
            "word_count": len(' '.join(s['text'] for s in sections).split()),
            "notes": ["Extraction uses a lightweight local adapter, not the phase 1 ensemble.", "Factoids are source statements, not independently verified facts.", "Scores are illustrative; no citation uplift is predicted."]}

@app.post('/api/draft')
def draft(source: DraftRequest):
    analysis = analyze(source)
    blocks = analysis['sections']
    title = source.query.strip().rstrip('?')
    if source.tone == 'More formal':
        title = 'A guide to: ' + title[0].lower() + title[1:]
    elif source.tone == 'More conversational':
        title = "Let’s explore: " + title[0].lower() + title[1:]
    rendered = []
    changes = []
    replaced = False
    for block in blocks:
        text = block['text']
        kind = block['kind']
        if kind == 'h1' and not replaced:
            changes.append({"before": text, "after": title, "reason": "Align the page title with the target question.", "source_id": block['id']})
            text = title
            replaced = True
        rendered.append(('#' * int(kind[1]) + ' ' if kind.startswith('h') else '- ' if kind == 'li' else '') + text)
    if not replaced:
        rendered.insert(0, '# ' + title)
        changes.append({"before": '(No page heading)', "after": title, "reason": "Proposed heading for the draft; review before applying.", "source_id": "metadata"})
    if source.allow_structure and analysis['structure_recommended']:
        rendered.insert(1, '## At a glance')
        changes.append({"before": '(No section heading)', "after": 'At a glance', "reason": "Optional grouping because the mock structural score is low.", "source_id": "structure"})
    return {"mode": "mock", "markdown": '\n\n'.join(rendered), "changes": changes,
            "summary": "Deterministic preview: title and optional heading edits only. Body claims are retained verbatim. Connect the optimizer to generate substantive rewrites.",
            "preservation": ["Source statements retained", "No new product claims", "Original CSS and assets untouched"],
            "review_items": ["Verify source claims before publication.", "This export is a Markdown content proposal, not a restyled or patched HTML page."]}
