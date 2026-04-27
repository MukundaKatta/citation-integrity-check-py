# citation-integrity-check

[![PyPI](https://img.shields.io/pypi/v/citation-integrity-check.svg)](https://pypi.org/project/citation-integrity-check/)
[![Python](https://img.shields.io/pypi/pyversions/citation-integrity-check.svg)](https://pypi.org/project/citation-integrity-check/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Verify answer citations refer to supplied source ids and that cited sources actually support the claims.** Zero runtime dependencies.

Python port of [@mukundakatta/citation-integrity-check](https://github.com/MukundaKatta/citation-integrity-check). The JS sibling has the original API; this README sticks to the Python surface.

## Install

```bash
pip install citation-integrity-check
```

## Usage

```python
from citation_integrity_check import verify

sources = [
    {"id": "1", "text": "Photosynthesis converts light into chemical energy in plants."},
    {"id": "abc123", "text": "Chlorophyll absorbs red and blue wavelengths of light."},
]
answer = (
    "Plants use photosynthesis to convert light into energy [1]. "
    "Chlorophyll absorbs red and blue light [id:abc123]."
)

result = verify(answer, sources)

result.ok            # True if no missing ids and no unsupported claims
result.missing       # list[str]    -- cited ids that don't exist in sources
result.unsupported   # list[Claim]  -- sentences with no valid supporting citation
result.coverage      # float in [0, 1] -- fraction of sentences with a valid citation
```

## Citation forms

Two markers are recognized inside the answer:

| Form         | Resolves to                                          |
|--------------|------------------------------------------------------|
| `[1]`        | `sources[0]` (1-based index) **and** `source.id == "1"` |
| `[id:abc]`   | `source.id == "abc"`                                 |

Anything else inside brackets (like `[Note]`) is ignored, so stylistic prose doesn't count as a citation.

## How "unsupported" is decided

A sentence is unsupported when **any** of these is true:

- It has no citation marker at all (`reason="no_citation"`).
- All cited ids are missing from `sources` (`reason="missing_source"`).
- The cited source's text doesn't share enough non-stopword tokens with the sentence (`reason="insufficient_overlap"`).

Token-overlap is `|claim_tokens & source_tokens| / |claim_tokens|`, with a small built-in stopword list. The threshold is tunable:

```python
verify(answer, sources, support_threshold=0.5)  # stricter
```

## API differences from the JS sibling

* Returns a `CitationResult` dataclass with `unsupported` claims (per-sentence) instead of the JS `unused` ids list.
* Adds the `[id:foo]` named-citation form alongside numeric `[N]`.
* Adds the token-overlap `support_threshold` to verify the cited source actually mentions the claim.

See the JS sibling's [README](https://github.com/MukundaKatta/citation-integrity-check) for the full design notes.
