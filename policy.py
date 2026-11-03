"""Policy Enforcement Point (PEP) for the Socratic tutor.

Every sensitive action is decided by the OPA server in policy/tutor.rego.  If OPA
is unreachable or returns an invalid response, the PEP fails closed: the answer
key and full solution stay hidden.
"""
from __future__ import annotations
from pathlib import Path
import logging
import os
import time
import asyncio
import weakref
from datetime import datetime, timezone
from typing import Any
import httpx
from dotenv import load_dotenv
from langsmith import traceable
logger = logging.getLogger(__name__)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _env_path in (Path(__file__).resolve().parent / '.env',):
    if os.path.isfile(_env_path):
        load_dotenv(_env_path, override=False)
OPA_URL = os.getenv('OPA_URL', 'http://127.0.0.1:8181').rstrip('/')
OPA_DECISION_PATH = os.getenv('OPA_DECISION_PATH', 'tutor/decision')
OPA_TIMEOUT_SECONDS = float(os.getenv('OPA_TIMEOUT_SECONDS', '3'))
_CLIENTS = weakref.WeakKeyDictionary()

def _http_client():
    loop = asyncio.get_running_loop()
    client = _CLIENTS.get(loop)
    if client is None or client.is_closed:
        token=os.getenv('OPA_BEARER_TOKEN','')
        client = httpx.AsyncClient(timeout=OPA_TIMEOUT_SECONDS, trust_env=False, transport=httpx.AsyncHTTPTransport(retries=1),headers={'Authorization':'Bearer '+token} if token else {})
        _CLIENTS[loop] = client
    return client

async def close_policy_client():
    client = _CLIENTS.pop(asyncio.get_running_loop(), None)
    if client is not None:
        await client.aclose()

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def denied(action: str, reason: str, *, engine: str='fail_closed') -> dict[str, Any]:
    return {'allow': False, 'action': action, 'reason': reason, 'engine': engine, 'decided_at': _now()}

@traceable(run_type='tool', name='opa_policy_decision')
async def decide(action: str, *, attempts: int, max_attempts: int, extra: dict[str, Any] | None=None) -> dict[str, Any]:
    """Ask OPA for a decision and fail closed on any error."""
    policy_input = {'action': action, 'attempts': attempts, 'max_attempts': max_attempts}
    if extra:
        policy_input.update(extra)
    url = f'{OPA_URL}/v1/data/{OPA_DECISION_PATH}'
    started = time.perf_counter()
    try:
        response = await _http_client().post(url, json={'input': policy_input})
        response.raise_for_status()
        payload = response.json()
        result = payload.get('result')
        if not isinstance(result, dict) or not isinstance(result.get('allow'), bool):
            raise ValueError('OPA returned no boolean decision')
        result = {'allow': result['allow'], 'action': action, 'reason': str(result.get('reason', 'no reason supplied')), 'engine': 'opa', 'decided_at': _now(), 'latency_ms': round((time.perf_counter() - started) * 1000, 1)}
        logger.info('OPA %s -> %s (%s ms): %s', action, 'ALLOW' if result['allow'] else 'DENY', result['latency_ms'], result['reason'])
        return result
    except Exception as exc:
        logger.warning('OPA unavailable for %s; failing closed: %s', action, exc)
        result = denied(action, f'OPA unavailable ({type(exc).__name__}); fail closed. {str(exc)[:180]}')
        result['latency_ms'] = round((time.perf_counter() - started) * 1000, 1)
        return result

async def opa_ready() -> bool:
    try:
        response = await _http_client().get(f'{OPA_URL}/health')
        return response.status_code == 200
    except Exception:
        return False
