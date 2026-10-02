"""Resolve semantic-role provenance without changing upstream content extraction."""
from bs4 import BeautifulSoup, Tag
from preprocessing.blocks import _dom_index, PRESERVE_WHITESPACE_TAGS

PROTECTED_ROLES = frozenset({'button', 'navigation', 'menu', 'menubar', 'banner',
    'contentinfo', 'link', 'checkbox', 'radio', 'switch', 'textbox', 'combobox',
    'listbox', 'option', 'slider', 'spinbutton', 'tab', 'tablist', 'searchbox', 'toolbar', 'form'})


def protected_roles(value):
    return tuple(role for role in str(value or '').lower().split() if role in PROTECTED_ROLES)


def html_role_context(content, blocks):
    # Match the pinned parser's source DOM and path recipe, not browser execution.
    source = BeautifulSoup(content, 'html.parser', preserve_whitespace_tags=PRESERVE_WHITESPACE_TAGS)
    paths, _ = _dom_index(source)
    contexts = {}
    pending = [(source, ())]
    while pending:
        node, inherited = pending.pop()
        own = protected_roles(node.attrs.get('role'))
        roles = tuple(dict.fromkeys(inherited + own))
        if roles:
            contexts[paths[id(node)]] = list(roles)
        pending.extend((child, roles) for child in node.contents if isinstance(child, Tag))
    return {block['block_id']:contexts[path] for block in blocks
            if (path := (block.get('source_locator') or {}).get('dom_path')) in contexts}
