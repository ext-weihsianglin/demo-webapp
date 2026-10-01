# GPT-5.6+ model support verification — 2026-10-01

Default dropdown adds `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-6-sol`, `gpt-6.1-sol`, `gpt-6-luna`, and `gpt-6-astra`. Existing GPT-4.1 choices/default remain. Official model docs list Responses and structured-output support. Stubbed endpoint tests verify selection, routing and telemetry for every choice.

Explicitly enabled credentialed smoke tests were attempted for all seven new models. All failed with `api_error` before any draft could be applied. A minimal diagnostic request to `gpt-5.6-sol` returned HTTP 403, `model_not_found`; the current account's model list contained none of the seven requested IDs. No credentials or raw provider error bodies were exposed. Live GPT-5.6+ rewriting is **not verified with the current credentials**. The earlier GPT-4.1-mini live baseline remains the measured baseline.

The orchestrator now presents `model_unavailable` for provider `model_not_found` errors so users can choose another model or configure credentials with model access. This does not substitute a fallback model. A stubbed denial test verifies the visible failure without exposing provider details.

Repeat after provisioning access:

```sh
RUN_OPENAI_LIVE=1 RUN_OPENAI_LIVE_MODELS=gpt-5.6-sol,gpt-5.6-terra,gpt-5.6-luna,gpt-6-sol,gpt-6.1-sol,gpt-6-luna,gpt-6-astra uv run pytest -q tests/test_live_rewriting.py
```

