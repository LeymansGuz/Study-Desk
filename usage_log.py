"""Per-request actual LLM token accounting.

The user id is carried in a context variable from the authenticated request into
the LangChain call. Every structured model call records the provider's usage
object, not a heuristic estimate.
"""
from __future__ import annotations
import logging
from contextvars import ContextVar
from typing import Any
import db
logger = logging.getLogger(__name__)
CURRENT_USER_ID: ContextVar[str | None] = ContextVar('current_user_id', default=None)

def set_current_user(user_id: str | None) -> None:
    CURRENT_USER_ID.set(user_id)

def current_user_id() -> str | None:
    return CURRENT_USER_ID.get()

def _usage_numbers(response: Any) -> tuple[int, int]:
    usage = getattr(response, 'usage_metadata', None) or {}
    if not usage:
        metadata = getattr(response, 'response_metadata', None) or {}
        usage = metadata.get('token_usage') or metadata.get('usage') or {}
    if not isinstance(usage, dict):
        return (0, 0)
    input_tokens = usage.get('input_tokens') or usage.get('prompt_tokens') or usage.get('input_token_count') or 0
    output_tokens = usage.get('output_tokens') or usage.get('completion_tokens') or usage.get('output_token_count') or 0
    try:
        input_tokens = int(input_tokens or 0)
        output_tokens = int(output_tokens or 0)
    except (TypeError, ValueError):
        return (0, 0)
    return (max(0, input_tokens), max(0, output_tokens))

def record_response_usage(response: Any, stage: str='', latency_ms: float=0) -> str | None:
    """Persist the provider's token usage for the signed-in request, if any."""
    user_id = current_user_id()
    if not user_id:
        return
    input_tokens, output_tokens = _usage_numbers(response)
    try:
        import observability
        raw = getattr(response, 'response_metadata', {}) or {}
        usage = raw.get('token_usage') or raw.get('usage') or {}
        details = (getattr(response, 'usage_metadata', {}) or {}).get('input_token_details') or {}
        cached = int(usage.get('prompt_cache_hit_tokens', details.get('cache_read', 0)) or 0)
        identifier, cost = observability.provider_call(user_id, stage, str(raw.get('model_name', raw.get('model', 'configured model'))), input_tokens, output_tokens, min(input_tokens, cached), latency_ms, bool(input_tokens or output_tokens))
        return identifier
    except Exception:
        logger.exception('Could not record token usage for user %s', user_id[:8])
