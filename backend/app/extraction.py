"""Invoke the pinned upstream Markdownify corpus parser for submitted snapshots."""
from importlib.metadata import version
from preprocessing.api import PARSER_REVISION, parse_snapshot
from app.source_context import html_role_context

UPSTREAM = {"repository": "https://github.com/ext-weihsianglin/content-optimization-system",
            "revision": PARSER_REVISION, "package_version": version("content-optimization-exploration"),
            "serializer": "markdownify-structured-v1"}


def extract_document(content, format, href, hostname):
    document, chunks = parse_snapshot(content, href, hostname, source_format=format)
    if document['source']['format'] == 'html':
        roles, editorial_forms = html_role_context(content, document['blocks'])
        if roles:
            document['source_role_context'] = roles
        if editorial_forms:
            document['source_editorial_form_context'] = editorial_forms
    return document, chunks


def section_view(block):
    kind = {"heading": f"h{block['heading_level']}", "paragraph": "p", "list": "ol" if block.get("ordered") else "ul",
            "list_item": "li", "code": "pre", "quote": "blockquote", "table": "table", "image": "img",
            "definition_list": "dl", "definition_term": "dt", "definition_description": "dd",
            "thematic_break": "hr"}[block["type"]]
    return {"id": block["block_id"], "kind": kind, "text": block["text"]}
