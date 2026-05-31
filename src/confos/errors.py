"""Typed errors mapped to stable exit codes (see CLI_CONTRACT §5).

The whole error story is intentionally small: a handful of exception types, each
carrying the exit code an agent or script can branch on. Higher ``--verbose`` shows
the full traceback; by default the user sees a single clean line.
"""

from __future__ import annotations

# Exit codes (CLI_CONTRACT §5). 130 = interrupted, handled at the top level.
EXIT_OK = 0
EXIT_GENERIC = 1
EXIT_USAGE = 2
EXIT_CONFIG = 3
EXIT_NETWORK = 4
EXIT_PARTIAL = 5
EXIT_INTERRUPTED = 130


class ConfosError(Exception):
    """Base for every expected confos failure.

    ``exit_code`` becomes the process exit status; ``error_type`` is the stable
    machine-readable label echoed in the ``--json`` error envelope.
    """

    exit_code: int = EXIT_GENERIC
    error_type: str = "error"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class UsageError(ConfosError):
    """Invalid invocation or argument validation failure."""

    exit_code = EXIT_USAGE
    error_type = "usage"


class ConfigError(ConfosError):
    """Configuration or environment problem (bad home dir, missing FTS5, ...)."""

    exit_code = EXIT_CONFIG
    error_type = "config"


class NotFoundError(ConfosError):
    """A requested entity (venue, paper, author) isn't present locally."""

    exit_code = EXIT_GENERIC
    error_type = "not_found"


class NetworkError(ConfosError):
    """Network or upstream-backend failure (OpenReview unreachable, etc.)."""

    exit_code = EXIT_NETWORK
    error_type = "network"


class PartialIngestError(ConfosError):
    """Ingest completed but some items failed — the dataset is incomplete."""

    exit_code = EXIT_PARTIAL
    error_type = "partial_ingest"
