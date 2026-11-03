"""One consistent text-layer extraction path for upload validation and indexing."""
import re

def extract_page(page):
    try:
        text = page.extract_text(extraction_mode='layout', layout_mode_space_vertically=False) or ''
    except (TypeError, ValueError):
        text = page.extract_text() or ''
    return re.sub('(?<=\\S) {3,}(?=\\S)', ' | ', text)
