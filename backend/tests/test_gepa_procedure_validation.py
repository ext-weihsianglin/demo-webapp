import json
from types import SimpleNamespace as NS
import pytest
from app.gepa.adapter import Adapter
from app.gepa.evaluation import PageEvaluator, AttemptBudget
from app.gepa.storage import RunStore
from app.gepa.runs import RunConfig
from app.gepa.procedure_validation import validate_procedure, PROFILE
from app.prompt_registry import PromptRegistry


class SequenceClient:
    def __init__(self, texts):
        self.texts=iter(texts)
        self.responses=self
        self.requests=[]
    def create(self, **request):
        self.requests.append(request)
        text=next(self.texts)
        return NS(status='completed',output=[],usage=NS(input_tokens=10,output_tokens=10),
                  output_text=json.dumps({'editorial_strategy':text,'summary':'Clarify supported answers.'}))


def fixture(tmp_path, texts):
    client=SequenceClient(texts)
    registry=PromptRegistry(tmp_path/'registry')
    store=RunStore('procedure-test',tmp_path/'runs')
    adapter=Adapter(PageEvaluator(AttemptBudget(100),client=client),registry,registry.baseline('gpt-5-mini'),
                    store,RunConfig(dataset_id='fixture',model='gpt-5-mini',reflection_model='gpt-5-mini'))
    return adapter,client,store,registry


@pytest.mark.parametrize('bad',[
    'Plan useful edits and set',
    'Convert the rewritten paragraph into a numbered list.',
    'Return review_flags.uncovered_queries for missing evidence.',
    'Choose a faithful edit.\nStep 2: ',
    'x'*6000,
])
def test_invalid_procedure_is_repaired_once_before_registry(tmp_path,bad):
    good='Clarify supported answers. Preserve all factual qualifiers.'
    adapter,client,store,registry=fixture(tmp_path,[bad,good])
    seed={'editorial_strategy':registry.editorial}
    result=adapter.propose_new_texts(seed,{'editorial_strategy':[]},['editorial_strategy'])
    assert result['editorial_strategy']==good
    assert len(client.requests)==2 and adapter.proposals==1
    repair=json.loads(client.requests[1]['input'][0]['content'])
    assert json.loads(repair['repair']['invalid_response'])['editorial_strategy']==bad
    assert repair['repair']['validation_errors']
    assert store.read('reflection-output-1')['validation_errors']
    assert store.read('reflection-output-1-repair-1')['validation_errors']==[]
    assert json.loads(store.read('reflection-output-1')['output_text'])['editorial_strategy']==bad
    assert len(list((registry.root/'p2'/'gpt-5-mini'/'candidates').glob('*/prompt.json')))==1
    assert sum(e.get('usage',{}).get('calls',0) for e in store.events())==2
    assert registry.procedure_contract['procedure_validation']==PROFILE


def test_failed_repair_keeps_parent_and_logs_both_raw_responses(tmp_path):
    adapter,client,store,registry=fixture(tmp_path,['Unfinished and','Still unfinished or'])
    adapter.last_proposal='previous-candidate'
    seed={'editorial_strategy':registry.editorial}
    assert adapter.propose_new_texts(seed,{'editorial_strategy':[]},['editorial_strategy'])==seed
    assert len(client.requests)==2 and adapter.proposals==1 and adapter.last_proposal is None
    assert len(adapter.candidates)==1
    assert store.events()[-1]['reason']=='procedure_validation_failed'
    assert 'Still unfinished or' in store.read('reflection-output-1-repair-1')['output_text']


def test_repair_is_budgeted_with_complete_invalid_response(tmp_path):
    adapter,client,store,registry=fixture(tmp_path,['unclosed '*140000])
    seed={'editorial_strategy':registry.editorial}
    assert adapter.propose_new_texts(seed,{'editorial_strategy':[]},['editorial_strategy'])==seed
    assert len(client.requests)==1
    assert store.events()[-1]['reason']=='repair_context_limit'
    assert len(store.read('reflection-output-1')['output_text'])>1000000


def test_validator_allows_procedure_steps_and_explicit_prohibitions():
    body={'editorial_strategy':'1. Map supported queries.\n2. Do not create new blocks or Markdown lists.\n3. Preserve facts. Choose the smallest useful edit set.',
          'summary':'Use a compact grounded procedure.'}
    assert validate_procedure(body,6000)==[]
