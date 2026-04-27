"""Verify that answer citations refer to supplied sources and are supported.

Two flavors of citation marker are recognized inside ``answer``:

* numeric  ``[1]`` / ``[42]``  -- resolves to ``sources[N-1]`` by 1-based index
  AND to any ``source.id`` whose string representation equals ``"N"``.
* named    ``[id:abc123]``     -- resolves to the ``source.id == "abc123"``.

Bare bracketed text that is neither a digit run nor an ``id:...`` form is
ignored (e.g. ``[Note]`` does not count as a citation).

Three things are computed per the spec:

* ``missing``     -- citation ids that don't resolve to any supplied source.
* ``unsupported`` -- claims (sentences) that have no valid citation OR cite a
  source whose ``text`` doesn't actually overlap the claim by the
  ``support_threshold`` token-overlap fraction (default ``0.2``).
* ``coverage``    -- fraction of answer sentences with at least one valid
  citation. ``0.0`` when there are no sentences.

The token-overlap heuristic is intentionally simple: lowercase, split on
non-alphanumeric, drop a small built-in stopword set, then compute
``|claim_tokens & source_tokens| / |claim_tokens|``. Tunable via
``support_threshold``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

# A small stopword list keeps the overlap heuristic from being dominated by
# function words that are present in literally any sentence and source.
_STOPWORDS: Set[str] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}

# Match either [123]  -> ('123', '')
#         or  [id:foo] -> ('', 'foo')
# Anything else inside brackets (e.g. "[note]") is intentionally ignored so
# we don't false-positive on stylistic brackets in prose.
_CITATION_RE = re.compile(r"\[(?:(\d+)|id:([^\]\s]+))\]", re.IGNORECASE)

# Sentence splitter: terminator (. ! ?) followed by whitespace or end-of-string.
# Newlines are also treated as sentence boundaries so bullet lists count as
# multiple sentences. Kept simple on purpose -- we want predictable behavior,
# not a full NLP segmenter.
_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|\n|$)")

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class Claim:
    """A single sentence-level claim extracted from the answer.

    Attributes:
        sentence: The trimmed sentence text.
        citations: List of citation ids referenced by this sentence (may be
            empty). Ids are normalized to strings.
        reason: Why the claim is unsupported, if it is. One of
            ``"no_citation"`` (no citations at all),
            ``"missing_source"`` (cited id doesn't exist), or
            ``"insufficient_overlap"`` (cited source doesn't actually
            mention the claim by the token-overlap heuristic). Empty string
            when the claim is supported.
    """

    sentence: str
    citations: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class CitationResult:
    """Structured result returned by :func:`verify`.

    Attributes:
        ok: ``True`` iff there are no missing ids and no unsupported claims.
        missing: Sorted unique citation ids that don't resolve to any source.
        unsupported: Claims that lack a valid supporting citation.
        coverage: Fraction of sentences with at least one valid citation,
            in ``[0.0, 1.0]``. ``0.0`` for an empty answer.
    """

    ok: bool
    missing: List[str]
    unsupported: List[Claim]
    coverage: float


def verify(
    answer: str,
    sources: Sequence[Mapping[str, Any]],
    *,
    support_threshold: float = 0.2,
) -> CitationResult:
    """Verify ``answer`` citations against ``sources``.

    Args:
        answer: The model's answer text. May contain ``[1]`` / ``[id:foo]``
            citation markers.
        sources: Iterable of ``{"id": <str>, "text": <str>}`` dicts. ``id``
            is required; ``text`` is required for claim support to be
            verifiable (sources without text can still satisfy the
            "id resolves" check, but cannot support a claim).
        support_threshold: Minimum fraction of (non-stopword) claim tokens
            that must appear in the cited source's text for the citation to
            count as supporting. Default ``0.2``.

    Returns:
        A :class:`CitationResult` describing missing ids, unsupported
        claims, and per-sentence coverage.
    """
    if answer is None:
        answer = ""
    if not isinstance(answer, str):
        raise TypeError("verify: answer must be a string")
    if sources is None:
        sources = []

    # Build a {normalized_id -> source_text} map. Numeric citations resolve
    # by 1-based index AND by id-equality, so we register both.
    by_id: dict = {}
    for i, src in enumerate(sources):
        if not isinstance(src, Mapping):
            continue
        sid = src.get("id")
        text = src.get("text", "")
        sid_str = str(sid) if sid is not None else ""
        text_str = text if isinstance(text, str) else ""
        if sid_str:
            by_id[sid_str] = text_str
        # Numeric index alias -- so [1] picks up sources[0].
        by_id.setdefault(str(i + 1), text_str)

    sentences = _split_sentences(answer)

    # Walk every citation in the answer to compute the global "missing" set.
    all_cited_ids: Set[str] = set()
    for _, raw_id in _iter_citations(answer):
        all_cited_ids.add(raw_id)

    missing_ids = sorted({cid for cid in all_cited_ids if cid not in by_id})

    claims: List[Claim] = []
    supported_count = 0
    for sentence in sentences:
        cite_ids = [cid for _, cid in _iter_citations(sentence)]
        # Strip citation markers before measuring overlap so we score on
        # actual claim words, not the bracket text.
        sentence_text = _CITATION_RE.sub("", sentence).strip()
        claim = Claim(sentence=sentence_text, citations=cite_ids)

        if not cite_ids:
            claim.reason = "no_citation"
            claims.append(claim)
            continue

        # Find citations that resolve to a real source AND are supported.
        valid_supports = []
        any_resolves = False
        for cid in cite_ids:
            if cid not in by_id:
                continue
            any_resolves = True
            src_text = by_id[cid]
            if _supports(sentence_text, src_text, support_threshold):
                valid_supports.append(cid)

        if valid_supports:
            supported_count += 1
            continue
        if not any_resolves:
            claim.reason = "missing_source"
        else:
            claim.reason = "insufficient_overlap"
        claims.append(claim)

    coverage = (supported_count / len(sentences)) if sentences else 0.0
    unsupported = [c for c in claims if c.reason]
    ok = not missing_ids and not unsupported

    return CitationResult(
        ok=ok,
        missing=missing_ids,
        unsupported=unsupported,
        coverage=coverage,
    )


def _iter_citations(text: str) -> Iterable[Tuple[int, str]]:
    """Yield (start_index, normalized_id) for every citation marker."""
    for m in _CITATION_RE.finditer(text):
        num, named = m.group(1), m.group(2)
        cid = num if num else named
        yield m.start(), cid


def _split_sentences(text: str) -> List[str]:
    """Split ``text`` into trimmed, non-empty sentences."""
    out = []
    for m in _SENTENCE_RE.finditer(text):
        s = m.group(0).strip()
        if s:
            out.append(s)
    return out


def _supports(claim: str, source: str, threshold: float) -> bool:
    """Return True if ``source`` overlaps ``claim`` by ``threshold`` of tokens.

    No source text -> never supports. Empty claim tokens (after stopword
    removal) -> trivially supported (we don't penalize a sentence that's
    just stopwords; that's a quirk of the heuristic, not a bug).
    """
    if not source:
        return False
    claim_tokens = _meaningful_tokens(claim)
    if not claim_tokens:
        return True
    source_tokens = set(_TOKEN_RE.findall(source.lower()))
    overlap = len(claim_tokens & source_tokens)
    return (overlap / len(claim_tokens)) >= threshold


def _meaningful_tokens(text: str) -> Set[str]:
    """Lowercase tokens with built-in stopwords removed."""
    return {tok for tok in _TOKEN_RE.findall(text.lower()) if tok not in _STOPWORDS}
