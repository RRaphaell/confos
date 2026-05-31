"""Source adapters: fetch from a source, return normalized objects + raw payloads.

Adapters never write the database and never know about other adapters (ARCHITECTURE §4).
v1 ships only ``openreview``; the :class:`~confos.adapters.base.SourceAdapter` Protocol is
the seam that lets AIE/PMLR/OpenAlex slot in later without a rewrite (D10).
"""
