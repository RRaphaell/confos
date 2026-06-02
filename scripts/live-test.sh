#!/usr/bin/env bash
#
# Opt-in live smoke test against the REAL OpenReview API.
#
# CI never hits the network (it replays a recorded cassette). This script is the manual
# counterpart: it ingests one small, stable venue (ICLR 2025 MLMP workshop, ~33 papers)
# for real and exercises the offline query surface on top of it, asserting exit codes and
# non-empty results. Run it before a release, or after touching the OpenReview adapter.
#
#   ./scripts/live-test.sh
#
# Uses an isolated, throwaway CONFOS_HOME (removed on exit). Override the binary with
# e.g. CONFOS="confos" to test an installed build instead of the working tree.

set -euo pipefail

CONFOS="${CONFOS:-uv run confos}"
VENUE_ID="ICLR.cc/2025/Workshop/MLMP"
MIN_PAPERS=30

HOME_DIR="$(mktemp -d "${TMPDIR:-/tmp}/confos-live.XXXXXX")"
export CONFOS_HOME="$HOME_DIR"
trap 'rm -rf "$HOME_DIR"' EXIT

note() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[31mFAIL:\033[0m %s\n' "$*" >&2; exit 1; }

# Evaluate a Python expression against a confos --json envelope on stdin, where the
# parsed object is bound to `d` (no jq dependency).
jget() { python3 -c "import sys,json; d=json.load(sys.stdin); print(eval(sys.argv[1]))" "$1"; }

note "confos --version"
$CONFOS --version

note "init store at $CONFOS_HOME"
$CONFOS init >/dev/null

note "ingest $VENUE_ID (LIVE network)"
INGEST_JSON="$($CONFOS ingest "$VENUE_ID" --json)"
STATUS="$(printf '%s' "$INGEST_JSON" | jget "d['data']['status']")"
SEEN="$(printf '%s' "$INGEST_JSON" | jget "d['data']['items_seen']")"
SLUG="$(printf '%s' "$INGEST_JSON" | jget "d['data']['venue']")"
echo "  status=$STATUS seen=$SEEN slug=$SLUG"
[ "$STATUS" = "ok" ] || fail "ingest status was '$STATUS', expected 'ok'"
[ "$SEEN" -ge "$MIN_PAPERS" ] || fail "ingested $SEEN papers, expected >= $MIN_PAPERS"

note "index status"
$CONFOS index status --json >/dev/null || fail "index status failed"

note "enrich profiles --venue $SLUG --limit 15 (LIVE network, resumable; ~20/min limit)"
ENRICH_JSON="$($CONFOS enrich profiles --venue "$SLUG" --limit 15 --json)"
FETCHED="$(printf '%s' "$ENRICH_JSON" | jget "d['data']['fetched']")"
echo "  fetched=$FETCHED profile(s)"
[ "$FETCHED" -ge 1 ] || fail "enrich fetched 0 profiles, expected >= 1"
ORG_COV="$($CONFOS stats orgs --venue "$SLUG" --explain --json | jget "d['data']['data_quality']['papers_with_signal']")"
echo "  orgs coverage after enrich: $ORG_COV"
[ "$ORG_COV" -ge 1 ] || fail "orgs coverage still 0 after enrich"

note "papers search 'neural' --venue $SLUG"
N="$($CONFOS papers search "neural" --venue "$SLUG" --json | jget "len(d['data'])")"
echo "  $N result(s)"
[ "$N" -ge 1 ] || fail "expected >= 1 search result for 'neural'"

note "authors find --topic 'learning' --venue $SLUG"
$CONFOS authors find --topic "learning" --venue "$SLUG" --json >/dev/null || fail "authors find failed"

note "stats overview --venue $SLUG"
$CONFOS stats overview --venue "$SLUG" --json >/dev/null || fail "stats overview failed"

note "export context --topic 'neural' --venue $SLUG"
PACK_TYPE="$($CONFOS export context --topic "neural" --venue "$SLUG" --json | jget "d['data']['type']")"
[ "$PACK_TYPE" = "confos.context_pack" ] || fail "context pack type was '$PACK_TYPE'"

note "viz network --topic 'neural' --venue $SLUG --format mermaid"
$CONFOS viz network --topic "neural" --venue "$SLUG" --format mermaid >/dev/null || fail "viz network failed"

printf '\n\033[32mLIVE TEST PASSED\033[0m — ingested %s papers from %s and ran the query surface.\n' "$SEEN" "$SLUG"
