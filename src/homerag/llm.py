"""Access to the Anthropic API (placeholder, Phase 3).

The single place that imports `anthropic`: model calls with retries, an on-disk response cache
and cost logging. Everything else receives an LLM object as a parameter, so tests pass a fake.
"""
