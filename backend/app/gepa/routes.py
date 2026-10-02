"""HTTP validation only; coordinator and artifacts own research behavior."""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from app.prompt_registry import PromptRegistry
from app.rewriting import model_options
from app.gepa.datasets import list_datasets
from app.gepa.runs import RunManager, RunConfig
from app.gepa.storage import safe_id

router=APIRouter()
manager=RunManager()


def invoke(operation):
    try:
        return operation()
    except FileNotFoundError:
        raise HTTPException(404,'Research artifact not found') from None
    except (ValueError,KeyError,TypeError,OSError):
        raise HTTPException(400,'Research configuration or frozen artifact is invalid/unavailable') from None


@router.get('/api/prompts')
def prompts(model: str):
    if model not in model_options()['models']:
        raise HTTPException(400,'Choose a server-enabled model')
    return invoke(lambda:manager.registry.catalog(model))


@router.get('/api/gepa/datasets')
def datasets():
    return {'datasets':list_datasets()}


@router.get('/api/gepa/runs')
def runs():
    return invoke(lambda:{'runs':manager.list()})


@router.post('/api/gepa/runs',status_code=202)
def start(config: RunConfig):
    if manager.active:
        raise HTTPException(409,'A research run is already active')
    try:
        return manager.start(config)
    except ValueError as error:
        raise HTTPException(400,str(error)) from None
    except (OSError,KeyError,TypeError):
        raise HTTPException(400,'Frozen research data is unavailable or incompatible') from None


@router.get('/api/gepa/runs/{identity}')
def status(identity: str):
    return invoke(lambda:manager.status(identity))


@router.post('/api/gepa/runs/{identity}/stop')
def stop(identity: str):
    return invoke(lambda:manager.stop(identity))


@router.get('/api/gepa/runs/{identity}/events')
def events(identity: str,after: int=Query(default=0,ge=0)):
    return invoke(lambda:{'events':manager.store(identity).events(after)})


@router.get('/api/gepa/runs/{identity}/candidates/{candidate_id}')
def candidate(identity: str,candidate_id: str):
    def read():
        store=manager.store(identity)
        record=store.read('candidate-'+safe_id(candidate_id))
        evaluations=[store.read(p.stem) for p in store.path.glob('evaluation-'+safe_id(candidate_id)+'-*.json')]
        return {'candidate':record,'evaluations':evaluations}
    return invoke(read)


@router.get('/api/gepa/runs/{identity}/export')
def export(identity: str):
    def document():
        result=manager.store(identity).export()
        result['summary']=manager.status(identity)
        return JSONResponse(result,headers={'Content-Disposition':f'attachment; filename="gepa-{safe_id(identity)}.json"'})
    return invoke(document)


class SourceRejection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    reason: str=Field(min_length=1,max_length=2000)


@router.post('/api/gepa/runs/{identity}/candidates/{candidate_id}/reject')
def reject_candidate(identity: str,candidate_id: str,request: SourceRejection):
    return invoke(lambda:manager.reject_candidate(identity,candidate_id,request.reason))


class Promotion(BaseModel):
    run_id: str


@router.post('/api/prompts/{candidate_id}/promote')
def promote(candidate_id: str,request: Promotion):
    result=invoke(lambda:manager.promote(request.run_id,candidate_id))
    return {'id':result['id'],'model':result['model'],'prompt_hash':result['prompt_hash']}
