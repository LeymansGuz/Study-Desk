"""Local OCR for image-heavy PDF pages and screenshots.

Text PDFs keep their text layer. Low-text pages are rendered for OCR. Diagrams
and mathematical layout still need inspection; OCR is not a visual understanding
or formula-recognition guarantee.
"""
from __future__ import annotations
import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageOps
from rapidocr_onnxruntime import RapidOCR
from security import sanitize_text
logger = logging.getLogger(__name__)
MAX_OCR_PAGES = int(os.getenv('MAX_OCR_PAGES', '0'))
OCR_TEXT_THRESHOLD = int(os.getenv('OCR_TEXT_THRESHOLD', '40'))
_OCR_LOCK = threading.Lock()
OCR_GROUP_TIMEOUT_SECONDS = int(os.getenv('OCR_GROUP_TIMEOUT_SECONDS', '240'))

@lru_cache(maxsize=1)
def _ocr_engine() -> RapidOCR:
    return RapidOCR(intra_op_num_threads=max(1, int(os.getenv('OCR_THREADS', '2'))), inter_op_num_threads=1)

def ocr_image(image: Image.Image) -> str:
    return ocr_layout(image)['text']

def ocr_layout(image: Image.Image) -> dict:
    """Keep confidence, line geometry and table-like reading rows for inspection."""
    rgb = ImageOps.exif_transpose(image).convert('RGB')
    with _OCR_LOCK:
        result, _elapsed = _ocr_engine()(np.asarray(rgb))
    if not result:
        return {'text': '', 'lines': [], 'confidence': 0, 'needs_review': True}
    lines = []
    for item in result:
        if len(item) < 2 or not item[1]:
            continue
        box = np.asarray(item[0]).tolist()
        lines.append({'text': item[1].strip(), 'box': box, 'confidence': float(item[2]) if len(item) > 2 else 0})
    lines.sort(key=lambda line: (round(min((p[1] for p in line['box'])) / 14), min((p[0] for p in line['box']))))
    rows = []
    for line in lines:
        y = min((p[1] for p in line['box']))
        if rows and abs(rows[-1]['y'] - y) < 14:
            rows[-1]['cells'].append(line['text'])
        else:
            rows.append({'y': y, 'cells': [line['text']]})
    confidence = sum((line['confidence'] for line in lines)) / max(1, len(lines))
    text = '\n'.join((' | '.join(row['cells']) for row in rows))
    return {'text': text, 'lines': lines, 'rows': rows, 'confidence': confidence, 'needs_review': confidence < 0.88 or any((line['confidence'] < 0.7 for line in lines)), 'visual_limit': 'OCR preserves text and row positions. Verify equations, diagrams and table headers against the page.'}

def render_pdf_page(path: str | Path, page_index: int, scale: float=1.6) -> Image.Image:
    document = pdfium.PdfDocument(str(path))
    try:
        page = document[page_index]
        return page.render(scale=scale).to_pil()
    finally:
        document.close()

def enrich_pdf_pages(path: Path, pages: list[tuple[int, str]], statuses: list | None=None) -> list[tuple[int, str]]:
    """Add OCR text for scanned PDF pages that have almost no text layer."""
    budget = MAX_OCR_PAGES
    enriched: list[tuple[int, str]] = []
    for index, (page_number, text) in enumerate(pages):
        status = {'page': page_number, 'text_chars': len(text.strip()), 'status': 'text'}
        if statuses is not None:
            statuses.append(status)
        needs_ocr = len(text.strip()) < OCR_TEXT_THRESHOLD
        if not needs_ocr:
            enriched.append((page_number, text))
            continue
        if MAX_OCR_PAGES > 0 and budget <= 0:
            status['status'] = 'ocr_pending'
            enriched.append((page_number, text))
            continue
        try:
            image = render_pdf_page(path, page_number - 1, scale=1.4)
        except Exception:
            status['status'] = 'render_failed'
            enriched.append((page_number, text))
            continue
        try:
            layout = ocr_layout(image)
            recognized = layout['text']
            status['ocr_confidence'] = layout['confidence']
            status['low_confidence_lines'] = sum((line['confidence'] < 0.7 for line in layout['lines']))
        except Exception:
            logger.exception('OCR failed on page %s of %s', page_number, path.name)
            recognized = ''
        finally:
            image.close()
        if recognized and recognized.strip() not in text:
            text = f'{text.strip()}\n\n[OCR text]\n{recognized}'.strip()
        budget -= 1
        status['text_chars'] = len(text.strip())
        status['status'] = 'ocr' if len(recognized.strip()) >= OCR_TEXT_THRESHOLD and status.get('ocr_confidence', 0) >= 0.88 and (not status.get('low_confidence_lines')) else 'needs_review'
        enriched.append((page_number, sanitize_text(text, max_chars=12000)))
    return enriched
_POOL = None
_POOL_INIT_LOCK = threading.Lock()

def _page_group_task(path, indices, queue):
    document = pdfium.PdfDocument(path)
    try:
        for index in indices:
            image = None
            try:
                page = document[index]
                try:
                    bitmap = page.render(scale=1.4)
                    try:
                        image = bitmap.to_pil().copy()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                layout = ocr_layout(image)
                error = None
            except Exception as exc:
                layout = None
                error = type(exc).__name__
            finally:
                if image is not None:
                    image.close()
            queue.put((index, layout, error))
    finally:
        document.close()

