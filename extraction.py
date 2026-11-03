"""Safe extraction of assignment questions from PDFs and screenshots.

Files are processed in memory and never stored or ingested into the RAG corpus.
Images are OCR'd locally with RapidOCR; PDFs use their text layer and fall back
to page rendering + OCR for scanned pages.
"""
from __future__ import annotations
import io
import logging
from contextvars import ContextVar
from typing import Any
import pypdfium2 as pdfium
from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from security import MAX_ASSIGNMENT_CHARS, MAX_PDF_PAGES, extract_office_text, scan_untrusted_text, validate_upload
from document_ocr import MAX_OCR_PAGES, ocr_layout
from upload_limits import QUESTION_FILE_BYTES, QUESTION_PAGES, IMAGE_PIXELS
_QUALITY = ContextVar('assignment_quality', default=None)

def ocr_image(image):
    result = ocr_layout(image)
    quality = _QUALITY.get()
    if quality is not None and result.get('needs_review'):
        quality.append('Some text was recognised with low confidence. Check symbols, numbers and labels against the original.')
    return result['text']
logger = logging.getLogger(__name__)
MAX_IMAGE_PIXELS = IMAGE_PIXELS
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

def extract_assignment_file(filename: str, data: bytes) -> dict[str, Any]:
    """Validate and extract text from a question PDF or screenshot."""
    validated = validate_upload(filename, data, corpus=False, max_bytes=QUESTION_FILE_BYTES, max_pages=QUESTION_PAGES)
    if validated.get('active_content'):
        logger.warning('Accepted assignment PDF with active/embedded content: %s', validated['filename'])
    extension = validated['extension']
    ocr_used = False
    page_count = validated.get('page_count') or 1
    quality = []
    token = _QUALITY.set(quality)
    try:
        return _extract_validated(filename, data, validated, quality)
    finally:
        _QUALITY.reset(token)

def _extract_validated(filename, data, validated, quality):
    extension = validated['extension']
    ocr_used = False
    page_count = validated.get('page_count') or 1
    if extension == '.pdf':
        text, ocr_used, page_count = _extract_pdf(data, validated.get('_pdf_pages'))
    elif extension in {'.doc', '.docx'}:
        text = extract_office_text(data)
        page_count = 1
    elif extension in {'.txt','.md'}:
        text=validated['text'];page_count=1
    else:
        text = _extract_image(data)
        ocr_used = True
    text = (text or '').strip()
    if not text:
        raise HTTPException(status_code=422, detail='No readable text was found. Try a clearer screenshot or a text-based PDF.')
    truncated = len(text) > MAX_ASSIGNMENT_CHARS
    if truncated:
        raise HTTPException(413, 'This attachment contains too much text for one question. Upload only the relevant question and working pages.')
    if ocr_used:
        quality.append('OCR extracts text, not diagram relationships. Supply any essential geometric or graph facts in words.')
    flags = scan_untrusted_text(text)
    if flags:
        raise HTTPException(status_code=400, detail='The uploaded question contains instruction-like text that could hijack the tutor. Remove it and try again.')
    return {'warnings': list(dict.fromkeys(quality)), 'needs_review': bool(quality), 'filename': validated['filename'], 'text': text, 'page_count': page_count, 'ocr_used': ocr_used, 'truncated': truncated, 'chars': len(text)}

def _extract_pdf(data: bytes, validated_pages=None) -> tuple[str, bool, int]:
    try:
        if validated_pages is None:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise HTTPException(status_code=400, detail='Encrypted PDFs are not supported.')
            validated_pages = [(index, (page.extract_text() or '').strip()) for index, page in enumerate(reader.pages, 1)]
        page_count = len(validated_pages)
        if page_count > min(MAX_PDF_PAGES, QUESTION_PAGES):
            raise HTTPException(status_code=413, detail=f'This question PDF has {page_count} pages. Upload at most 20 relevant question/working pages; course documents belong in Workspace.')
        text_pages = [text.strip() for _, text in validated_pages]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail='Could not read this PDF.') from exc
    ocr_used = False
    ocr_budget = MAX_OCR_PAGES or page_count
    if any((len(page_text) < 30 for page_text in text_pages)) and ocr_budget:
        try:
            document = pdfium.PdfDocument(data)
            for index, page_text in enumerate(text_pages):
                if ocr_budget <= 0:
                    break
                if len(page_text) >= 30:
                    continue
                page = document[index]
                width,height=page.get_size()
                scale=min(2.0,(MAX_IMAGE_PIXELS/max(1,width*height))**.5)
                image = page.render(scale=scale).to_pil()
                try:
                    recognized = ocr_image(image)
                finally:
                    image.close()
                    page.close()
                if recognized:
                    text_pages[index] = recognized
                    ocr_used = True
                ocr_budget -= 1
            document.close()
        except Exception as exc:
            logger.exception('OCR fallback failed for PDF')
            raise HTTPException(422,'Could not read the scanned question pages completely. Use clearer or cropped pages, or enter the question text.') from exc
    return ('\n\n'.join(text_pages), ocr_used, page_count)

def _extract_image(data: bytes) -> str:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail='Image dimensions are too large.')
            image.load()
            working = image.copy()
            try:
                return ocr_image(working)
            finally:
                working.close()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=415, detail='Unsupported or corrupt image.') from exc
    except Image.DecompressionBombError as exc:
        raise HTTPException(status_code=413, detail='Image is too large.') from exc
