"""Shared helpers for normalizing newspaper CSV data."""

from __future__ import annotations

import html
import re
from urllib.parse import urlsplit, urlunsplit
from typing import Any, Dict, Iterable, Iterator, Tuple

import pandas as pd

COLUMN_ALIASES: Dict[str, Iterable[str]] = {
    "state": ["state"],
    "city": ["city"],
    "paper_name": ["paper name", "name"],
    "website_url": ["website url", "url", "site", "website"],
    "phone": ["phone", "phone number"],
    "email": ["email", "e-mail"],
    "mailing_address": ["mailing address", "address"],
    "county": ["county"],
    "publication_frequency": ["publication frequency", "frequency"],
    "chain_owner": ["chain owner", "owner", "chain"],
    "cms_platform": ["cms platform", "platform"],
    "cms_vendor": ["cms vendor", "vendor"],
}

REQUIRED_FIELDS = {"paper_name", "website_url"}
BASE_FIELDS = [
    "state",
    "city",
    "paper_name",
    "website_url",
    "phone",
    "email",
    "mailing_address",
    "county",
    "publication_frequency",
    "chain_owner",
    "cms_platform",
    "cms_vendor",
]


_LEADING_ARTICLE_RE = re.compile(r"^(The|A|An)\s+(.+)$", flags=re.IGNORECASE)
_TRAILING_ARTICLE_RE = re.compile(r"^(.+),\s*(The|A|An)$", flags=re.IGNORECASE)


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    column_lookup = {col.lower(): col for col in frame.columns}
    rename_map: Dict[str, str] = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            lower_alias = alias.lower()
            if lower_alias in column_lookup:
                rename_map[column_lookup[lower_alias]] = canonical
                break

    normalized = frame.rename(columns=rename_map)
    for field in COLUMN_ALIASES.keys():
        if field not in normalized.columns:
            normalized[field] = None

    return normalized


def clean_value(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_paper_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", html.unescape(value).strip())
    if not cleaned:
        return None

    trailing_match = _TRAILING_ARTICLE_RE.match(cleaned)
    if trailing_match:
        base = trailing_match.group(1).strip()
        article = trailing_match.group(2).title()
        return f"{base}, {article}" if base else None

    leading_match = _LEADING_ARTICLE_RE.match(cleaned)
    if leading_match:
        article = leading_match.group(1).title()
        base = leading_match.group(2).strip()
        return f"{base}, {article}" if base else None

    return cleaned


def paper_name_match_key(value: str | None) -> str:
    normalized = normalize_paper_name(value)
    if not normalized:
        return ""

    lowered = normalized.lower().strip()
    trailing_match = _TRAILING_ARTICLE_RE.match(lowered)
    if trailing_match:
        lowered = trailing_match.group(1).strip()

    lowered = re.sub(r"\s+", " ", lowered)
    return lowered


def normalize_website_url(value: str | None) -> str | None:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
        raw = f"https://{raw}"

    parsed = urlsplit(raw)
    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").lower()
    if "@" in netloc:
        netloc = netloc.split("@", 1)[1]
    if ":" in netloc:
        host, port = netloc.rsplit(":", 1)
        if (scheme == "https" and port == "443") or (scheme == "http" and port == "80"):
            netloc = host

    path = re.sub(r"/+", "/", parsed.path or "").rstrip("/")
    normalized = urlunsplit((scheme, netloc, path, "", "")).strip()
    return normalized or None


def website_url_match_key(value: str | None) -> str:
    normalized = normalize_website_url(value)
    if not normalized:
        return ""

    parsed = urlsplit(normalized)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = (parsed.path or "").rstrip("/")
    return f"{host}{path}".lower()


def build_lookup_key(data: Dict[str, str | None]) -> Tuple[str, str, str]:
    return (
        paper_name_match_key(data.get("paper_name")),
        (data.get("city") or "").strip().lower(),
        (data.get("state") or "").strip().lower(),
    )


def iter_normalized_rows(frame: pd.DataFrame) -> Iterator[Tuple[Dict[str, str | None], Dict[str, Any]]]:
    known_fields = set(COLUMN_ALIASES.keys())

    for _, row in frame.iterrows():
        data = {field: clean_value(row.get(field)) for field in known_fields}
        data["paper_name"] = normalize_paper_name(data.get("paper_name"))
        data["website_url"] = normalize_website_url(data.get("website_url"))

        extras: Dict[str, Any] = {}
        for column in row.index:
            if column in known_fields:
                continue
            value = clean_value(row.get(column))
            if value is not None:
                extras[column] = value

        contact_keys = {"primary contact", "primary_contact", "editor", "editor name"}
        contact_value = None
        for key in list(extras.keys()):
            if key.strip().lower() in contact_keys:
                contact_value = extras.pop(key)
                break
        if contact_value:
            contact_lookup = {}
            existing_lookup = extras.get("contact_lookup")
            if isinstance(existing_lookup, dict):
                contact_lookup.update(existing_lookup)
            contact_lookup["primary_contact"] = contact_value
            extras["contact_lookup"] = contact_lookup

        data["extra_data"] = extras if extras else None
        yield data, extras
