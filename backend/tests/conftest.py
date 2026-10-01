import pytest

@pytest.fixture
def draft_stub(monkeypatch):
    from app import main
    from app.rewriting import rewrite
    from test_rewriting import StubClient
    monkeypatch.setattr(main, 'rewrite', lambda *args: rewrite(*args, client=StubClient()))
