"""Command layer (typer).

Commands parse arguments and format output — they hold no business logic and never
talk to adapters or repositories directly (ARCHITECTURE §4). Each calls exactly one
service and renders its result in the requested mode (human / --json / --plain).
"""
