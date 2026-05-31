# Name Conflict Check: `confos`

**Date:** 2026-05-23
**Purpose:** Verify the `confos` name is clear enough to claim before we scaffold a repo and start publishing under it.

---

## Method

Two web searches:

1. `"confos" CLI tool software project github`
2. `"confos" software OR conference OR npm OR pypi`

Plus mental scan of common collisions (Spanish "confos" slang, abbreviations, etc.).

---

## Findings

### Software namespace: clear

| Namespace | Result |
|---|---|
| PyPI | No package named `confos` |
| npm | No package named `confos` |
| GitHub | No repository at `github.com/*/confos` matching our category |
| Common-name CLI | No CLI tool of that name surfaced in search |

This is the namespace that matters most for a CLI: the package install and the repo URL. Both are clean.

### Brand-collision: ConFoo (Montreal)

The only meaningful collision is **ConFoo** (`confoo.ca`), a long-running developer conference held in Montreal. It's well-known in the Canadian/Quebec dev community and has run since around 2009.

Differences from `confos`:

- **Spelling:** `confoo` (double-o) vs `confos` (terminal -s). Visually distinct.
- **Category:** ConFoo is an *event*, confos is a *tool*. Different cognitive bucket.
- **Domain:** `confoo.ca` is taken; `confos.dev` / `confos.io` / equivalents are likely available (not yet checked).

Risk: when speaking the name aloud, especially with a non-native English speaker or a noisy environment, "confos" and "confoo" sound similar. A non-zero fraction of listeners will assume we're talking about the Montreal conference until corrected. The reverse is also true — ConFoo attendees may stumble onto our repo and wonder if it's affiliated.

This is annoying but not disqualifying. The lived experience of having a name partially overlap with another developer-community brand is normal (think `Conf` vs `Confluent`, `Air` vs `Airflow`, etc.). We disambiguate when it matters.

### Other words checked

- **`confs`** — no major collision; sometimes used informally as "configs" or "conferences" shorthand.
- **`confer`** — common English word; verbs are bad CLI names.
- **`papers`** — already used as PyPI and shell utility names.
- **`venue`** — too generic.
- **`paperos`** — available, but more paper-centric than conference-centric.

---

## Recommendation

**Proceed with `confos`.** The package, repo, and CLI namespace is open. The ConFoo conference is the only notable brand overlap, and it's distant enough (different category, different spelling) to be a marketing-level annoyance, not a structural problem.

If ConFoo ever becomes a real issue (e.g., we get sustained "is this the Montreal conference?" confusion), the fallback names worth considering are `paperos`, `venueos`, or `confcli`. For now, ship under `confos`.

---

## Open items

- [ ] Check domain availability: `confos.dev`, `confos.io`, `confos.sh`.
- [ ] Check that `confos` isn't a registered trademark in any relevant jurisdiction (low risk for a 6-char invented word, but worth a quick USPTO/EUIPO search before we put it on slides or a website).
- [ ] Reserve PyPI name early — `pip install confos` should resolve to us. PyPI lets you reserve a name with an empty 0.0.0 release.

---

## Sources

- [ConFoo developer conference (Montreal)](https://confoo.ca/en/2010/top)
- [conference-radar (PyPI)](https://pypi.org/project/conference-radar/)
- [conference-scheduler (PyPI)](https://pypi.org/project/conference-scheduler/)
- [conference (npm)](https://www.npmjs.com/package/conference)
