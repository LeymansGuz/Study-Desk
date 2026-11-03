"""Local embedding comparisons plus task intent; numeric-only variants are repeats."""
from functools import lru_cache
import re
import logging
import threading
import numpy as np
logger = logging.getLogger(__name__)
_ENCODER_LOCK = threading.Lock()

@lru_cache(maxsize=1)
def encoder():
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    return DefaultEmbeddingFunction()

def normalized(text):
    return re.sub('\\b\\d+(?:\\.\\d+)?\\b', 'NUMBER', text.lower())

def task_families(text):
    groups = {'proof': 'prove|show that|justify', 'explain': 'explain|interpret|discuss|describe|why', 'derivative': 'differentiat|derivative|slope', 'integral': 'integrat|antiderivative|area under', 'numeric': 'calculat|compute|determin|find|value|price|yield|solve'}
    return {name for name, pattern in groups.items() if re.search(pattern, text, re.I)}

@lru_cache(maxsize=1024)
def vector(text):
    with _ENCODER_LOCK:
        return np.asarray(encoder()([text])[0], dtype=float)

def duplicate(question, previous):
    from tools import problem_similarity
    if any((problem_similarity(question, old) >= 0.82 for old in previous)):
        return True
    if not previous:
        return False
    intent = task_families(question)
    try:
        query = vector(normalized(question))
        for old in previous:
            other_intent = task_families(old)
            if intent and other_intent and (not intent & other_intent):
                continue
            other = vector(normalized(old))
            cosine = float(np.dot(query, other) / (np.linalg.norm(query) * np.linalg.norm(other)))
            if cosine >= 0.94:
                return True
    except Exception:
        logger.warning('Semantic duplicate encoder unavailable; wording guard remains active')
    return False
