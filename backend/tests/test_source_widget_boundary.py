import pytest
from app.extraction import extract_document
from app.rewriting import editable


def parsed(source):
    return extract_document(source, 'html', 'https://example.com/guide', 'example.com')[0]


def test_translation_widget_is_retained_but_not_editable():
    doc = parsed('<main><p>Original editorial prose with enough detail to rewrite.</p></main>'
                 '<div id="goog-gt-tt"><div><div>Texte d\'origine</div>'
                 '<div>Évaluez cette traduction</div></div></div>')
    labels = [b for b in doc['blocks'] if b['text'] in ("Texte d'origine", 'Évaluez cette traduction')]
    assert len(labels) == 2
    assert all(not editable(b, doc) for b in labels)


@pytest.mark.parametrize('webform', [True, False])
def test_webforms_editorial_region_exception_does_not_open_regular_forms(webform):
    hidden = '<input type="hidden" name="__VIEWSTATE" value="test">' if webform else ''
    doc = parsed('<html><body><form>' + hidden + '<div id="main-content">'
        '<p>Original editorial prose with enough detail to rewrite.</p>'
        '<button><span>Subscribe now</span></button></div>'
        '<p>Enter your details to subscribe.</p></form></body></html>')
    body = next(b for b in doc['blocks'] if b['text'].startswith('Original editorial'))
    assert editable(body, doc) == webform
    assert all(not editable(b, doc) for b in doc['blocks'] if b is not body)
