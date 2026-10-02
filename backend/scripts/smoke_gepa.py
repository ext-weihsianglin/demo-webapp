"""Explicit, bounded provider check: one reflection-page rewrite and one mutation.

This is wiring evidence, not a selection evaluation or quality claim.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.gepa.adapter import Adapter
from app.gepa.datasets import load_dataset, root
from app.gepa.evaluation import AttemptBudget, PageEvaluator
from app.gepa.runs import RunConfig
from app.gepa.storage import RunStore
from app.prompt_registry import PromptRegistry, atomic_json
from app.rewriting import Settings


def smoke(dataset_id, output, page_index=0):
    if output.exists():
        raise ValueError('Choose a fresh output path')
    if not os.getenv('OPENAI_API_KEY') or os.getenv('P1_ENABLE_LIVE_EMBEDDINGS') != '1':
        raise ValueError('Configure credentials and explicitly enable embedding cache misses')
    data = load_dataset(dataset_id)
    pages = sorted((p for p in data['pages'] if p['role'] == 'reflection'), key=lambda p: len(p['content']))
    if not 0 <= page_index < len(pages):
        raise ValueError('Reflection page index must be 0–59')
    page = pages[page_index]
    registry = PromptRegistry()
    baseline = registry.baseline('gpt-4.1-mini')
    store = RunStore('smoke-' + uuid4().hex, root()/'smoke')
    budget = AttemptBudget(1)
    evaluator = PageEvaluator(budget, 1, record=lambda r: store.write('evaluation', r),
                              settings=Settings.from_env('gpt-4.1-mini'))
    config = RunConfig(dataset_id=dataset_id, candidates=1, enable_live_calls=True)
    adapter = Adapter(evaluator, registry, baseline, store, config)
    batch = adapter.evaluate([page], {'editorial_strategy': baseline['editorial_strategy']}, capture_traces=True)
    feedback = adapter.make_reflective_dataset({'editorial_strategy': baseline['editorial_strategy']}, batch, ['editorial_strategy'])
    candidate = adapter.propose_new_texts({'editorial_strategy': baseline['editorial_strategy']}, feedback, ['editorial_strategy'])
    result = batch.outputs[0]
    report = {'scope': 'one reflection page; no selection evaluation, promotion or quality conclusion',
              'dataset_id': dataset_id, 'dataset_hash': data['manifest_hash'], 'page_id': page['snapshot_id'],
              'p1_split': page['p1_split'], 'role': page['role'], 'query_count': len(page['queries']),
              'baseline_prompt_hash': baseline['prompt_hash'], 'mutation_prompt_hash': adapter.prompt(candidate)['prompt_hash'],
              'status': result['status'], 'budget': budget.snapshot(),
              'rewrite': result['rewrite']['telemetry'], 'fidelity': result.get('fidelity'),
              'p1': {k: result['original'].get(k) for k in ('status','feature_version','model_sha256','serving_policy','embedding')},
              'proposed_embedding': result.get('proposed_embedding'),
              'reflection': [e['usage'] for e in store.events() if e['phase'] == 'reflection'],
              'local_trace': str(store.path)}
    atomic_json(output, report)
    print(json.dumps({'report': str(output), 'status': result['status'], 'attempts': budget.attempts,
                      'reflection_calls': len(report['reflection'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--page-index', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required to enable provider calls')
    smoke(args.dataset, args.output, args.page_index)
