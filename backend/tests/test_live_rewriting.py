"""Opt-in credentialed smoke: RUN_OPENAI_LIVE=1 uv run pytest tests/test_live_rewriting.py."""
import os
import pytest
from app.extraction import extract_document
from app.rewriting import rewrite

@pytest.mark.skipif(os.getenv('RUN_OPENAI_LIVE') != '1', reason='Explicit RUN_OPENAI_LIVE=1 required')
def test_configured_model_live_smoke():
    if not os.getenv('OPENAI_API_KEY'):
        pytest.fail('OPENAI_API_KEY unavailable on server')
    content='<main><h1>Road shoes</h1><p>The best shoe depends on fit, cushioning and running surface.</p><p>For everyday road runs, choose comfortable fit and natural cushioning. For trails, prioritize terrain grip. No single shoe is best for every runner.</p></main>'
    p,c=extract_document(content,'html','https://example.com/shoes','example.com')
    result=rewrite(p,c,'How should I choose shoes for road runs?', 'More conversational', False)
    assert result['status']=='succeeded', result['summary']
    assert result['changes'] and result['telemetry']['input_tokens'] > 0
