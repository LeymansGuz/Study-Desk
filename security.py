"""Security primitives for the study tool.

The app is local-first, but the upload surface, LLM calls, and admin actions still
need explicit boundaries. This module provides constant-time admin auth, a small
sliding-window rate limiter, upload validation, prompt-injection scanning, and
safe untrusted-text wrapping.
"""
from __future__ import annotations
from pathlib import Path, PurePosixPath
import hashlib
import io
import zipfile
import logging
import os
import re
import secrets
import threading
import time
import unicodedata
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from fastapi import HTTPException, Request
from pypdf import PdfReader
logger = logging.getLogger(__name__)
PROJECT_DIR = Path(__file__).resolve().parent
for _env_path in (Path(__file__).resolve().parent / '.env',):
    if _env_path.is_file():
        load_dotenv(_env_path, override=False)
from upload_limits import DOCUMENT_BYTES, IMAGE_BYTES, IMAGE_PIXELS, IMAGE_EXTENSIONS
MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_BYTES', str(DOCUMENT_BYTES)))
MAX_PDF_PAGES = int(os.getenv('MAX_PDF_PAGES', '300'))
MAX_UPLOAD_TEXT_CHARS = int(os.getenv('MAX_UPLOAD_TEXT_CHARS', '2000000'))
MAX_ASSIGNMENT_CHARS = int(os.getenv('MAX_ASSIGNMENT_CHARS', '30000'))
ALLOWED_CORPUS_EXTENSIONS = {'.pdf', '.md', '.txt', '.doc', '.docx'} | IMAGE_EXTENSIONS
ALLOWED_ASSIGNMENT_EXTENSIONS = ALLOWED_CORPUS_EXTENSIONS.copy()
ACTIVE_PDF_MARKERS = (b'/JavaScript', b'/EmbeddedFile', b'/Launch', b'/RichMedia')
INJECTION_PATTERNS = [re.compile('\\bignore\\s+(?:all\\s+)?(?:previous|above|prior)\\s+instructions?\\b', re.I), re.compile('\\b(?:system|developer)\\s+(?:prompt|message)\\b', re.I), re.compile('\\breveal\\s+(?:the\\s+)?(?:system|hidden|secret)\\s+(?:prompt|instructions?|key)\\b', re.I), re.compile('\\byou\\s+are\\s+now\\s+(?:a|an|the)\\b', re.I), re.compile('\\b(?:tool|function)\\s*call\\b', re.I), re.compile('<\\s*script\\b', re.I), re.compile('\\b(?:exfiltrate|send\\s+the\\s+key|print\\s+the\\s+key)\\b', re.I)]

def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sanitize_filename(name: str, allowed: set[str] | None=None) -> str:
    # Upload names can use either separator regardless of the server's OS.
    normalized = unicodedata.normalize('NFKC', name or '').replace('\\', '/')
    base = PurePosixPath(normalized).name
    base = re.sub('[^A-Za-z0-9._ -]+', '_', base)
    base = re.sub('\\s+', ' ', base).strip(' .')
    base = re.sub('\\.{2,}', '.', base)
    if not base:
        raise HTTPException(status_code=400, detail='Invalid file name.')
    suffix = Path(base).suffix.lower()
    if allowed is not None and suffix not in allowed:
        raise HTTPException(status_code=415, detail=f"Unsupported file type. Allowed: {', '.join(sorted(allowed))}.")
    if len(base) > 140:
        base = base[:120] + suffix
    return base

def scan_untrusted_text(text: str) -> list[str]:
    """Return human-readable flags for likely prompt-injection content."""
    flags: list[str] = []
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            flags.append(pattern.pattern)
    if '\u200b' in text or '\u202e' in text:
        flags.append('zero-width or bidirectional formatting characters')
    return flags

def sanitize_text(text: str, *, max_chars: int | None=None) -> str:
    text = unicodedata.normalize('NFKC', text or '')
    text = text.replace('\x00', '')
    text = ''.join((char for char in text if char in '\n\t' or (ord(char) >= 32 and char not in '\u200b\u202e')))
    text = re.sub('\\r\\n?', '\n', text)
    text = re.sub('\\n{4,}', '\n\n\n', text).strip()
    if max_chars is not None:
        text = text[:max_chars]
    return text

def neutralize_prompt_delimiters(text: str) -> str:
    """Prevent untrusted text from closing our XML-like prompt blocks."""
    for tag in ('course_material', 'student_question', 'requested_topic', 'student_answer', 'question', 'private_canonical_answer', 'private_worked_solution', 'assignment'):
        text = re.sub(f'<\\s*/?\\s*{tag}[^>]*>', '[removed tag]', text, flags=re.IGNORECASE)
    return text

