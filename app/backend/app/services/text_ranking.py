"""
Dependency-free TF-IDF cosine ranking.

Used to rank all MCSB controls by textual relevance to an external control so the
mapping prompt presents the strongest candidates first (better model attention)
without excluding any control. Pure functions, no third-party dependencies - the
corpus is tiny (< 100 short documents) so plain-Python sparse vectors are fast.
"""

import math
import re
from collections import Counter
from typing import Dict, List, Sequence, Tuple

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Minimal stop-word set: high-frequency words that add no discriminating signal.
_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "is",
    "are", "be", "as", "by", "that", "this", "it", "its", "your", "you", "at",
    "from", "which", "should", "must", "such", "using", "use", "used", "ensure",
})


def tokenize(text: str) -> List[str]:
    """Lowercase, extract alphanumeric tokens, and drop stop-words/short tokens."""
    if not text:
        return []
    return [
        token for token in _TOKEN_RE.findall(text.lower())
        if len(token) > 1 and token not in _STOP_WORDS
    ]


def compute_idf(documents: Sequence[Sequence[str]]) -> Dict[str, float]:
    """Smoothed inverse document frequency over a tokenised corpus."""
    total = len(documents)
    document_frequency: Counter = Counter()
    for tokens in documents:
        for token in set(tokens):
            document_frequency[token] += 1
    # Smoothed idf keeps weights positive even for corpus-wide terms.
    return {
        token: math.log((total + 1) / (freq + 1)) + 1.0
        for token, freq in document_frequency.items()
    }


def tfidf_vector(tokens: Sequence[str], idf: Dict[str, float]) -> Dict[str, float]:
    """Build an L2-normalised TF-IDF vector for a token sequence."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    length = len(tokens)
    vector = {
        token: (count / length) * idf.get(token, 0.0)
        for token, count in counts.items()
        if idf.get(token, 0.0) > 0.0
    }
    norm = math.sqrt(sum(weight * weight for weight in vector.values()))
    if norm == 0.0:
        return {}
    return {token: weight / norm for token, weight in vector.items()}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine similarity of two L2-normalised sparse vectors."""
    if not a or not b:
        return 0.0
    # Iterate over the smaller vector for efficiency.
    if len(a) > len(b):
        a, b = b, a
    return sum(weight * b.get(token, 0.0) for token, weight in a.items())


def rank_documents(
    query_tokens: Sequence[str],
    document_tokens: Sequence[Sequence[str]],
    idf: Dict[str, float],
) -> List[Tuple[int, float]]:
    """Rank documents against a query, returning (index, score) best-first.

    Ordering is stable: equal scores preserve the documents' original order.
    """
    query_vector = tfidf_vector(query_tokens, idf)
    scored = [
        (index, cosine(query_vector, tfidf_vector(tokens, idf)))
        for index, tokens in enumerate(document_tokens)
    ]
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored
