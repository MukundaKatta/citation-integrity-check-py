"""citation_integrity_check -- verify answer citations against supplied sources.

Public surface (Python port of the JS sibling):

    from citation_integrity_check import verify, CitationResult, Claim

* ``verify(answer, sources)`` -- returns a :class:`CitationResult` with
  missing ids, unsupported claims, and per-sentence citation coverage.
* ``CitationResult`` -- structured result dataclass.
* ``Claim`` -- per-sentence claim record (sentence text + cited ids).

Citations may be plain ``[1]`` / ``[2]`` numeric references that resolve to
``sources`` by 1-based index OR by ``source.id`` equality, or named
``[id:abc123]`` references that match ``source.id`` directly.

Zero runtime dependencies, stdlib only.
"""

from .verify import Claim, CitationResult, verify

__version__ = "0.1.0"
VERSION = __version__

__all__ = [
    "VERSION",
    "Claim",
    "CitationResult",
    "verify",
]
