"""Best-effort organisation inference from an email domain (v1).

The reliable org signal in a submission note is an author's *email* domain (present only
when an authorid is a raw email rather than a tilde profile id — the minority at major
venues). v1 maps a small seed of well-known domains to a display name + country, and
otherwise derives a readable name from the registrable domain. Phase 3 replaces this with
profile-history affiliations + a user-editable ``aliases/orgs.yml`` and reports
known/unknown/low-confidence coverage.
"""

from __future__ import annotations

import re

from .countries import country_from_domain

# Seed map: email domain → (display name, country). Small + high-confidence by design.
_DOMAIN_ORG_SEED: dict[str, tuple[str, str]] = {
    "mit.edu": ("MIT", "United States"),
    "stanford.edu": ("Stanford University", "United States"),
    "berkeley.edu": ("UC Berkeley", "United States"),
    "cmu.edu": ("Carnegie Mellon University", "United States"),
    "washington.edu": ("University of Washington", "United States"),
    "google.com": ("Google", "United States"),
    "deepmind.com": ("Google DeepMind", "United Kingdom"),
    "microsoft.com": ("Microsoft", "United States"),
    "meta.com": ("Meta", "United States"),
    "fb.com": ("Meta", "United States"),
    "openai.com": ("OpenAI", "United States"),
    "anthropic.com": ("Anthropic", "United States"),
    "nvidia.com": ("NVIDIA", "United States"),
    "ox.ac.uk": ("University of Oxford", "United Kingdom"),
    "cam.ac.uk": ("University of Cambridge", "United Kingdom"),
    "ethz.ch": ("ETH Zurich", "Switzerland"),
    "tsinghua.edu.cn": ("Tsinghua University", "China"),
    "pku.edu.cn": ("Peking University", "China"),
}

_EMAIL_RE = re.compile(r"^[^@]+@(.+)$")


def domain_from_email(email: str) -> str | None:
    """Extract the lowercased domain from an email address, or None."""
    match = _EMAIL_RE.match(email.strip().lower())
    return match.group(1) if match else None


def _registrable_name(domain: str) -> str:
    """Fallback org name for an unseeded domain: the domain itself.

    We keep the raw domain (e.g. ``nus.edu.sg``) rather than a mangled title-case of one
    label (``Nus``), which reads like a bug. It is honestly "derived from the email
    domain"; Phase 3 maps domains to real display names via the alias file.
    """
    return domain


def org_from_email(
    email: str,
    *,
    org_aliases: dict[str, str] | None = None,
    country_aliases: dict[str, str] | None = None,
) -> tuple[str, str | None] | None:
    """Best-effort (org_name, country) from an email, or None if no domain.

    Resolution order: user ``orgs.yml`` alias (highest priority) → built-in seed →
    derived-from-domain. Country comes from ``countries.yml`` (by domain or org name)
    else the domain TLD.
    """
    domain = domain_from_email(email)
    if domain is None:
        return None
    org_aliases = org_aliases or {}
    country_aliases = country_aliases or {}

    def _country(name: str) -> str | None:
        return (
            country_aliases.get(domain)
            or country_aliases.get(name.lower())
            or country_from_domain(domain)
        )

    if domain in org_aliases:
        name = org_aliases[domain]
        return name, _country(name)
    if domain in _DOMAIN_ORG_SEED:
        return _DOMAIN_ORG_SEED[domain]
    derived = _registrable_name(domain)
    return derived, _country(derived)


def org_slug(name: str) -> str:
    """Stable id for an org: slug of its normalized name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"
