"""Shared local upload budgets, independent of paid model context limits."""
MIB = 1024 * 1024
WORKSPACE_FILES = 50
WORKSPACE_BYTES = 500 * MIB
DOCUMENT_BYTES = 200 * MIB
IMAGE_BYTES = 20 * MIB
IMAGE_PIXELS = 16_000_000
QUESTION_FILES = 5
QUESTION_BYTES = 50 * MIB
QUESTION_FILE_BYTES = 20 * MIB
QUESTION_PAGES = 20
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

def public():
    return {'workspace_files':WORKSPACE_FILES,'workspace_bytes':WORKSPACE_BYTES,
            'document_bytes':DOCUMENT_BYTES,'image_bytes':IMAGE_BYTES,'image_pixels':IMAGE_PIXELS,
            'question_files':QUESTION_FILES,'question_bytes':QUESTION_BYTES,
            'question_file_bytes':QUESTION_FILE_BYTES,'question_pages':QUESTION_PAGES,
            'question_chars':30_000}
