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
    if trace is not None:
        now=time.perf_counter()
        if trace.get('stage_started') is not None:
            name=trace.get('stage','retrieval')
            trace.setdefault('stage_ms',{})[name]=trace.setdefault('stage_ms',{}).get(name,0)+(now-trace['stage_started'])*1000
        trace['stage_started']=now;trace['stage']=stage
        if not trace.get('root_id'):
            import observability
            current=observability.CURRENT.get() or {}
            trace.update(root_id=current.get('root_id',''),session_id=current.get('session_id',''))

LOCAL_CHECKS = ContextVar('generation_local_checks', default=None)
COMPLEX_TIMEOUT_SECONDS = float(os.getenv('GENERATION_COMPLEX_TIMEOUT_SECONDS','90'))

def set_generation_profile(difficulty,question_types):
    trace=TRACE.get()
    if trace and difficulty in {'hard','insane'} and any(t in {'proof','long_answer'} for t in question_types or []):
        trace['timer'].reschedule(trace['started']+max(GENERATION_TIMEOUT_SECONDS,COMPLEX_TIMEOUT_SECONDS))

def set_tutor_profile(*, extended=False):
    """Give a deep explanation or supplied extended task the existing complex budget."""
    trace=TRACE.get()
    if trace and extended:
        trace['timer'].reschedule(trace['started']+max(GENERATION_TIMEOUT_SECONDS,COMPLEX_TIMEOUT_SECONDS))


def set_repair_profile():
    """One bounded grace period finishes a feedback-guided candidate repair."""
    trace=TRACE.get()
    if trace and not trace.get('repair_grace_used'):
        trace['repair_grace_used']=True
        deadline=trace['started']+GENERATION_TIMEOUT_SECONDS+min(30,max(0,float(os.getenv('GENERATION_REPAIR_GRACE_SECONDS','15'))))
        trace['timer'].reschedule(max(trace['timer'].when(),deadline))


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
    queued=time.perf_counter()
    await gate.acquire()
    logger.info('pipeline generation_slot capacity=%s timeout_seconds=%s background=%s', gate.capacity, GENERATION_TIMEOUT_SECONDS, BACKGROUND.get())
    token = _OWNED.set(asyncio.Lock())
    checks_token = LOCAL_CHECKS.set({})
    trace={'stage':'retrieval'}
    trace_token=TRACE.set(trace)
    import providers
    connection_token=providers.ACTIVE.set(providers.ACTIVE.get() or providers.snapshot())
    outcome='success'
    try:
        async with providers.workflow_slot():
            async with asyncio.timeout(GENERATION_TIMEOUT_SECONDS) as timer:
                trace.update(timer=timer,started=asyncio.get_running_loop().time())
                trace.update(work_started=time.perf_counter(),queue_ms=(time.perf_counter()-queued)*1000,stage_started=time.perf_counter())
                yield
    except BaseException as exc:
        outcome='error'
        if not getattr(exc,'pipeline_stage',None):exc.pipeline_stage=trace['stage']
        raise
    finally:
        if trace.get('work_started') is not None:
            mark_stage(trace.get('stage','retrieval'))
            try:
                import monitoring,usage_log
                monitoring.record_generation('pipeline_profile',usage_log.current_user_id(),outcome='profile',stage=trace['stage'],request_id=trace.get('root_id',''),session_id=trace.get('session_id',''),duration_ms=(time.perf_counter()-trace['work_started'])*1000,detail={'outcome':outcome,'queue_ms':round(trace['queue_ms'],2),'stage_ms':{k:round(v,2) for k,v in trace.get('stage_ms',{}).items()}})
            except Exception:logger.warning('Pipeline timing could not be recorded',exc_info=True)
        providers.ACTIVE.reset(connection_token)
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
        # Each workflow already reserves one global slot. Independent checks
        # may borrow a spare slot; if none is free they share their owned slot.
        # Racing both avoids deadlock when all five workflows are active.
        gate=current_gate()
        own_task=asyncio.create_task(owned.acquire());extra_task=asyncio.create_task(gate.acquire())
        selected=None
        try:
            await asyncio.wait([own_task,extra_task],return_when=asyncio.FIRST_COMPLETED)
            selected='owned' if own_task.done() and not own_task.cancelled() and own_task.exception() is None else 'extra'
            await (own_task if selected=='owned' else extra_task)
        finally:
            for task in [own_task,extra_task]:
                if not task.done():task.cancel()
            await asyncio.gather(own_task,extra_task,return_exceptions=True)
            own_acquired=own_task.done() and not own_task.cancelled() and own_task.exception() is None
            extra_acquired=extra_task.done() and not extra_task.cancelled() and extra_task.exception() is None
            if own_acquired and selected!='owned':owned.release()
            if extra_acquired and selected!='extra':gate.release()
        try:yield
        finally:
            if selected=='owned':owned.release()
            elif selected=='extra':gate.release()
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
