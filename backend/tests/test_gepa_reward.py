import json
import pytest
from app.gepa.reward import components, policy
from app.gepa.runs import RunManager, RunConfig
from app.prompt_registry import PromptRegistry
from test_gepa_runs import ResearchClient, make_dataset, scorer, wait


def test_penalty_is_per_block_not_diluted_by_other_edits_and_keeps_rationale():
    findings=[{'block_id':'b1','verdict':'unsupported','category':'price','reason':'Invented a lower price.','source_ids':['b1']},
              {'block_id':'b2','verdict':'uncertain','category':'scope','reason':'Source scope unclear.','source_ids':[]}]
    changes=[{'source_id':'b1','review_flags':['unsupported_addition'],'evidence':[{'block_id':'b1'}]}]
    value=components(.6,findings,changes,policy())
    assert value['reward']==pytest.approx(.53) and value['fidelity_penalty']==pytest.approx(.07)
    assert value['unsupported_edits']==1 and value['uncertain_edits']==1
    assert value['factual_violations'][0]['reason']=='Invented a lower price.'
    extras=[{'source_id':f'b{i}','review_flags':[],'evidence':[]} for i in range(3,103)]
    assert components(.6,findings,changes+extras,policy())==value
    # Reward is deliberately unclipped so bad proposals retain a learning signal.
    assert components(.6,findings,changes,policy(1,1))['reward']==pytest.approx(-1.4)


@pytest.mark.parametrize('penalty',[.3,1.0])
def test_recommendation_uses_penalized_reward_and_preserves_raw_scores(tmp_path,monkeypatch,penalty):
    make_dataset(tmp_path,monkeypatch)
    class FidelityImproves(ResearchClient):
        def create(self, **request):
            response=super().create(**request)
            if request['text']['format']['name']=='fidelity':
                data=json.loads(request['input'][0]['content']);body=json.loads(response.output_text)
                for c in data['changes']:
                    verdict='supported' if 'choose a comfortable fit;' in c['after'] else 'unsupported'
                    body['edits'][c['source_id']].update(verdict=verdict,reason='Faithful change.' if verdict=='supported' else 'Unsupported certainty.')
                response.output_text=json.dumps(body)
            return response
    def measured(*args):
        value=scorer(*args)
        if value['mean_score']==.6:
            value['mean_score']=.35
            for q in value['per_query']:q['score']=.35
        return value
    registry=PromptRegistry(tmp_path/'registry')
    manager=RunManager(registry=registry,client=FidelityImproves(),scorer=measured,directory=tmp_path/'runs')
    final=wait(manager,manager.start(RunConfig(dataset_id='fixture',candidates=1,unsupported_penalty=penalty,enable_live_calls=True))['id'])
    assert final['recommendation']
    baseline=next(c for c in final['candidates'] if c['id'].endswith('--rewrite-page-v7'))
    winner=next(c for c in final['candidates'] if c['id']==final['recommendation'])
    assert baseline['selection_mean']==pytest.approx(.4) and baseline['selection_reward']==pytest.approx(.4-penalty)
    assert winner['selection_mean']==pytest.approx(.35) and winner['selection_reward']==pytest.approx(.35)
    assert winner['selection_penalty']==0 and winner['fidelity_violation_rate']==0
    assert registry.resolve(None,'gpt-4.1-mini')['id']==baseline['id']  # never auto-promote
    manifest=manager.store(final['id']).read('manifest')
    manifest.pop('reward_policy')
    manager.store(final['id']).write('manifest',manifest)
    assert not manager.status(final['id'])['promotion_compatible']
    with pytest.raises(ValueError,match='reward policy'):
        manager.promote(final['id'],winner['id'])
