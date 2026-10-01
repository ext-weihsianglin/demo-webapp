"""Invoke the pinned upstream retention parser for any submitted snapshot."""
from importlib.metadata import version
from preprocessing.api import PARSER_REVISION, parse_snapshot

UPSTREAM = {"repository": "https://github.com/ext-weihsianglin/content-optimization-system",
            "revision": PARSER_REVISION, "package_version": version("content-optimization-exploration")}


def extract_document(content, format, href, hostname):
    return parse_snapshot(content, href, hostname, source_format=format)


def section_view(block):
    kind = {"heading": f"h{block['heading_level']}", "paragraph": "p", "list": "ol" if block.get("ordered") else "ul",
            "list_item": "li", "code": "pre", "quote": "blockquote", "table": "table", "image": "img"}[block["type"]]
    return {"id": block["block_id"], "kind": kind, "text": block["text"]}
