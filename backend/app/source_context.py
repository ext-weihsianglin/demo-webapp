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
    # Google Translate overlays are interface text, regardless of label language.
    if any(value.startswith(('goog-gt-', 'goog-te-'))
           for value in [str(attributes.get('id') or ''), *map(str, classes)]):
        roles += ('translation_widget',)
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
    contexts, nodes = {}, {}
    pending = [(source, ())]
    while pending:
        node, inherited = pending.pop()
        nodes[paths[id(node)]] = node
        own = protected_roles(node.attrs.get('role'))
        # Body/page classification classes are not navigation-container evidence.
        if node.name not in ('html', 'body', '[document]'):
            own += container_roles(node.attrs)
        roles = tuple(dict.fromkeys(inherited + own))
        if roles:
            contexts[paths[id(node)]] = list(roles)
        pending.extend((child, roles) for child in node.contents if isinstance(child, Tag))
    roles = {block['block_id']:contexts[path] for block in blocks
             if (path := (block.get('source_locator') or {}).get('dom_path')) in contexts}
    # ASP.NET Web Forms can wrap an entire page, including editorial content.
    # Exempt only an explicitly marked content region inside a body-level form
    # with a Web Forms hidden field. Controls and other protected roles still win.
    wrappers = {id(form) for form in source.find_all('form')
                if form.parent.name == 'body'
                and form.find('input', attrs={'type': 'hidden', 'name': '__VIEWSTATE'})}
    editorial_forms = {}
    for block in blocks:
        node = nodes.get((block.get('source_locator') or {}).get('dom_path'))
        if node is None:
            continue
        ancestors = [node, *node.parents]
        form = next((n for n in ancestors if n.name == 'form'), None)
        if form is None or id(form) not in wrappers:
            continue
        region = []
        for ancestor in ancestors:
            if ancestor is form:
                break
            region.append(ancestor)
        if any(n.name in ('main', 'article') or n.get('role') == 'main'
               or n.get('id') == 'main-content' for n in region):
            editorial_forms[block['block_id']] = paths[id(form)]
    return roles, editorial_forms
