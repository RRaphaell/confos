"""Command layer (typer).

Commands parse arguments and format output — they hold no business logic and never
talk to adapters or repositories directly (ARCHITECTURE §4). Each calls exactly one
service (from Phase 1 on); for now several are honest "not implemented yet" stubs that
keep the full ``--help`` tree visible while phases land.
"""
