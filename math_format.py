"""Bounded local KaTeX compilation using the same renderer as the browser."""
import functools, json, shutil, subprocess, os
from pathlib import Path
ROOT = Path(__file__).resolve().parent

@functools.lru_cache(maxsize=128)
def validate_fields(texts):
    if not any(('$' in text or '\\(' in text or '\\[' in text for text in texts)):
        return
    node = os.getenv('STUDY_NODE_BINARY') or shutil.which('node')
    if not node:
        raise ValueError('The mathematical formatting validator is unavailable.')
    try:
        process = subprocess.run([node, str(ROOT / 'scripts/check-math.cjs')], input=json.dumps(texts, ensure_ascii=False), encoding='utf-8', capture_output=True, timeout=6, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if process.returncode:
            raise ValueError('Mathematical formatting could not compile: ' + process.stderr[:350])
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('Mathematical formatting validation could not finish.') from exc

def validate(text):
    return validate_fields((text,))

async def check(*texts):
    import asyncio
    from tools import CandidateError
    try:
        await asyncio.to_thread(validate_fields, tuple(texts))
    except ValueError as exc:
        raise CandidateError(str(exc), feedback='Rewrite invalid mathematical markup using supported KaTeX syntax. Preserve the problem and all mathematical meanings. ' + str(exc)) from exc
