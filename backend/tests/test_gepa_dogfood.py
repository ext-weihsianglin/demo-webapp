import importlib.util
from pathlib import Path
import pytest


spec = importlib.util.spec_from_file_location('dogfood', Path(__file__).parents[1]/'scripts/dogfood_gepa.py')
dogfood = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dogfood)


def test_paired_dogfood_keeps_failures_in_comparison_and_balances_call_order(tmp_path, monkeypatch):
    calls = []
    original = {'source_origin':{'split':'test'},'target_queries':['First?','Second?'],
                'p1':{'status':'scored','mean_score':.3,
                      'per_query':[{'query':'First?','score':.2},{'query':'Second?','score':.4}]}}
    def request(base, path, body):
        if path == 'analyze': return 200, original, 0
        calls.append(body['prompt_id'])
        if body['prompt_id'] == 'baseline':
            return 502, {'detail':{'status':'api_error'}}, 1
        return 200, {'status':'succeeded','fidelity':{'status':'passed'},
                     'telemetry':{'prompt_id':'candidate'},'target_queries':original['target_queries'],
                     'p1_after':{'status':'scored','mean_score':.35,
                                 'per_query':[{'query':'First?','score':.4},{'query':'Second?','score':.3}]}}, 1
    monkeypatch.setattr(dogfood, 'request', request)
    rows = dogfood.evaluate('local',{'snapshot_id':'page','hostname':'host'},
                           {'baseline_prompt_id':'baseline','model':'gpt-4.1-mini','repetitions':2},'candidate',tmp_path)
    assert calls == ['baseline','candidate','candidate','baseline']
    assert len(rows) == 4
    assert all(r['mean_p1'] == .3 and r['failed'] and r['retained_original'] for r in rows if r['kind']=='baseline')
    assert all(r['per_query'][1]['delta'] < 0 for r in rows if r['kind']=='candidate')


def test_dogfood_never_treats_missing_credentials_as_quality_evidence(tmp_path, monkeypatch):
    original = {'source_origin':{'split':'test'},'target_queries':['First?'],
                'p1':{'status':'scored','mean_score':.3,'per_query':[{'query':'First?','score':.3}]}}
    monkeypatch.setattr(dogfood,'request',lambda base,path,body:
                        (200,original,0) if path=='analyze' else (503,{'detail':{'status':'missing_credentials'}},0))
    with pytest.raises(ValueError,match='Unclassified failure'):
        dogfood.evaluate('local',{'snapshot_id':'page','hostname':'host'},
                         {'baseline_prompt_id':'baseline','model':'gpt-4.1-mini','repetitions':2},'candidate',tmp_path)