def wrap_untrusted(label: str, text: str, max_chars: int=MAX_ASSIGNMENT_CHARS) -> str:
    """Wrap untrusted text in nonce-tagged delimiters."""
    nonce = secrets.token_hex(6)
    cleaned = neutralize_prompt_delimiters(sanitize_text(text, max_chars=max_chars))
    tag = f'{label}-{nonce}'
    return f'<{tag}>\n{cleaned}\n</{tag}>'

def extract_office_text(data: bytes) -> str:
    """Extract Word text without depending on a single parser.

    DOCX is a ZIP of XML; python-docx gives predictable paragraph/table text.
    Extractous/Tika remains the fallback and is the only path for legacy .doc.
    """
    candidates: list[str] = []
    if data.startswith(b'PK'):
        try:
            from docx import Document
            document = Document(io.BytesIO(data))
            parts: list[str] = []
            parts.extend((p.text for p in document.paragraphs if p.text.strip()))
            for table in document.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        parts.append('\t'.join(cells))
            for section in document.sections:
                for part in (section.header, section.footer):
                    parts.extend((p.text for p in part.paragraphs if p.text.strip()))
            text = '\n'.join(parts).strip()
            if text:
                candidates.append(text)
        except Exception as exc:
            log = logging.getLogger(__name__)
            log.warning('python-docx extraction failed: %s', type(exc).__name__)
            try:
                import zipfile
                import xml.etree.ElementTree as ET
                with zipfile.ZipFile(io.BytesIO(data)) as package:
                    names = ['word/document.xml'] + sorted((name for name in package.namelist() if name.startswith(('word/header', 'word/footer')) and name.endswith('.xml')))
                    xml_parts: list[str] = []
                    for name in names:
                        try:
                            root = ET.fromstring(package.read(name))
                        except Exception:
                            continue
                        paragraphs = []
                        for paragraph in root.iter():
                            if not str(paragraph.tag).endswith('}p'):
                                continue
                            text = ''.join((str(node.text or '') for node in paragraph.iter() if str(node.tag).endswith('}t'))).strip()
                            if text:
                                paragraphs.append(text)
                        if paragraphs:
                            xml_parts.append('\n'.join(paragraphs))
                    xml_text = '\n'.join(xml_parts).strip()
                    if xml_text:
                        candidates.append(xml_text)
            except Exception as fallback_exc:
                log.warning('DOCX XML extraction failed: %s', type(fallback_exc).__name__)
    try:
        from extractous import Extractor
        text, _metadata = Extractor().extract_bytes_to_string(bytearray(data))
        if str(text or '').strip():
            candidates.append(str(text).strip())
    except Exception as exc:
        log = logging.getLogger(__name__)
        log.warning('Extractous Word extraction failed: %s', type(exc).__name__)
    return max(candidates, key=len) if candidates else ''

