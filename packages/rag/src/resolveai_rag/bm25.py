"""Minimal BM25Okapi for hybrid retrieval (no extra dependency)."""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_ids: list[str] = []
        self._docs_tokens: list[list[str]] = []
        self._doc_len: list[int] = []
        self._avgdl = 0.0
        self._df: Counter[str] = Counter()
        self._n = 0

    def rebuild(self, documents: dict[str, str]) -> None:
        self.doc_ids = list(documents.keys())
        self._docs_tokens = [tokenize(documents[i]) for i in self.doc_ids]
        self._doc_len = [len(toks) for toks in self._docs_tokens]
        self._n = len(self.doc_ids)
        self._avgdl = (sum(self._doc_len) / self._n) if self._n else 0.0
        self._df = Counter()
        for toks in self._docs_tokens:
            for term in set(toks):
                self._df[term] += 1

    def search(self, query: str, *, limit: int = 5) -> list[tuple[str, float]]:
        if self._n == 0:
            return []
        q_terms = tokenize(query)
        if not q_terms:
            return []
        scores: list[tuple[str, float]] = []
        for idx, doc_id in enumerate(self.doc_ids):
            score = self._score(q_terms, idx)
            if score > 0:
                scores.append((doc_id, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:limit]

    def _score(self, q_terms: list[str], doc_idx: int) -> float:
        toks = self._docs_tokens[doc_idx]
        tf = Counter(toks)
        dl = self._doc_len[doc_idx] or 1
        score = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            df = self._df.get(term, 0)
            idf = math.log(1 + (self._n - df + 0.5) / (df + 0.5))
            freq = tf[term]
            denom = freq + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1.0))
            score += idf * (freq * (self.k1 + 1)) / denom
        return score


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    *,
    k: int = 60,
    limit: int = 5,
) -> list[tuple[str, float]]:
    """RRF: score = Σ 1 / (k + rank)."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ordered[:limit]
