from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy.orm import Session

from .. import schemas
from ..models import Paper

try:
    from google import genai
    from google.genai import types
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    genai = None
    types = None

_CLIENT = None
_LOOKUP_DEBUG = os.getenv("LOOKUP_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


class NewsContact(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    website: Optional[str] = None
    primary_contact: Optional[str] = None
    chain_owner: Optional[str] = None
    county: Optional[str] = None
    publication_frequency: Optional[str] = None
    wikipedia_link: Optional[str] = None
    source_links: List[str] = []
    social_media_links: List[str] = []

    @field_validator("primary_contact", mode="before")
    @classmethod
    def _coerce_primary_contact(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            pieces: list[str] = []
            for item in value.values():
                if isinstance(item, str) and item.strip():
                    pieces.append(item.strip())
                elif item is not None:
                    pieces.append(str(item).strip())
            joined = ", ".join([piece for piece in pieces if piece])
            return joined or None
        if isinstance(value, list):
            pieces = [str(item).strip() for item in value if str(item).strip()]
            joined = ", ".join(pieces)
            return joined or None
        return str(value).strip() or None

    @field_validator(
        "name",
        "email",
        "phone",
        "mailing_address",
        "website",
        "wikipedia_link",
        "publication_frequency",
        "chain_owner",
        "county",
        mode="before",
    )
    @classmethod
    def _coerce_text_fields(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            pieces: list[str] = []
            for item in value.values():
                if isinstance(item, str) and item.strip():
                    pieces.append(item.strip())
                elif item is not None:
                    pieces.append(str(item).strip())
            joined = ", ".join([piece for piece in pieces if piece])
            return joined or None
        if isinstance(value, list):
            pieces = [str(item).strip() for item in value if str(item).strip()]
            joined = ", ".join(pieces)
            return joined or None
        return str(value).strip() or None

    @field_validator("source_links", "social_media_links", mode="before")
    @classmethod
    def _coerce_links(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, dict):
            items: list[str] = []
            for item in value.values():
                if item is None:
                    continue
                cleaned = str(item).strip()
                if cleaned:
                    items.append(cleaned)
            return items
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []
        return [str(value).strip()] if str(value).strip() else []

def _get_client():
    global _CLIENT
    if genai is None or types is None:
        raise RuntimeError("google-genai is not installed")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    if _CLIENT is None:
        _CLIENT = genai.Client(api_key=api_key)
    return _CLIENT


def _clean_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _is_missing(value: Optional[str]) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _normalize_links(values: List[str]) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()
    blocked_prefixes = ("https://vertexaisearch.cloud.google.com/grounding-api-redirect/",)
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if any(cleaned.startswith(prefix) for prefix in blocked_prefixes):
            continue
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    cleaned = value.strip()
    return cleaned or None


def _normalize_phone_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None

    pattern = re.compile(r"\+?1?[\s\-.()]*\d{3}[\s\-.()]*\d{3}[\s\-.()]*\d{4}")

    def _format_match(match: re.Match[str]) -> str:
        digits = "".join(ch for ch in match.group(0) if ch.isdigit())
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        return match.group(0)

    formatted = pattern.sub(_format_match, text)
    return formatted or None
def _build_prompt(paper: Paper) -> str:
    parts = [
        f"Newspaper name: {paper.paper_name}",
        f"City: {paper.city or 'Unknown'}",
        f"State: {paper.state or 'Unknown'}",
    ]
    if paper.website_url:
        parts.append(f"Website: {paper.website_url}")
    if paper.phone:
        parts.append(f"Existing phone: {paper.phone}")
    if paper.email:
        parts.append(f"Existing email: {paper.email}")
    if paper.mailing_address:
        parts.append(f"Existing mailing address: {paper.mailing_address}")
    if paper.county:
        parts.append(f"County: {paper.county}")
    details = "\n".join(parts)
    return (
        "Find the official editorial contact info for the newspaper listed below. "
        "Return JSON with keys: name, email, phone, mailing_address, website, primary_contact, chain_owner, county, publication_frequency, "
        "wikipedia_link, source_links, social_media_links. Use null for unknown values. "
        "For source_links, include only human-accessible public URLs (official site pages, press association listings, newsroom contact pages). "
        "For social_media_links, include official social media profile URLs only. "
        "Do not include API endpoints, Vertex/Google AI links, or tool/integration URLs.\n\n"
        f"{details}"
    )


def _extract_response_text(response) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    candidates = getattr(response, "candidates", None)
    if candidates:
        content = getattr(candidates[0], "content", None)
        parts = getattr(content, "parts", None) if content else None
        if parts and getattr(parts[0], "text", None):
            return parts[0].text
    raise RuntimeError("Lookup response did not include text output")


def _fetch_contact(paper: Paper) -> NewsContact:
    client = _get_client()
    prompt = _build_prompt(paper)
    if _LOOKUP_DEBUG:
        print(f"Lookup prompt for paper_id={paper.id}:\n{prompt}")
    config = types.GenerateContentConfig(
        system_instruction=(
            "You are a specialized researcher for media databases. "
            "Find official contact information for news organizations. "
            "Prioritize Wikipedia for history and Press Associations/Official 'About' pages for contacts. "
            "Always return a valid JSON object."
        ),
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"{prompt}\n\nReturn only a JSON object with the required keys.",
        config=config,
    )
    raw_text = _extract_response_text(response)
    if _LOOKUP_DEBUG:
        print(f"Lookup raw response for paper_id={paper.id}:\n{raw_text}")
    try:
        return NewsContact.model_validate_json(raw_text)
    except ValidationError:
        try:
            parsed = NewsContact.model_validate_json(raw_text[raw_text.find("{") : raw_text.rfind("}") + 1])
            return parsed
        except Exception as exc:
            raise RuntimeError(f"Lookup response validation failed: {exc}") from exc


def lookup_paper_contact(db: Session, paper: Paper) -> schemas.LookupResult:
    contact = _fetch_contact(paper)

    updates: Dict[str, Optional[str]] = {}
    if _is_missing(paper.phone) and contact.phone:
        updates["phone"] = _normalize_phone_text(contact.phone)
    if _is_missing(paper.email) and contact.email:
        updates["email"] = _clean_str(contact.email)
    if _is_missing(paper.mailing_address) and contact.mailing_address:
        updates["mailing_address"] = _clean_str(contact.mailing_address)
    if _is_missing(paper.website_url) and contact.website:
        updates["website_url"] = _clean_str(contact.website)
    if contact.publication_frequency:
        updates["publication_frequency"] = _clean_str(contact.publication_frequency)
    chain_owner_value = _clean_str(contact.chain_owner)
    if chain_owner_value is not None:
        updates["chain_owner"] = chain_owner_value
    if _is_missing(paper.county) and contact.county:
        updates["county"] = _clean_str(contact.county)

    for field, value in updates.items():
        setattr(paper, field, value)

    metadata: Dict[str, Any] = {
        "last_lookup_at": datetime.utcnow().isoformat(),
        "source_links": _normalize_links(contact.source_links or []),
        "wikipedia_link": _clean_str(contact.wikipedia_link),
        "primary_contact": _clean_str(contact.primary_contact),
        "contact_name": _clean_str(contact.name),
        "website": _clean_str(contact.website),
        "chain_owner": _clean_str(contact.chain_owner),
        "publication_frequency": _clean_str(contact.publication_frequency),
        "county": _clean_str(contact.county),
        "social_media_links": _normalize_links(contact.social_media_links or []),
        "phone": _normalize_phone_text(contact.phone),
        "email": _clean_str(contact.email),
        "mailing_address": _clean_str(contact.mailing_address),
    }

    extra = dict(paper.extra_data or {})
    extra["contact_lookup"] = metadata
    paper.extra_data = extra

    db.add(paper)
    db.commit()
    db.refresh(paper)

    return schemas.LookupResult(
        paper_id=paper.id,
        updated=bool(updates),
        phone=paper.phone,
        email=paper.email,
        mailing_address=paper.mailing_address,
        lookup_metadata=metadata,
    )
