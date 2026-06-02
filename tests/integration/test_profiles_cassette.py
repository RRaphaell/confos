"""Profile fetch against RECORDED OpenReview profiles (vcrpy replay, no network in CI).

Proves the real OpenReviewAdapter resolves an author handle anonymously and parses the
``history``/links shape this codebase relies on. Recorded with two well-known handles.
Re-record with::

    CONFOS_RECORD=1 uv run pytest tests/integration/test_profiles_cassette.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
import vcr

from confos.adapters.openreview import OpenReviewAdapter

CASSETTE_DIR = Path(__file__).parent.parent / "fixtures" / "cassettes"
CASSETTE = "profiles.yaml"
HANDLES = ["~Nora_Belrose1", "~Yoshua_Bengio1"]

# Keep only the profile content confos actually reads; drop everything else (emails,
# relations, metaContent, password, ACLs) so the committed cassette holds no needless
# personal data beyond the public affiliation/links these researchers chose to publish.
_KEEP_CONTENT = {"history", "homepage", "gscholar", "dblp", "expertise"}


def _scrub_profiles(response: dict[str, Any]) -> dict[str, Any]:
    raw = response.get("body", {}).get("string")
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    if not isinstance(text, str):
        return response
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return response
    for profile in payload.get("profiles", []) if isinstance(payload, dict) else []:
        content = profile.get("content")
        if isinstance(content, dict):
            profile["content"] = {k: v for k, v in content.items() if k in _KEEP_CONTENT}
        for drop in ("metaContent", "password", "readers", "writers", "signatures", "nonreaders"):
            profile.pop(drop, None)
    scrubbed = json.dumps(payload)
    response["body"]["string"] = scrubbed.encode("utf-8") if isinstance(raw, bytes) else scrubbed
    return response


_recording = bool(os.environ.get("CONFOS_RECORD"))
_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode="once" if _recording else "none",
    match_on=["method", "host", "path", "query"],
    filter_headers=["authorization", "cookie", "set-cookie"],
    before_record_response=_scrub_profiles,
    decode_compressed_response=True,
)

pytestmark = pytest.mark.skipif(
    not _recording and not (CASSETTE_DIR / CASSETTE).exists(),
    reason="cassette not recorded; run with CONFOS_RECORD=1 once (needs network)",
)


def test_fetch_profiles_parses_real_profiles() -> None:
    adapter = OpenReviewAdapter()
    with _vcr.use_cassette(CASSETTE):
        fetched = list(adapter.fetch_profiles(HANDLES))  # sequential → deterministic replay
    results = {handle: (snap, status) for handle, snap, status in fetched}

    assert set(results) == set(HANDLES)
    for handle in HANDLES:
        snapshot, status = results[handle]
        assert status == "found", handle
        assert snapshot is not None and snapshot["id"] == handle
        history = snapshot["content"].get("history")
        assert isinstance(history, list) and history
        # At least one career entry carries a normalizable institution (name/domain).
        assert any(
            isinstance(h.get("institution"), dict)
            and (h["institution"].get("name") or h["institution"].get("domain"))
            for h in history
        )
