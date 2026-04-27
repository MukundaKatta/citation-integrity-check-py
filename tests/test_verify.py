"""Tests for ``citation_integrity_check.verify``."""

from __future__ import annotations

import pytest

from citation_integrity_check import CitationResult, verify


def test_all_supported_returns_ok():
    sources = [
        {"id": "1", "text": "Photosynthesis converts light into chemical energy in plants."},
        {"id": "2", "text": "Chlorophyll absorbs red and blue wavelengths of light."},
    ]
    answer = "Plants use photosynthesis to convert light into energy [1]. Chlorophyll absorbs red and blue light [2]."
    r = verify(answer, sources)
    assert isinstance(r, CitationResult)
    assert r.ok is True
    assert r.missing == []
    assert r.unsupported == []
    assert r.coverage == 1.0


def test_missing_citation_id_is_flagged():
    sources = [{"id": "1", "text": "The sky is blue because of Rayleigh scattering."}]
    # [99] does not exist as id or 1-based index -> missing.
    answer = "The sky is blue [99]."
    r = verify(answer, sources)
    assert "99" in r.missing
    assert r.ok is False


def test_unsupported_when_no_citation():
    sources = [{"id": "1", "text": "Cats are mammals."}]
    answer = "The Eiffel Tower is in Paris."
    r = verify(answer, sources)
    assert r.ok is False
    assert len(r.unsupported) == 1
    assert r.unsupported[0].reason == "no_citation"
    assert r.coverage == 0.0


def test_unsupported_when_citation_does_not_match_claim_text():
    sources = [{"id": "1", "text": "The Pacific Ocean is large."}]
    # Cites a real source but the source text has zero overlap with the claim.
    answer = "Newton invented calculus [1]."
    r = verify(answer, sources)
    assert r.ok is False
    assert len(r.unsupported) == 1
    assert r.unsupported[0].reason == "insufficient_overlap"
    assert r.coverage == 0.0


def test_named_id_citation_form():
    sources = [
        {"id": "abc123", "text": "Quantum entanglement was demonstrated by Aspect in 1982."},
    ]
    answer = "Aspect demonstrated quantum entanglement experimentally [id:abc123]."
    r = verify(answer, sources)
    assert r.ok is True
    assert r.coverage == 1.0


def test_numeric_citation_resolves_by_index():
    # No explicit id "1" -- only the implicit 1-based index alias should match.
    sources = [{"id": "uuid-foo", "text": "Mount Everest is the tallest mountain on Earth."}]
    answer = "Everest is the tallest mountain [1]."
    r = verify(answer, sources)
    assert r.ok is True
    assert r.missing == []


def test_partial_coverage_is_reported():
    sources = [{"id": "1", "text": "Bananas are berries botanically speaking."}]
    answer = "Bananas are berries botanically speaking [1]. Sky color is blue."
    r = verify(answer, sources)
    # 1 of 2 sentences is supported.
    assert r.coverage == pytest.approx(0.5)
    assert r.ok is False


def test_empty_answer_has_zero_coverage_and_is_ok_when_no_citations():
    r = verify("", [])
    # No claims, no missing -> trivially ok. Coverage = 0 because no sentences.
    assert r.ok is True
    assert r.coverage == 0.0
    assert r.missing == []
    assert r.unsupported == []


def test_brackets_that_arent_citations_are_ignored():
    # "[Note]" must not count as a citation, so this sentence is "no_citation".
    sources = [{"id": "1", "text": "Anything"}]
    answer = "Some claim [Note]."
    r = verify(answer, sources)
    assert r.ok is False
    assert r.unsupported[0].reason == "no_citation"


def test_support_threshold_is_tunable():
    sources = [{"id": "1", "text": "alpha beta gamma"}]
    answer = "alpha delta epsilon zeta [1]."
    # claim meaningful tokens: alpha, delta, epsilon, zeta -> overlap=1/4=0.25
    # default threshold 0.2 -> supported
    r_default = verify(answer, sources)
    assert r_default.ok is True
    # Tighten the threshold to 0.5 -> no longer supported.
    r_strict = verify(answer, sources, support_threshold=0.5)
    assert r_strict.ok is False
    assert r_strict.unsupported[0].reason == "insufficient_overlap"


def test_non_string_answer_raises():
    with pytest.raises(TypeError):
        verify(123, [])  # type: ignore[arg-type]


def test_none_answer_treated_as_empty():
    r = verify(None, [])  # type: ignore[arg-type]
    assert r.ok is True
    assert r.coverage == 0.0


def test_sources_can_be_omitted_for_unsupported_check():
    answer = "Standalone claim [1]."
    r = verify(answer, [])
    assert "1" in r.missing
    assert r.ok is False
