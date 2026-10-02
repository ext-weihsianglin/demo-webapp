"""Budgeted page evaluation; original scores remain in the fixed denominator."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from openai import OpenAI
from app.extraction import extract_document
from app.fidelity import check_fidelity
from app.rewriting import rewrite
from app.scoring import score_document


class RunStopped(Exception):
    pass


class Reservation:
    def __init__(self, budget):
        self.budget, self.used, self.released = budget, False, False

    def dispatch(self):
        with self.budget.lock:
            self.budget.check()
            if self.used or self.released:
                raise ValueError('Attempt reservation reused')
            self.used = True
            self.budget.reserved -= 1
            self.budget.attempts += 1

    def release(self):
        with self.budget.lock:
            if not self.used and not self.released:
                self.released = True
                self.budget.reserved -= 1


class AttemptBudget:
    def __init__(self, limit, consecutive=3, rate=.2, minimum=10):
        self.limit, self.consecutive_limit, self.rate, self.minimum = limit, consecutive, rate, minimum
        self.lock = threading.RLock()
        self.attempts = self.reserved = self.completed = self.failures = self.consecutive = 0
        self.stop_reason = None

    def check(self):
        if self.stop_reason:
            raise RunStopped(self.stop_reason)

    def stop(self, reason='user_stop'):
        with self.lock:
            self.stop_reason = self.stop_reason or reason

    def reserve(self, count):
        with self.lock:
            self.check()
            if self.attempts + self.reserved + count > self.limit:
                self.stop('attempt_budget')
                raise RunStopped('attempt_budget')
            self.reserved += count
            return [Reservation(self) for _ in range(count)]

    def complete(self, technical_failure):
        with self.lock:
            self.completed += 1
            self.failures += int(technical_failure)
            self.consecutive = self.consecutive + 1 if technical_failure else 0
            if self.consecutive >= self.consecutive_limit or (self.completed >= self.minimum and self.failures/self.completed > self.rate):
                self.stop('circuit_breaker')

    def snapshot(self):
        with self.lock:
            return {'attempts': self.attempts, 'reserved': self.reserved, 'completed': self.completed,
                    'technical_failures': self.failures, 'stop_reason': self.stop_reason, 'limit': self.limit}


class GuardedClient:
    """Checks stop at the actual SDK boundary, and counts only dispatched P2 calls."""
    def __init__(self, client, budget, token=None):
        self.client, self.budget, self.token = client, budget, token
        self.responses = self

    def create(self, **kwargs):
        self.budget.check()
        if self.token:
            self.token.dispatch()
        return self.client.responses.create(**kwargs)


class PageEvaluator:
    def __init__(self, budget, workers=10, *, client=None, scorer=None, record=None, settings=None):
        self.budget, self.workers = budget, workers
        self.client = client
        self.settings = settings
        self.scorer = scorer
        self.record = record or (lambda result: None)
        self.cache, self.originals = {}, {}
        self.lock = threading.RLock()

    def _client(self):
        return self.client or OpenAI(timeout=120, max_retries=0)

    def _score(self, document, page, result, phase):
        if self.scorer:
            value = self.scorer(document,page['content'],page['format'],page['queries'])
            result[phase] = value.get('embedding')
        else:
            value = score_document(document,page['content'],page['format'],page['queries'],
                before_call=self.budget.check,on_embedding=lambda usage: result.update({phase:usage}))
        if value['status'] != 'scored':
            result['scoring_unavailable'] = {'phase':phase,**value}
        return value

    def evaluate(self, pages, prompt):
        missing = [p for p in pages if (prompt['prompt_hash'], p['snapshot_id']) not in self.cache]
        # Entire requested batch is admitted before starting any of its page calls.
        tokens = self.budget.reserve(len(missing))
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            jobs = {pool.submit(self._page, p, prompt, token): token for p, token in zip(missing,tokens)}
            error = None
            for job in as_completed(jobs):
                try:
                    result = job.result()
                    self.cache[(prompt['prompt_hash'],result['page_id'])] = result
                except Exception as exc:
                    error = error or exc
                    self.budget.stop('evaluation_unavailable' if not isinstance(exc,RunStopped) else str(exc))
            if error:
                raise error
        return [self.cache[(prompt['prompt_hash'], p['snapshot_id'])] for p in pages]

    def _page(self, page, prompt, token):
        result = {'page_id': page['snapshot_id'], 'hostname':page['hostname'], 'role':page['role'],
                  'candidate_id':prompt['id'], 'prompt_hash':prompt['prompt_hash'], 'queries':page['queries']}
        technical = False
        try:
            self.budget.check()
            document, chunks = extract_document(page['content'],page['format'],page['href'],page['hostname'])
            if document['snapshot_id'] != page['snapshot_id']:
                raise ValueError('Frozen snapshot changed')
            before = self.originals.get(page['snapshot_id'])
            if before is None:
                self.budget.check()
                before = self._score(document,page,result,'original_embedding')
                if before['status'] != 'scored':
                    raise ValueError('Original P1 unavailable')
                self.originals[page['snapshot_id']] = before
            result['original'] = before
            outcome = rewrite(document,chunks,page['queries'],'Preserve original',False,
                model=prompt['model'], prompt=prompt['effective_prompt'],prompt_id=prompt['id'],
                p1_feedback=before,settings=self.settings,client=GuardedClient(self._client(),self.budget,token))
            result.update(rewrite=outcome, original_document=document)
            after = before
            failure = outcome['status'] not in ('succeeded','abstained')
            technical = failure
            if outcome['status'] == 'succeeded':
                self.budget.check()
                gate = check_fidelity(document,outcome['changes'],client=GuardedClient(self._client(),self.budget))
                result['fidelity'] = gate
                failure = gate['status'] != 'passed'
                technical = gate['status'] == 'unavailable'
                if not failure:
                    self.budget.check()
                    after = self._score(outcome['document'],page,result,'proposed_embedding')
                    if after['status'] != 'scored':
                        raise ValueError('Proposed P1 unavailable')
            result.update(status='retained_original' if failure or outcome['status']=='abstained' else 'applied',
                          failed=failure, technical_failure=technical, after=after, score=after['mean_score'],
                          delta=after['mean_score']-before['mean_score'])
            return result
        except RunStopped:
            result.update(status='interrupted',failed=True)
            raise
        except Exception:
            result.update(status='unavailable',failed=True)
            technical = True
            raise
        finally:
            token.release()
            with self.budget.lock:
                if token.used:
                    self.budget.complete(technical)
                self.record(result)
