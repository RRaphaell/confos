"""Output rendering: JSON envelope, rich tables, plain TSV, graph emitters.

This layer knows how to *format* data for stdout. It never knows where the data
came from (ARCHITECTURE §4) — callers pass in already-computed results plus the
provenance to stamp.
"""
