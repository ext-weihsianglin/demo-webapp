from app.experiment_names import slug, prompt_name, experiment_name
from app.prompt_registry import PromptRegistry


def test_readable_names_preserve_prompt_identity_and_promotion(tmp_path):
    registry = PromptRegistry(tmp_path)
    candidate = registry.create('gpt-5-mini', 'Preserve evidence and factual qualifiers.', 'old-run', [])
    registry.promote(candidate['id'], candidate['model'])
    catalog = registry.catalog(candidate['model'])
    entry = next(p for p in catalog['prompts'] if p['selected'])
    assert entry['display_name'].startswith('gpt-5-mini-preserve-evidence-factual-qualifiers-')
    assert catalog['selected_id'] == candidate['id']
    assert registry.resolve(candidate['id'],candidate['model'])['prompt_hash'] == candidate['prompt_hash']
    assert prompt_name(registry.baseline('gpt-5-mini')) == 'gpt-5-mini-baseline-v7'


def test_slugs_and_legacy_labels_are_safe_and_stable():
    assert slug('../../ Evidence first!') == 'evidence-first'
    assert slug('   ') == 'experiment'
    assert experiment_name('a'*32, {'model':'gpt-5-mini'}) == 'gpt-5-mini-fidelity-search-aaaaaaaa'
    assert experiment_name('evidence-first-20261002-abcd', {}) == 'evidence-first-20261002-abcd'
