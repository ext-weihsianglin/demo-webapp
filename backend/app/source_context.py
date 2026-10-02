"""Resolve semantic-role provenance without changing upstream content extraction."""
import re
from bs4 import BeautifulSoup, Tag
from preprocessing.blocks import _dom_index, PRESERVE_WHITESPACE_TAGS

PROTECTED_ROLES = frozenset({'button', 'navigation', 'menu', 'menubar', 'banner',
    'contentinfo', 'link', 'checkbox', 'radio', 'switch', 'textbox', 'combobox',
    'listbox', 'option', 'slider', 'spinbutton', 'tab', 'tablist', 'searchbox', 'toolbar', 'form'})


NAVIGATION_TOKENS = frozenset({'nav', 'navbar', 'navigation', 'menu', 'submenu', 'menubar', 'subnav'})


def container_roles(attributes):
    classes = attributes.get('class') or []
    if isinstance(classes, str):
        classes = [classes]
    labels = ' '.join([str(attributes.get('id') or ''), *map(str, classes)])
    labels = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', labels).lower()
    tokens = set(re.findall(r'[a-z0-9]+', labels))
    roles = ('navigation',) if tokens & NAVIGATION_TOKENS else ()
    # Treat common footer names conservatively, without matching arbitrary
    # substrings such as "football" or "footwear".
    if 'footer' in tokens or ('foot' in tokens and tokens & {'main', 'site', 'page'}):
        roles += ('contentinfo',)
    return roles


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
        # Body/page classification classes are not navigation-container evidence.
        if node.name not in ('html', 'body', '[document]'):
            own += container_roles(node.attrs)
        roles = tuple(dict.fromkeys(inherited + own))
        if roles:
            contexts[paths[id(node)]] = list(roles)
        pending.extend((child, roles) for child in node.contents if isinstance(child, Tag))
    return {block['block_id']:contexts[path] for block in blocks
            if (path := (block.get('source_locator') or {}).get('dom_path')) in contexts}
