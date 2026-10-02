"""One in-process GEPA coordinator with persistent review artifacts."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import importlib.metadata
import os
import threading

from gepa import optimize
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.prompt_registry import PromptRegistry
from app.rewriting import model_options, Settings
from app.fidelity import PROMPT as GATE_PROMPT, MODEL as GATE_MODEL, SCHEMA_VERSION, OUTPUT_BUDGET
from app.prompt_registry import digest
from app.gepa.datasets import load_dataset, root
from app.gepa.storage import RunStore, safe_id
from app.gepa.evaluation import AttemptBudget, PageEvaluator, RunStopped
from app.gepa.adapter import Adapter, Callbacks, REFLECTION_PROMPT

TERMINAL={'completed','stopped','failed','interrupted'}


class RunConfig(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    dataset_id: str
    model: str='gpt-4.1-mini'
    reflection_model: str='gpt-4.1-mini'
    prompt_id: str | None=None
    candidates: int=Field(default=10,ge=1,le=50)
    reflection_batch: int=Field(default=2,ge=1,le=20)
    attempts: int=Field(default=100,ge=30,le=2000)
    concurrency: int=Field(default=10,ge=1,le=20)
    length_multiplier: float=Field(default=1.5,ge=1,le=3)
    consecutive_failures: int=Field(default=3,ge=1,le=20)
    failure_rate: float=Field(default=.2,gt=0,le=1)
    failure_minimum: int=Field(default=10,ge=1,le=100)
    seed: int=Field(default=0,ge=0,le=2147483647)
    enable_live_calls: bool=False

    @model_validator(mode='after')
    def supported(self):
        models=model_options()['models']
        if self.model not in models or self.reflection_model not in models:
            raise ValueError('Choose server-enabled models')
        safe_id(self.dataset_id)
        return self


class RunManager:
    def __init__(self, *, registry=None, client=None, scorer=None, directory=None):
        self._registry=registry
        self.client,self.scorer,self.directory=client,scorer,directory
        self.lock=threading.RLock()
        self.active=None
        self.contexts={}

    @property
    def registry(self):
        with self.lock:
            if self._registry is None:
                self._registry=PromptRegistry()
            return self._registry

    def store(self, identity):
        return RunStore(identity,self.directory)

    def start(self, config):
        if not config.enable_live_calls:
            raise ValueError('Explicitly enable live research calls before Start')
        if self.client is None and not os.getenv('OPENAI_API_KEY'):
            raise ValueError('Backend OPENAI_API_KEY unavailable')
        data=load_dataset(config.dataset_id)
        baseline=self.registry.resolve(config.prompt_id or self.registry.baseline(config.model)['id'],config.model)
        settings=Settings.from_env(config.model)
        with self.lock:
            if self.active:
                raise ValueError('A research run is already active')
            identity=uuid4().hex
            store=self.store(identity)
            budget=AttemptBudget(config.attempts,config.consecutive_failures,config.failure_rate,config.failure_minimum)
            context={'budget':budget,'config':config,'dataset':data,'baseline':baseline,'store':store,'settings':settings}
            self.contexts[identity]=context
            self.active=identity
            manifest={'run_id':identity,'config':config.model_dump(),'dataset':{k:v for k,v in data.items() if k!='pages'},
                'page_roles':[{k:p[k] for k in ('snapshot_id','role','query_set_hash')} for p in data['pages']],
                'baseline':baseline,'rewrite_settings':settings.__dict__,
                'fidelity':{'model':GATE_MODEL,'prompt_hash':digest(GATE_PROMPT),'schema_version':SCHEMA_VERSION,
                            'output_budget':OUTPUT_BUDGET,'uncertain_policy':'reject_whole_proposal'},
                'reflection_prompt_hash':digest(REFLECTION_PROMPT),'gepa_version':importlib.metadata.version('gepa'),
                'cache_scope':'per_run','merge_enabled':False,'created_at':datetime.now(timezone.utc).isoformat()}
            store.write('manifest',manifest)
            store.write('summary',{'id':identity,'status':'preflighting','config':config.model_dump(),
                'budget':budget.snapshot(),'candidates':[],'recommendation':None,'stop_reason':None})
            thread=threading.Thread(target=self._execute,args=(identity,),daemon=True,name='gepa-'+identity[:8])
            thread.start()
            return self.status(identity)

    def _execute(self, identity):
        context=self.contexts[identity]
        store,budget,config=context['store'],context['budget'],context['config']
        adapter=None
        status='completed'
        reason=None
        try:
            def record(result):
                store.write('evaluation-'+result['candidate_id']+'-'+result['page_id'],result)
                store.event('page_evaluated',page_id=result['page_id'],candidate_id=result['candidate_id'],
                            role=result['role'],status=result['status'],score=result.get('score'),delta=result.get('delta'),
                            budget=budget.snapshot(), usage_by_phase={
                                'rewrite':result.get('rewrite',{}).get('telemetry',{}),
                                'fidelity':result.get('fidelity',{}).get('telemetry',{}),
                                'embedding':{key:sum((result.get(phase) or {}).get(key,0) for phase in ('original_embedding','proposed_embedding'))
                                    for key in ('calls','input_tokens','cached_requests')}})
            evaluator=PageEvaluator(budget,config.concurrency,client=self.client,scorer=self.scorer,record=record,settings=context['settings'])
            adapter=Adapter(evaluator,self.registry,context['baseline'],store,config)
            context['adapter']=adapter
            summary=store.read('summary')
            summary['status']='running'
            store.write('summary',summary)
            store.event('started')
            train=[p for p in context['dataset']['pages'] if p['role']=='reflection']
            val=[p for p in context['dataset']['pages'] if p['role']=='selection']
            # The harness owns actual attempt accounting. GEPA uses the same
            # recorded page rewards and its genuine Pareto/mutation engine.
            optimize(seed_candidate={'editorial_strategy':context['baseline']['editorial_strategy']},
                trainset=train,valset=val,adapter=adapter,reflection_minibatch_size=config.reflection_batch,
                skip_perfect_score=False,candidate_selection_strategy='pareto',frontier_type='instance',
                use_merge=False,stop_callbacks=[lambda state: bool(budget.stop_reason) or adapter.proposals>=config.candidates or state.i>=config.candidates],
                callbacks=[Callbacks(adapter)],cache_evaluation=False,seed=config.seed,raise_on_exception=True,
                run_dir=None,logger=RunLogger(store))
            reason=budget.stop_reason or ('proposal_limit' if adapter.proposals>=config.candidates else 'completed')
            status='stopped' if budget.stop_reason else 'completed'
        except RunStopped as error:
            status,reason='stopped',str(error)
        except Exception as error:
            # Exception bodies may contain credential/provider/source content.
            status,reason='failed',budget.stop_reason or 'fatal_'+type(error).__name__
            store.event('failed',reason=reason)
        finally:
            candidates=adapter.snapshot() if adapter else []
            baseline=adapter.full_scores.get(context['baseline']['id']) if adapter else None
            eligible=[c for c in candidates if c.get('selection_pages')==30 and baseline and
                      c.get('selection_mean',-1)>baseline['selection_mean'] and c['failure_rate']<=baseline['failure_rate']]
            recommendation=max(eligible,key=lambda c:c['selection_mean'])['id'] if eligible else None
            store.write('summary',{'id':identity,'status':status,'config':config.model_dump(),
                'budget':budget.snapshot(),'candidates':candidates,'recommendation':recommendation,'stop_reason':reason,
                'proposals':adapter.proposals if adapter else 0,'finished_at':datetime.now(timezone.utc).isoformat()})
            store.event('finished',status=status,reason=reason,recommendation=recommendation)
            with self.lock:
                self.active=None
                self.contexts.pop(identity,None)

    def status(self, identity):
        store=self.store(identity)
        summary=store.read('summary')
        usage={phase:{'calls':0,'input_tokens':0,'output_tokens':0,'cached_requests':0} for phase in ('rewrite','fidelity','reflection','embedding')}
        events=store.events()
        for event in events:
            for phase, values in event.get('usage_by_phase',{}).items():
                for key in usage[phase]:
                    usage[phase][key]+=values.get(key,0)
            if event['phase']=='reflection':
                for key in usage['reflection']:
                    usage['reflection'][key]+=event.get('usage',{}).get(key,0)
        summary['usage']=usage
        with self.lock:
            context=self.contexts.get(identity)
            if context:
                summary['budget']=context['budget'].snapshot()
                adapter=context.get('adapter')
                if adapter:
                    summary['candidates']=adapter.snapshot()
                    summary['proposals']=adapter.proposals
            elif summary['status'] not in TERMINAL or summary['status']=='interrupted':
                last_budget=next((event['budget'] for event in reversed(events) if 'budget' in event),summary['budget'])
                summary.update(status='interrupted',stop_reason='server_restart',recommendation=None,
                    budget={**last_budget,'reserved':0,'stop_reason':'server_restart'},
                    candidates=[store.read(path.stem) for path in sorted(store.path.glob('candidate-*.json'))])
                store.write('summary',summary)
        return summary

    def stop(self, identity):
        with self.lock:
            context=self.contexts.get(identity)
            if context:
                context['budget'].stop()
                summary=context['store'].read('summary')
                summary['status']='stopping'
                context['store'].write('summary',summary)
        return self.status(identity)

    def shutdown(self):
        with self.lock:
            for context in self.contexts.values():
                context['budget'].stop('server_shutdown')

    def list(self):
        directory=Path(self.directory or root()/'runs')
        return [self.status(p.parent.name) for p in sorted(directory.glob('*/summary.json'),reverse=True)]

    def promote(self, identity, candidate_id):
        summary=self.status(identity)
        if summary['status'] not in ('completed','stopped') or summary['recommendation']!=candidate_id:
            raise ValueError('Only a complete recommended candidate can be promoted')
        return self.registry.promote(candidate_id,summary['config']['model'])


class RunLogger:
    def __init__(self, store):
        self.store=store
    def log(self, message):
        self.store.event('engine',message=message)
