"""Services: orchestration and the business "verbs" (ARCHITECTURE §4).

Services coordinate adapters (fetch) and repositories (read/write) and own ranking and
aggregation. They never import typer and never embed SQL strings.
"""
