import pytest

@pytest.fixture
def draft_stub(monkeypatch):
    from app import main
    from app.rewriting import rewrite
    from test_rewriting import StubClient
    monkeypatch.setattr(main, 'rewrite', lambda *args, **kwargs: rewrite(*args, client=StubClient(), **kwargs))

    # Mock the external judge SDK as well; ordinary tests never call providers.
    from app import fidelity
    from test_gepa_runs import ResearchClient
    monkeypatch.setenv('OPENAI_API_KEY','stub-key')
    monkeypatch.setattr(fidelity,'OpenAI',lambda **kwargs: ResearchClient())
