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


def test_candidate_and_promoted_default_survive_a_fresh_registry_process(tmp_path):
    import json, subprocess, sys
    registry = PromptRegistry(tmp_path)
    candidate = registry.create('gpt-4.1-mini', 'Clarify only source-supported answers.', 'run-1', [])
    registry.promote(candidate['id'], candidate['model'])
    code = "from app.prompt_registry import PromptRegistry; import json,sys; r=PromptRegistry(sys.argv[1]); print(json.dumps(r.resolve(None,'gpt-4.1-mini')))"
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path)], cwd=__import__('pathlib').Path(__file__).resolve().parents[1], check=True, text=True, capture_output=True)
    restored = json.loads(result.stdout)
    assert restored['id'] == candidate['id']
    assert restored['effective_prompt'] == candidate['effective_prompt']
    assert restored['prompt_hash'] == candidate['prompt_hash']


def test_procedure_contract_supports_long_instructions_without_changing_fixed_guards(tmp_path):
    registry = PromptRegistry(tmp_path)
    baseline = registry.baseline('gpt-4.1-mini')
    legacy = registry.create('gpt-4.1-mini', 'Clarify supported answers.', 'old', [])
    procedure = '\n'.join(f'{i}. Map each query intent to existing evidence; preserve qualifiers.' for i in range(15))
    context = {'rationale':'Map every intent to source evidence before editing.',
        'reflection_model':'gpt-5-mini','reflection_instruction_hash':'a'*64,
        'reflection_trace':{'run_id':'new','artifact':'reflection-input-1'}}
    candidate = registry.create('gpt-4.1-mini', procedure, 'new', [baseline['id']], character_limit=6000,
        optimization_context=context)
    assert candidate['characters'] > 501
    assert candidate['component_contract'] == 'query-procedure-v1'
    assert candidate['contract_hash'] == baseline['contract_hash']
    assert candidate['effective_prompt'] == procedure + '\n\n' + registry.fixed
    registry.promote(candidate['id'], candidate['model'])
    restored = PromptRegistry(tmp_path).resolve(None, candidate['model'])
    assert restored == candidate
    assert restored['optimization_context'] == context
    assert registry.resolve(legacy['id'], legacy['model']) == legacy
    with pytest.raises(ValueError, match='length'):
        registry.create('gpt-4.1-mini', 'x' * 6001, 'new', [], character_limit=6000)
