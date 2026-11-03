"""Local source-copy guard. Topic vocabulary alone is not a copied question."""
import re
from difflib import SequenceMatcher

def tokens(text):
    text = re.sub('\\b\\d+(?:\\.\\d+)?\\b', 'NUMBER', text.casefold())
    return re.findall('[a-z]+|NUMBER', text)

def source_copy_reason(question, sources):
    """Catch verbatim and number-swapped exercise clones before model solving."""
    q = tokens(question)
    if len(q) < 9:
        return ''
    for row in sources or []:
        source = tokens(row.get('text') or row.get('excerpt') or '')
        if len(source) < 9:
            continue
        match = SequenceMatcher(None, q, source, autojunk=False).find_longest_match()
        if match.size >= min(18, max(9, int(len(q) * 0.65))):
            return 'The question copies a substantial source span, including number-only variants. Design a different reasoning task, not a paraphrase or reskin.'
        if len(q) >= 14:
            for start in range(0, max(1, len(source) - len(q) + 1), max(1, len(q) // 4)):
                window = source[start:start + len(q) + 6]
                if SequenceMatcher(None, q, window, autojunk=False).ratio() > 0.88:
                    return 'The question is structurally too close to a source exercise. Change the inference and information flow, not only names or numbers.'
    return ''