def validate_upload(filename: str, data: bytes, *, corpus: bool=True, max_bytes: int | None=None, max_pages: int | None=None) -> dict[str, Any]:
    """Validate an uploaded course document before it can enter the index."""
    allowed = ALLOWED_CORPUS_EXTENSIONS if corpus else ALLOWED_ASSIGNMENT_EXTENSIONS
    name = sanitize_filename(filename, allowed)
    extension = Path(name).suffix.lower()
    if not data:
        raise HTTPException(status_code=400, detail='Empty file.')
    byte_limit = MAX_UPLOAD_BYTES if max_bytes is None else max_bytes
    if extension in IMAGE_EXTENSIONS: byte_limit = min(byte_limit, IMAGE_BYTES)
    if len(data) > byte_limit:
        raise HTTPException(status_code=413, detail=f'File exceeds the {byte_limit // (1024 * 1024)} MB limit.')
    page_count = 0
    pdf_pages = None
    extracted_text = ''
    active_content = False
    if extension == '.pdf':
        if not data.startswith(b'%PDF-'):
            raise HTTPException(status_code=415, detail='File does not look like a PDF.')
        active_content = any((marker in data for marker in ACTIVE_PDF_MARKERS))
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                try:
                    unlocked = bool(reader.decrypt(''))
                except Exception:
                    unlocked = False
                if not unlocked:
                    raise HTTPException(status_code=400, detail='Password-protected PDFs are not supported.')
            root = reader.trailer.get('/Root') or {}
            names = root.get('/Names') or {}
            acroform = root.get('/AcroForm') or {}
            open_action = root.get('/OpenAction')
            unsafe_open_action = False
            if open_action is not None and hasattr(open_action, 'get'):
                action_type = open_action.get('/S')
                unsafe_open_action = action_type not in {None, '/GoTo'}
            if '/AA' in root or '/JavaScript' in names or '/XFA' in acroform or unsafe_open_action:
                active_content = True
            page_count = len(reader.pages)
            page_limit = min(MAX_PDF_PAGES,max_pages) if max_pages is not None else MAX_PDF_PAGES
            if page_count > page_limit:
                raise HTTPException(status_code=413, detail=f'PDF has {page_count} pages; the limit is {page_limit}. Use only the relevant pages.')
            from pdf_text import extract_page
            pdf_pages = [(index, extract_page(page)) for index, page in enumerate(reader.pages, 1)]
            extracted_text = '\n'.join((text for _, text in pdf_pages))[:MAX_UPLOAD_TEXT_CHARS]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail='Could not read this PDF.') from exc
    elif extension in {'.md', '.txt'}:
        if b'\x00' in data:
            raise HTTPException(status_code=415, detail='Text file contains binary data.')
        try:
            extracted_text = data.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail='Text file must be valid UTF-8.') from exc
        if len(extracted_text) > MAX_UPLOAD_TEXT_CHARS:
            raise HTTPException(status_code=413, detail='Text file is too large.')
        page_count = 1
    elif extension in {'.doc', '.docx'}:
        if extension == '.docx' and (not data.startswith(b'PK')):
            raise HTTPException(status_code=415, detail='File does not look like a DOCX document.')
        if extension == '.docx':
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as package:
                    members=package.infolist()
                    if len(members)>2000 or sum(m.file_size for m in members)>MAX_UPLOAD_BYTES or any(m.flag_bits & 1 for m in members):
                        raise HTTPException(413,'The Word document exceeds its unpacked-size or file-count limit.')
                    for member in members:
                        if member.filename.lower().endswith(('.xml','.rels')):
                            with package.open(member) as xml:
                                tail=b''
                                while chunk:=xml.read(65536):
                                    probe=(tail+chunk).replace(b'\x00',b'')
                                    if b'<!DOCTYPE' in probe or b'<!ENTITY' in probe:
                                        raise HTTPException(400,'Word XML document types and entity declarations are not supported.')
                                    tail=chunk[-64:]
            except zipfile.BadZipFile as exc:
                raise HTTPException(415,'File does not look like a DOCX document.') from exc
        if extension == '.doc' and (not data.startswith(b'\xd0\xcf\x11\xe0')):
            raise HTTPException(status_code=415, detail='File does not look like a DOC document.')
        try:
            extracted_text = extract_office_text(data)[:MAX_UPLOAD_TEXT_CHARS]
        except Exception as exc:
            logger.exception('Could not extract Word upload %s (size=%s sha256=%s)', name, len(data), hashlib.sha256(data).hexdigest()[:16])
            raise HTTPException(status_code=400, detail='Could not read this Word document. If it is an old .doc file, save it as .docx or PDF and try again.') from exc
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail='No readable text was found in this Word document.')
        page_count = 1
    elif extension in IMAGE_EXTENSIONS:
        from PIL import Image,UnidentifiedImageError
        try:
            with Image.open(io.BytesIO(data)) as image:
                expected={'.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG','.webp':'WEBP'}[extension]
                if image.format!=expected:raise HTTPException(415,'Image content does not match its filename extension.')
                if image.width*image.height>IMAGE_PIXELS:raise HTTPException(413,'Image exceeds the 16 megapixel limit. Crop the relevant question or notes.')
                if getattr(image,'n_frames',1)!=1:raise HTTPException(415,'Use a still screenshot rather than an animated image.')
                image.verify()
            page_count=1
        except HTTPException:raise
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
            raise HTTPException(415,'Unsupported, oversized or corrupt image.') from exc
    elif len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail='Image is too large.')
    flags = scan_untrusted_text(extracted_text)
    if flags:
        raise HTTPException(status_code=400, detail=f'File rejected by the prompt-injection screen. Remove instruction-like content or ask an administrator to review it. Signals: {len(flags)}.')
    return {'filename': name, 'extension': extension, 'size': len(data), 'sha256': hash_bytes(data), 'page_count': page_count, 'injection_flags': flags, 'text': extracted_text, 'active_content': active_content, '_pdf_pages': pdf_pages}

def security_headers(_request: Request, response: Any) -> None:
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    if _request.url.scheme == 'https':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"


class SlidingWindowLimiter:

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> tuple[bool, float, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            if len(self._events) >= 10000:
                stale = [name for name, values in self._events.items() if not values or values[-1] < cutoff]
                for name in stale:
                    self._events.pop(name, None)
                if key not in self._events and len(self._events) >= 10000:
                    return (False, self.window_seconds, 0)
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry = max(0.0, self.window_seconds - (now - events[0]))
                return (False, retry, 0)
            events.append(now)
            return (True, 0.0, self.limit - len(events))

def enforce_rate_limit(request: Request, limiter: SlidingWindowLimiter, scope: str, *, user_id: str | None=None) -> None:
    if user_id:
        key = f'user:{user_id}'
    else:
        key = f"ip:{(request.client.host if request.client else 'local')}"
    allowed, retry, _remaining = limiter.hit(f'{scope}:{key}')
    if not allowed:
        raise HTTPException(status_code=429, detail='Too many requests. Please wait and try again.', headers={'Retry-After': str(max(1, int(retry)))})
