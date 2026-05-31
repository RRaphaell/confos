"""Best-effort country inference from an email/institution domain (v1).

Country data is genuinely sparse and messy (research §10). v1 infers only from a small,
high-confidence set of country-code TLDs; everything else returns ``None`` (Unknown),
counted honestly by the stats layer. Phase 3 adds the user-editable alias file and
profile-based signals.
"""

from __future__ import annotations

# A deliberately small, high-confidence ccTLD → country map. Not exhaustive by design.
_CCTLD_COUNTRY: dict[str, str] = {
    "uk": "United Kingdom",
    "cn": "China",
    "jp": "Japan",
    "de": "Germany",
    "fr": "France",
    "ca": "Canada",
    "ch": "Switzerland",
    "kr": "South Korea",
    "in": "India",
    "il": "Israel",
    "nl": "Netherlands",
    "sg": "Singapore",
    "au": "Australia",
    "se": "Sweden",
    "it": "Italy",
    "es": "Spain",
}


def country_from_domain(domain: str) -> str | None:
    """Infer a country from a domain's TLD. ``.edu``/``.com``/etc. → None (ambiguous)."""
    if not domain or "." not in domain:
        return None
    labels = domain.lower().rstrip(".").split(".")
    tld = labels[-1]
    if tld == "edu":
        return "United States"  # .edu is overwhelmingly US institutions
    # ".ac.uk", ".edu.cn" etc.: the ccTLD is the last label.
    return _CCTLD_COUNTRY.get(tld)
