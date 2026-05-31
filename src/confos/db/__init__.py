"""Storage layer: SQLite connection, schema migration, typed repositories.

Repositories own SQL and never make network calls (ARCHITECTURE §4). The raw JSONL
snapshots are the truth; this database is a derived, rebuildable index.
"""
