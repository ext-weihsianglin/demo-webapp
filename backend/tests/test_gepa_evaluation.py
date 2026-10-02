from concurrent.futures import ThreadPoolExecutor
import pytest
from app.gepa.evaluation import AttemptBudget, RunStopped


def test_parallel_reservations_never_exceed_limit_and_free_cache_does_not_spend():
    budget = AttemptBudget(limit=100)
    def attempt(_):
        try:
            token = budget.reserve(1)[0]
            token.dispatch()
            budget.complete(False)
            return True
        except RunStopped:
            return False
    with ThreadPoolExecutor(max_workers=10) as pool:
        assert sum(pool.map(attempt, range(150))) == 100
    assert budget.snapshot()['attempts'] == 100


def test_full_selection_admission_does_not_start_partial_candidate():
    budget = AttemptBudget(limit=100)
    tokens = budget.reserve(80)
    for token in tokens:
        token.dispatch()
        budget.complete(False)
    with pytest.raises(RunStopped):
        budget.reserve(30)
    assert budget.snapshot()['attempts'] == 80


def test_circuit_breaker_and_valid_abstention_accounting():
    budget = AttemptBudget(limit=100)
    for _ in range(3):
        budget.reserve(1)[0].dispatch()
        budget.complete(True)
    assert budget.snapshot()['stop_reason'] == 'circuit_breaker'


def test_failure_rate_only_trips_after_minimum_completed_attempts():
    budget=AttemptBudget(limit=100,consecutive=10)
    for i in range(10):
        budget.reserve(1)[0].dispatch()
        budget.complete(i in (0,3,6))
        if i<9:
            assert budget.snapshot()['stop_reason'] is None
    assert budget.snapshot()['stop_reason']=='circuit_breaker'
