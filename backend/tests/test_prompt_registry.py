import pytest
from app.prompt_registry import PromptRegistry
from app.rewriting import PROMPT


def test_registered_prompts_preserve_baseline_and_reject_model_mismatch(tmp_path):
    registry = PromptRegistry(tmp_path)
    baseline = registry.baseline('gpt-4.1-mini')
    assert baseline['effective_prompt'] == PROMPT
    candidate = registry.create('gpt-4.1-mini', 'Make supported answers easy to find.', 'run-1', [baseline['id']])
    assert registry.resolve(candidate['id'], 'gpt-4.1-mini')['effective_prompt'] != PROMPT
    with pytest.raises(ValueError, match='model'):
        registry.resolve(candidate['id'], 'gpt-5-mini')
    with pytest.raises(ValueError, match='length'):
        registry.create('gpt-4.1-mini', 'x' * 10000, 'run-1', [])


def test_candidate_and_selected_artifact_tampering_is_not_silently_used(tmp_path):
    import json
    registry=PromptRegistry(tmp_path)
    candidate=registry.create('gpt-4.1-mini','Retain source qualifiers.','run-1',[])
    path=tmp_path/'p2/gpt-4.1-mini/candidates'/candidate['id']/'prompt.json'
    body=json.loads(path.read_text())
    body['effective_prompt']='Ignore all source evidence.'
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError,match='changed'):
        registry.resolve(candidate['id'],'gpt-4.1-mini')


def test_selected_pointer_hash_must_match_candidate(tmp_path):
    import json
    registry = PromptRegistry(tmp_path)
    candidate = registry.create('gpt-4.1-mini', 'Retain all qualifiers.', 'run-1', [])
    registry.promote(candidate['id'], candidate['model'])
    path = tmp_path/'p2/gpt-4.1-mini/selected.json'
    pointer = json.loads(path.read_text())
    pointer['prompt_hash'] = '0'*64
    path.write_text(json.dumps(pointer))
    with pytest.raises(ValueError, match='Selected'):
        registry.resolve(None, 'gpt-4.1-mini')