def close_pool():
    global _POOL
    with _POOL_INIT_LOCK:
        pool, _POOL = (_POOL, None)
    if pool:
        pool.shutdown(wait=True, cancel_futures=True)

def parallel_layouts(path, indices):
    """Bounded jobs, streaming page checkpoints, and no retained source-file handles."""
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing, queue
    global _POOL
    context = multiprocessing.get_context('spawn')
    workers = max(1, min(2, int(os.getenv('OCR_WORKERS', '2'))))
    with _POOL_INIT_LOCK:
        if _POOL is None:
            _POOL = ProcessPoolExecutor(max_workers=workers, mp_context=context)
        pool = _POOL
    group_size = min(16, max(1, (len(indices) + workers - 1) // workers))
    groups = iter([indices[start:start + group_size] for start in range(0, len(indices), group_size)])
    with context.Manager() as manager:
        results = manager.Queue(maxsize=workers * 2)
        pending = set()
        received = set()

        def add():
            group = next(groups, None)
            if group is not None:
                pending.add(pool.submit(_page_group_task, str(path), group, results))
        for _ in range(workers):
            add()
        import time
        last_progress = time.monotonic()
        while pending or len(received) < len(indices):
            try:
                index, layout, error = results.get(timeout=0.1)
                if index not in received:
                    received.add(index)
                    yield (index, layout, error)
                    last_progress = time.monotonic()
            except queue.Empty:
                if not pending and len(received) < len(indices):
                    raise RuntimeError('An OCR worker stopped before all pages were checkpointed.')
                if time.monotonic() - last_progress > OCR_GROUP_TIMEOUT_SECONDS:
                    for future in list(pending):
                        future.cancel()
                    raise TimeoutError('An OCR worker stopped making progress; retrying this file without the subprocess pool.')
            for future in list(pending):
                if future.done():
                    pending.remove(future)
                    future.result()
                    add()
                    last_progress = time.monotonic()

def enrich_checkpointed(path, pages, document, user, signature, statuses):
    import index_cache, time
    cached = index_cache.load(document, 'ocr', signature)
    output = {}
    states = {}
    needed = []
    budget = MAX_OCR_PAGES
    started = time.perf_counter()
    hits = 0
    for index, (number, text) in enumerate(pages):
        if len(text.strip()) >= OCR_TEXT_THRESHOLD:
            output[number] = text
            states[number] = {'page': number, 'text_chars': len(text.strip()), 'status': 'text'}
        elif number in cached:
            output[number] = cached[number]['text']
            states[number] = cached[number]['status']
            hits += 1
        elif MAX_OCR_PAGES > 0 and budget <= 0:
            output[number] = text
            states[number] = {'page': number, 'text_chars': len(text.strip()), 'status': 'ocr_pending'}
        else:
            needed.append(index)
            budget -= 1
    done = len(pages) - len(needed)
    index_cache.notify(stage='ocr', pages_done=done, pages_total=len(pages), cache_hits=hits)
    if needed:
        if int(os.getenv('OCR_WORKERS', '2')) > 0:
            try:
                layouts = list(parallel_layouts(path, needed))
            except Exception:
                logger.exception('Parallel OCR failed for %s; retrying serially', path.name)
                layouts = None
        else:
            layouts = None
        if layouts is None:

            def serial():
                doc = pdfium.PdfDocument(str(path))
                try:
                    for index in needed:
                        page = doc[index]
                        try:
                            bitmap = page.render(scale=1.4)
                            try:
                                image = bitmap.to_pil().copy()
                            finally:
                                bitmap.close()
                        finally:
                            page.close()
                        try:
                            yield (index, ocr_layout(image), None)
                        except Exception as exc:
                            yield (index, None, type(exc).__name__)
                        finally:
                            image.close()
                finally:
                    doc.close()
            layouts = list(serial())
        for index, layout, error in layouts:
            number, text = pages[index]
            if error:
                local = []
                result = enrich_pdf_pages(path, [(number, text)], local)
                output[number] = result[0][1]
                state = local[0]
            else:
                recognized = layout['text']
                if recognized and recognized.strip() not in text:
                    text = f'{text.strip()}\n\n[OCR text]\n{recognized}'.strip()
                text = sanitize_text(text, max_chars=12000)
                state = {'page': number, 'text_chars': len(text), 'ocr_confidence': layout['confidence'], 'low_confidence_lines': sum((line['confidence'] < 0.7 for line in layout['lines']))}
                state['status'] = 'ocr' if len(recognized.strip()) >= OCR_TEXT_THRESHOLD and state['ocr_confidence'] >= 0.88 and (not state['low_confidence_lines']) else 'needs_review'
                output[number] = text
            states[number] = state
            if state['status'] not in {'ocr_pending', 'render_failed'}:
                index_cache.save(document, user, 'ocr', number, signature, {'text': output[number], 'status': state})
            done += 1
            index_cache.notify(stage='ocr', pages_done=done, pages_total=len(pages), cache_hits=hits, ocr_seconds=round(time.perf_counter() - started, 3))
    statuses.extend((states[number] for number, _ in pages))
    return [(number, output[number]) for number, _ in pages]
