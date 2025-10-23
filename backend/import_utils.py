"""Shared helpers for normalizing newspaper CSV data."""

from __future__ import annotations

from typing import Dict, Iterable, Iterator, Tuple

import pandas as pd

COLUMN_ALIASES: Dict[str, Iterable[str]] = {
    "state": ["state"],
    "city": ["city"],
    "paper_name": ["paper name", "name"],
    "website_url": ["website url", "url", "site", "website"],
    "phone": ["phone", "phone number"],
    "mailing_address": ["mailing address", "address"],
    "county": ["county"],
    "chain_owner": ["chain owner", "owner", "chain"],
    "cms_platform": ["cms platform", "platform"],
    "cms_vendor": ["cms vendor", "vendor"],
}

REQUIRED_FIELDS = {"city", "paper_name"}
BASE_FIELDS = [
    "state",
    "city",
    "paper_name",
    "website_url",
    "phone",
    "mailing_address",
    "county",
    "chain_owner",
    "cms_platform",
    "cms_vendor",
]


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


def build_lookup_key(data: Dict[str, str | None]) -> Tuple[str, str, str]:
    return (
        (data.get("paper_name") or "").strip().lower(),
        (data.get("city") or "").strip().lower(),
        (data.get("state") or "").strip().lower(),
    )


def iter_normalized_rows(frame: pd.DataFrame) -> Iterator[Tuple[Dict[str, str | None], Dict[str, str]]]:
    known_fields = set(COLUMN_ALIASES.keys())

    for _, row in frame.iterrows():
        data = {field: clean_value(row.get(field)) for field in known_fields}

        extras: Dict[str, str] = {}
        for column in row.index:
            if column in known_fields:
                continue
            value = clean_value(row.get(column))
            if value is not None:
                extras[column] = value

        data["extra_data"] = extras if extras else None
        yield data, extras
