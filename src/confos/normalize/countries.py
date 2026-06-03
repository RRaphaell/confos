"""Best-effort country inference from a domain TLD or a profile's ISO country code.

Two signals feed this: an email/institution **domain** (ccTLD heuristic, the v1 path) and a
profile's explicit **ISO 3166-1 alpha-2** country code (``history[].institution.country``,
the Phase-1 path — authoritative, no domain-guessing). Everything we can't resolve returns
``None`` (Unknown), counted honestly by the stats layer.
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


# ISO 3166-1 alpha-2 → display name. Profiles store the institution country as an explicit
# two-letter code, which is far more reliable than guessing from a domain. Names match the
# ccTLD map's style ("United States", "United Kingdom", "South Korea") so both signals
# aggregate into the same buckets in stats/trends.
_ISO_ALPHA2_COUNTRY: dict[str, str] = {
    "US": "United States",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "CN": "China",
    "DE": "Germany",
    "FR": "France",
    "CA": "Canada",
    "CH": "Switzerland",
    "JP": "Japan",
    "KR": "South Korea",
    "IN": "India",
    "IL": "Israel",
    "NL": "Netherlands",
    "SG": "Singapore",
    "AU": "Australia",
    "SE": "Sweden",
    "IT": "Italy",
    "ES": "Spain",
    "AT": "Austria",
    "BE": "Belgium",
    "DK": "Denmark",
    "FI": "Finland",
    "NO": "Norway",
    "IE": "Ireland",
    "PT": "Portugal",
    "PL": "Poland",
    "CZ": "Czech Republic",
    "GR": "Greece",
    "HU": "Hungary",
    "RO": "Romania",
    "RU": "Russia",
    "UA": "Ukraine",
    "TR": "Turkey",
    "BR": "Brazil",
    "MX": "Mexico",
    "AR": "Argentina",
    "CL": "Chile",
    "CO": "Colombia",
    "ZA": "South Africa",
    "EG": "Egypt",
    "SA": "Saudi Arabia",
    "AE": "United Arab Emirates",
    "QA": "Qatar",
    "IR": "Iran",
    "PK": "Pakistan",
    "BD": "Bangladesh",
    "ID": "Indonesia",
    "MY": "Malaysia",
    "TH": "Thailand",
    "VN": "Vietnam",
    "PH": "Philippines",
    "HK": "Hong Kong",
    "TW": "Taiwan",
    "NZ": "New Zealand",
    "LU": "Luxembourg",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "HR": "Croatia",
    "RS": "Serbia",
    "BG": "Bulgaria",
    "EE": "Estonia",
    "LV": "Latvia",
    "LT": "Lithuania",
    "IS": "Iceland",
    "CY": "Cyprus",
    "MT": "Malta",
    "LB": "Lebanon",
    "JO": "Jordan",
    "KW": "Kuwait",
    "MA": "Morocco",
    "TN": "Tunisia",
    "NG": "Nigeria",
    "KE": "Kenya",
    "ET": "Ethiopia",
    "GH": "Ghana",
    "PE": "Peru",
    "EC": "Ecuador",
    "UY": "Uruguay",
    "CR": "Costa Rica",
    "KZ": "Kazakhstan",
    "UZ": "Uzbekistan",
    "AM": "Armenia",
    "GE": "Georgia",
    "AZ": "Azerbaijan",
    "LK": "Sri Lanka",
    "NP": "Nepal",
    "MO": "Macau",
}


def country_from_iso_alpha2(code: str | None) -> str | None:
    """Map an ISO 3166-1 alpha-2 code to a display name (case-insensitive), else None."""
    if not code:
        return None
    return _ISO_ALPHA2_COUNTRY.get(code.strip().upper())
