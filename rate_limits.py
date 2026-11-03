"""SlowAPI limits for the single-process private beta; identities are server-authenticated."""
import ipaddress
import math
import time
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

def ip_key(request: Request) -> str:
    host = request.client.host if request.client else 'unknown'
    try:
        host = str(ipaddress.ip_address(host))
    except ValueError:
        pass
    return 'ip:' + host

def account_key(request: Request) -> str:
    user = getattr(request.state, 'user', None)
    return 'user:' + user['id'] if user else ip_key(request)
limiter = Limiter(key_func=ip_key, strategy='moving-window', headers_enabled=False)
generation_limit = limiter.shared_limit('5/minute', scope='generation', key_func=account_key)
grading_limit = limiter.shared_limit('10/minute', scope='grading', key_func=account_key)
index_limit = limiter.shared_limit('2/5minutes', scope='index-control', key_func=account_key)

def exceeded(request: Request, exc: RateLimitExceeded):
    window, arguments = request.state.view_rate_limit
    reset, _remaining = limiter.limiter.get_window_stats(window, *arguments)
    retry = max(1, math.ceil(reset - time.time()))
    return JSONResponse({'detail': f'Too many requests. Try again in {retry} seconds.'}, status_code=429, headers={'Retry-After': str(retry)})

def install(app):
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, exceeded)
