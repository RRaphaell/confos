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
    """A readable org name derived from a domain (fallback when not in the seed)."""
    labels = domain.split(".")
    # Drop a leading ccTLD-style academic prefix and the public suffix labels.
    public = {"edu", "ac", "com", "org", "net", "gov", "co", "io", "ai"}
    core = [label for label in labels if label not in public and len(label) > 2]
    return core[0].capitalize() if core else domain


def org_from_email(email: str) -> tuple[str, str | None] | None:
    """Best-effort (org_name, country) from an email, or None if no domain.

    Returns a confident seed mapping when known; otherwise a derived name with a
    TLD-inferred country (which may be None).
    """
    domain = domain_from_email(email)
    if domain is None:
        return None
    if domain in _DOMAIN_ORG_SEED:
        return _DOMAIN_ORG_SEED[domain]
    return _registrable_name(domain), country_from_domain(domain)


def org_slug(name: str) -> str:
    """Stable id for an org: slug of its normalized name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"
