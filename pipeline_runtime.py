"""Bound provider calls, prioritize interactive work, and record stage timings."""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from functools import wraps
from contextvars import ContextVar
import heapq
import itertools
import logging
import os
import time
import weakref
logger = logging.getLogger(__name__)
BACKGROUND = ContextVar('pipeline_background', default=False)
_GATES = weakref.WeakKeyDictionary()
_OWNED = ContextVar('generation_slot_owned', default=None)
TRACE = ContextVar('generation_trace', default=None)

def mark_stage(stage):
    trace=TRACE.get()
    if trace is not None:trace['stage']=stage

LOCAL_CHECKS = ContextVar('generation_local_checks', default=None)
COMPLEX_TIMEOUT_SECONDS = float(os.getenv('GENERATION_COMPLEX_TIMEOUT_SECONDS','90'))

def set_generation_profile(difficulty,question_types):
    trace=TRACE.get()
    if trace and difficulty=='insane' and any(t in {'proof','long_answer'} for t in question_types or []):
        trace['timer'].reschedule(trace['started']+max(GENERATION_TIMEOUT_SECONDS,COMPLEX_TIMEOUT_SECONDS))

GENERATION_TIMEOUT_SECONDS = float(os.getenv('GENERATION_TIMEOUT_SECONDS', '60'))

def current_gate():
    loop = asyncio.get_running_loop()
    if loop not in _GATES:
        _GATES[loop] = ModelGate(max(1, int(os.getenv('MAX_CONCURRENT_LLM', '5'))))
    return _GATES[loop]

@asynccontextmanager
async def generation_slot():
    if _OWNED.get() is not None:
        yield
        return
    gate = current_gate()
    await gate.acquire()
    logger.info('pipeline generation_slot capacity=%s timeout_seconds=%s background=%s', gate.capacity, GENERATION_TIMEOUT_SECONDS, BACKGROUND.get())
    token = _OWNED.set(asyncio.Lock())
    checks_token = LOCAL_CHECKS.set({})
    trace={'stage':'retrieval'}
    trace_token=TRACE.set(trace)
    try:
        async with asyncio.timeout(GENERATION_TIMEOUT_SECONDS) as timer:
            trace.update(timer=timer,started=asyncio.get_running_loop().time())
            yield
    except BaseException as exc:
        if not getattr(exc,'pipeline_stage',None):exc.pipeline_stage=trace['stage']
        raise
    finally:
        TRACE.reset(trace_token)
        LOCAL_CHECKS.reset(checks_token)
        _OWNED.reset(token)
        gate.release()

def generation_process(function):

    @wraps(function)
    async def wrapped(*args, **kwargs):
        async with generation_slot():
            return await function(*args, **kwargs)
    return wrapped

class ModelGate:

    def __init__(self, capacity):
        self.capacity = capacity
        self.active = 0
        self.waiters = []
        self.sequence = itertools.count()

    def wake(self):
        while self.active < self.capacity and self.waiters:
            _, _, waiter = heapq.heappop(self.waiters)
            if waiter[0].done():
                continue
            self.active += 1
            waiter[1] = True
            waiter[0].set_result(None)

    async def acquire(self):
        future = asyncio.get_running_loop().create_future()
        waiter = [future, False]
        heapq.heappush(self.waiters, (int(BACKGROUND.get()), next(self.sequence), waiter))
        self.wake()
        try:
            await future
        except BaseException:
            future.cancel()
            if waiter[1]:
                self.release()
            raise

    def release(self):
        self.active -= 1
        self.wake()

@asynccontextmanager
async def model_slot(stage):
    owned = _OWNED.get()
    if owned is not None:
        async with owned:
            yield
        return
    gate = current_gate()
    started = time.perf_counter()
    await gate.acquire()
    acquired = time.perf_counter()
    try:
        yield
    finally:
        gate.release()
        logger.info('pipeline stage=%s queue_seconds=%.3f model_seconds=%.3f background=%s', stage, acquired - started, time.perf_counter() - acquired, BACKGROUND.get())
