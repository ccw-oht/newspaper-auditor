from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError
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


class NewsContact(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    website: Optional[str] = None
    primary_contact: Optional[str] = None
    wikipedia_link: Optional[str] = None
    source_links: List[str] = []


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
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


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
    details = "\n".join(parts)
    return (
        "Find the official editorial contact info for the newspaper listed below. "
        "Return JSON with keys: name, email, phone, mailing_address, website, primary_contact, "
        "wikipedia_link, source_links. Use null for unknown values.\n\n"
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
        updates["phone"] = _clean_str(contact.phone)
    if _is_missing(paper.email) and contact.email:
        updates["email"] = _clean_str(contact.email)
    if _is_missing(paper.mailing_address) and contact.mailing_address:
        updates["mailing_address"] = _clean_str(contact.mailing_address)

    for field, value in updates.items():
        setattr(paper, field, value)

    metadata: Dict[str, Any] = {
        "last_lookup_at": datetime.utcnow().isoformat(),
        "source_links": _normalize_links(contact.source_links or []),
        "wikipedia_link": _clean_str(contact.wikipedia_link),
        "primary_contact": _clean_str(contact.primary_contact),
        "contact_name": _clean_str(contact.name),
        "website": _clean_str(contact.website),
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
