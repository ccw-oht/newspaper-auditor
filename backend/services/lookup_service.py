from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from urllib.parse import urljoin, urlparse
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from pydantic import AliasChoices, BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..models import Audit, Paper

try:
    from google import genai
    from google.genai import types
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    genai = None
    types = None

_CLIENT = None
_LOOKUP_DEBUG = os.getenv("LOOKUP_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
_LOOKUP_REQUEST_DELAY_SECONDS = float(os.getenv("LOOKUP_REQUEST_DELAY_SECONDS", "0.2"))
_LOOKUP_THROTTLE_LOCK = threading.Lock()
_LOOKUP_NEXT_TIME = 0.0
_LOOKUP_MAX_ATTEMPTS = int(os.getenv("LOOKUP_MAX_ATTEMPTS", "5"))
_LOOKUP_BACKOFF_SECONDS = float(os.getenv("LOOKUP_BACKOFF_SECONDS", "1.5"))
_LOOKUP_BACKOFF_MAX_SECONDS = float(os.getenv("LOOKUP_BACKOFF_MAX_SECONDS", "12"))


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
    source_links: List[str] = Field(default_factory=list, validation_alias=AliasChoices("source_links", "relevant_source_links"))
    social_media_links: List[str] = Field(default_factory=list)

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


def _canonicalize_social_link(url: str) -> Optional[str]:
    if not url:
        return None
    cleaned = url.strip()
    if not cleaned:
        return None
    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    parsed = urlparse(cleaned)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    query = parsed.query or ""

    generic_handles = {
        "facebook": {"facebook", "fb", "facebookapp", "facebookads"},
        "twitter": {"twitter", "x", "home", "share"},
        "instagram": {"instagram", "ig", "reel", "reels"},
        "youtube": {"youtube", "channel", "c", "user"},
        "tiktok": {"tiktok"},
        "pinterest": {"pinterest"},
        "linkedin": {"linkedin"},
        "bluesky": {"bluesky"},
    }

    if "facebook.com" in host:
        lowered_path = path.lower()
        if "/sharer.php" in lowered_path or "/share.php" in lowered_path or "/sharer/sharer.php" in lowered_path:
            return None
        if lowered_path.startswith("/share"):
            return None
        if lowered_path.startswith("/sharer"):
            return None
        if lowered_path.startswith("/dialog"):
            return None
        if lowered_path.startswith("/plugins/"):
            return None
        if any(
            token in lowered_path
            for token in ["/posts/", "/photos/", "/videos/", "/reel/", "/reels/", "/watch", "/events/", "/permalink.php", "/story.php"]
        ):
            return None
        if lowered_path in {"", "/"}:
            return None
        canonical_path = re.sub(r"/+$", "", lowered_path)
        if canonical_path in {"/facebook", "/fb", "/facebookapp", "/facebookads"}:
            return None
        if canonical_path.startswith("/pages/") or canonical_path.startswith("/profile.php"):
            return f"https://www.facebook.com{canonical_path}"
        if canonical_path.count("/") == 1:
            return f"https://www.facebook.com{canonical_path}"
        return None

    if "twitter.com" in host or host == "x.com" or host.endswith(".x.com"):
        lowered_path = path.lower()
        if lowered_path.startswith("/intent/"):
            return None
        if any(
            lowered_path.startswith(prefix)
            for prefix in ["/share", "/search", "/home", "/i/", "/hashtag", "/status/"]
        ):
            return None
        if lowered_path in {"", "/"}:
            return None
        canonical_path = re.sub(r"/+$", "", lowered_path)
        handle = canonical_path.lstrip("/").split("/")[0]
        if handle in generic_handles["twitter"]:
            return None
        if canonical_path.count("/") > 1:
            return None
        return f"https://twitter.com{canonical_path}"

    if "instagram.com" in host:
        lowered_path = path.lower()
        if any(lowered_path.startswith(prefix) for prefix in ["/p/", "/reel/", "/tv/", "/stories/"]):
            return None
        if lowered_path in {"", "/"}:
            return None
        canonical_path = re.sub(r"/+$", "", lowered_path)
        handle = canonical_path.lstrip("/").split("/")[0]
        if handle in generic_handles["instagram"]:
            return None
        if canonical_path.count("/") > 1:
            return None
        return f"https://www.instagram.com{canonical_path}"

    if "linkedin.com" in host:
        lowered_path = path.lower()
        if lowered_path in {"", "/"}:
            return None
        canonical_path = re.sub(r"/+$", "", lowered_path)
        handle = canonical_path.lstrip("/").split("/")[0]
        if handle in generic_handles["linkedin"]:
            return None
        if not any(canonical_path.startswith(prefix) for prefix in ["/company/", "/in/", "/school/"]):
            return None
        return f"https://www.linkedin.com{canonical_path}"

    if "youtube.com" in host or "youtu.be" in host:
        lowered_path = path.lower()
        if any(lowered_path.startswith(prefix) for prefix in ["/watch", "/shorts", "/playlist"]):
            return None
        if lowered_path in {"", "/"}:
            return None
        if not any(lowered_path.startswith(prefix) for prefix in ["/@", "/channel/", "/c/", "/user/"]):
            return None
        handle = lowered_path.lstrip("/").split("/")[0]
        if handle in generic_handles["youtube"]:
            return None
        return cleaned

    if "tiktok.com" in host:
        lowered_path = path.lower()
        if "/video/" in lowered_path or lowered_path.startswith("/t/"):
            return None
        if lowered_path in {"", "/"}:
            return None
        canonical_path = re.sub(r"/+$", "", lowered_path)
        handle = canonical_path.lstrip("/").split("/")[0]
        if handle in generic_handles["tiktok"]:
            return None
        if not canonical_path.startswith("/@"):
            return None
        return f"https://www.tiktok.com{canonical_path}"

    if "bsky.app" in host or "bsky.social" in host or "bluesky" in host:
        lowered_path = path.lower()
        if lowered_path.startswith("/intent/"):
            return None
        if lowered_path in {"", "/"}:
            return None
        handle = lowered_path.lstrip("/").split("/")[0]
        if handle in generic_handles["bluesky"]:
            return None
        return cleaned

    if "pinterest.com" in host or host == "pin.it":
        lowered_path = path.lower()
        if "/pin/create" in lowered_path or "/pin/create/" in lowered_path:
            return None
        if lowered_path in {"", "/"}:
            return None
        canonical_path = re.sub(r"/+$", "", lowered_path)
        handle = canonical_path.lstrip("/").split("/")[0]
        if handle in generic_handles["pinterest"]:
            return None
        if canonical_path.count("/") > 1:
            return None
        return f"https://www.pinterest.com{canonical_path}"

    return None


def _normalize_social_href(href: str, base_url: Optional[str]) -> Optional[str]:
    if not href:
        return None
    cleaned = href.strip()
    if not cleaned:
        return None
    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    elif cleaned.startswith("/") and base_url:
        cleaned = urljoin(base_url, cleaned)
    return cleaned


def _is_social_link(url: str) -> bool:
    lowered = url.lower()
    return any(
        token in lowered
        for token in [
            "facebook.com",
            "fb.com",
            "instagram.com",
            "linkedin.com",
            "youtube.com",
            "youtu.be",
            "tiktok.com",
            "twitter.com",
            "x.com",
            "bsky.app",
            "bsky.social",
            "bluesky",
            "pinterest.com",
            "pin.it",
        ]
    )


def _extract_social_links_from_html(html: str | None, base_url: Optional[str]) -> List[str]:
    if not html:
        return []
    links: List[str] = []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("a"):
        for attr in ("href", "data-href", "data-url"):
            raw = tag.get(attr)
            if not isinstance(raw, str):
                continue
            normalized = _normalize_social_href(raw, base_url)
            if normalized and _is_social_link(normalized):
                links.append(normalized)
    return _normalize_links(links)


def _normalize_social_links(values: List[str]) -> List[str]:
    canonical: List[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        mapped = _canonicalize_social_link(value)
        if not mapped:
            continue
        if mapped in seen:
            continue
        seen.add(mapped)
        canonical.append(mapped)
    return canonical


def _partition_social_links(values: List[str]) -> tuple[List[str], List[str]]:
    social: List[str] = []
    non_social: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        canonical = _canonicalize_social_link(value)
        if canonical:
            social.append(canonical)
            continue
        if _is_social_link(value):
            continue
        non_social.append(value)
    return social, non_social


def _social_links_from_latest_audit(db: Session, paper: Paper) -> List[str]:
    stmt = (
        select(Audit.homepage_html)
        .where(Audit.paper_id == paper.id)
        .order_by(Audit.timestamp.desc())
        .limit(1)
    )
    homepage_html = db.execute(stmt).scalar_one_or_none()
    return _extract_social_links_from_html(homepage_html, paper.website_url)


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


def _usage_metadata_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    fields = [
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "tool_use_prompt_token_count",
        "thoughts_token_count",
    ]
    payload: dict[str, Any] = {}
    for field in fields:
        value = getattr(usage, field, None)
        if value is not None:
            payload[field] = value
    return payload


def _coerce_query_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []
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
        "Find the official contact info for the newspaper listed below. "
        "Return JSON with keys: name, email, phone, mailing_address, website, primary_contact, chain_owner, county, publication_frequency, "
        "wikipedia_link, social_media_links, and relevant source_links, . Use null for unknown values. "
        "For source_links, include only human-accessible public URLs (official site pages, press association listings, newsroom contact pages). "
        "For social_media_links, include ONLY the MOST RELEVANT official social media profile URL only — one for each found platform, and exclude associated chain/group or parent company pages. "
        "Keep the number of search queries to 5 or less if possible."
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


def _is_overload_error(exc: Exception) -> bool:
    message = str(exc)
    lowered = message.lower()
    return "503" in message or "unavailable" in lowered or "overloaded" in lowered


def _is_retryable_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if _is_overload_error(exc):
        return True
    return "did not include text output" in message


def _fetch_contact(paper: Paper, *, throttle: bool = True) -> tuple[NewsContact, dict[str, Any]]:
    if throttle and _LOOKUP_REQUEST_DELAY_SECONDS > 0:
        global _LOOKUP_NEXT_TIME
        with _LOOKUP_THROTTLE_LOCK:
            now = time.monotonic()
            if now < _LOOKUP_NEXT_TIME:
                time.sleep(_LOOKUP_NEXT_TIME - now)
            jitter = _LOOKUP_REQUEST_DELAY_SECONDS * 0.25
            _LOOKUP_NEXT_TIME = max(now, _LOOKUP_NEXT_TIME) + _LOOKUP_REQUEST_DELAY_SECONDS + random.uniform(0, jitter)

    client = _get_client()
    prompt = _build_prompt(paper)
    if _LOOKUP_DEBUG:
        print(f"Lookup prompt for paper_id={paper.id}:\n{prompt}")
    system_instruction = (
        "You are a specialized researcher for media databases. "
        "Find official contact information for news organizations. "
        "Prioritize Wikipedia for history and Press Associations/Official 'About' pages for contacts. "
        "Always return a valid JSON object."
    )
    contents = f"{prompt}\n\nReturn only a JSON object with the required keys."
    model_name = "gemini-3-flash-preview"
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )
    last_error: Exception | None = None
    max_attempts = max(1, _LOOKUP_MAX_ATTEMPTS)
    response = None
    raw_text = ""
    contact: NewsContact | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            usage = getattr(response, "usage_metadata", None)
            candidates = getattr(response, "candidates", None)
            candidate = candidates[0] if candidates else None
            grounding = getattr(candidate, "grounding_metadata", None) if candidate else None
            finish_reason = getattr(candidate, "finish_reason", None) if candidate else None
            if _LOOKUP_DEBUG:
                debug_payload = {
                    "paper_id": paper.id,
                    "usage_metadata": usage,
                    "finish_reason": finish_reason,
                    "web_search_queries": getattr(grounding, "web_search_queries", None) if grounding else None,
                }
                print(f"Lookup metadata: {json.dumps(debug_payload, default=str)}")
            raw_text = _extract_response_text(response)
            if _LOOKUP_DEBUG:
                print(f"Lookup raw response for paper_id={paper.id}:\n{raw_text}")
            try:
                contact = NewsContact.model_validate_json(raw_text)
            except ValidationError:
                contact = NewsContact.model_validate_json(raw_text[raw_text.find("{") : raw_text.rfind("}") + 1])
            break
        except Exception as exc:  # pragma: no cover - runtime-specific error handling
            last_error = exc
            if _LOOKUP_DEBUG:
                print(
                    f"Lookup attempt {attempt}/{max_attempts} failed for paper_id={paper.id}: {exc}"
                )
            if not _is_retryable_error(exc) or attempt >= max_attempts:
                raise
            backoff = min(_LOOKUP_BACKOFF_SECONDS * (2 ** (attempt - 1)), _LOOKUP_BACKOFF_MAX_SECONDS)
            jitter = backoff * 0.25
            time.sleep(backoff + random.uniform(0, jitter))
    else:  # pragma: no cover - defensive
        raise RuntimeError(f"Lookup failed after {max_attempts} attempts") from last_error
    usage = getattr(response, "usage_metadata", None) if response else None
    candidates = getattr(response, "candidates", None) if response else None
    candidate = candidates[0] if candidates else None
    grounding = getattr(candidate, "grounding_metadata", None) if candidate else None
    usage_payload = _usage_metadata_dict(usage)
    queries = _coerce_query_list(getattr(grounding, "web_search_queries", None) if grounding else None)
    finish_reason = getattr(candidate, "finish_reason", None) if candidate else None
    if contact is None:
        raise RuntimeError("Lookup response validation failed without output")
    if usage_payload:
        setattr(contact, "_usage_metadata", usage_payload)
    if queries:
        setattr(contact, "_web_search_queries", queries)
    logs: dict[str, Any] = {
        "prompt": prompt,
        "request_contents": contents,
        "system_instruction": system_instruction,
        "model": model_name,
        "raw_response": raw_text,
    }
    if usage_payload:
        logs["usage_metadata"] = usage_payload
    if queries:
        logs["web_search_queries"] = queries
    if finish_reason is not None:
        logs["finish_reason"] = finish_reason
    return contact, logs


def _lookup_paper_contact(
    db: Session,
    paper: Paper,
    *,
    throttle: bool = True,
) -> tuple[schemas.LookupResult, dict[str, Any]]:
    contact, logs = _fetch_contact(paper, throttle=throttle)
    usage = getattr(contact, "_usage_metadata", None)
    queries = getattr(contact, "_web_search_queries", None)

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

    source_social, source_links = _partition_social_links(contact.source_links or [])
    existing_lookup = paper.extra_data.get("contact_lookup") if isinstance(paper.extra_data, dict) else None
    existing_social_links: List[str] = []
    if isinstance(existing_lookup, dict):
        existing_value = existing_lookup.get("social_media_links")
        if isinstance(existing_value, list):
            existing_social_links = [item for item in existing_value if isinstance(item, str)]
    homepage_social_links = _social_links_from_latest_audit(db, paper)
    merged_social_links = _normalize_social_links(
        existing_social_links + (contact.social_media_links or []) + homepage_social_links + source_social
    )

    for field, value in updates.items():
        setattr(paper, field, value)

    metadata: Dict[str, Any] = {
        "last_lookup_at": datetime.utcnow().isoformat(),
        "source_links": _normalize_links(source_links),
        "wikipedia_link": _clean_str(contact.wikipedia_link),
        "primary_contact": _clean_str(contact.primary_contact),
        "contact_name": _clean_str(contact.name),
        "website": _clean_str(contact.website),
        "chain_owner": _clean_str(contact.chain_owner),
        "publication_frequency": _clean_str(contact.publication_frequency),
        "county": _clean_str(contact.county),
        "social_media_links": merged_social_links,
        "phone": _normalize_phone_text(contact.phone),
        "email": _clean_str(contact.email),
        "mailing_address": _clean_str(contact.mailing_address),
    }
    if logs:
        metadata["logs"] = logs
    if usage:
        metadata["usage_metadata"] = usage
    if queries:
        metadata["web_search_queries"] = queries

    extra = dict(paper.extra_data or {})
    extra["contact_lookup"] = metadata
    paper.extra_data = extra

    db.add(paper)
    db.commit()
    db.refresh(paper)

    result = schemas.LookupResult(
        paper_id=paper.id,
        updated=bool(updates),
        phone=paper.phone,
        email=paper.email,
        mailing_address=paper.mailing_address,
        lookup_metadata=metadata,
    )
    return result, logs


def lookup_paper_contact(db: Session, paper: Paper, *, throttle: bool = True) -> schemas.LookupResult:
    result, _ = _lookup_paper_contact(db, paper, throttle=throttle)
    return result


def lookup_paper_contact_with_logs(
    db: Session,
    paper: Paper,
    *,
    throttle: bool = True,
) -> tuple[schemas.LookupResult, dict[str, Any]]:
    return _lookup_paper_contact(db, paper, throttle=throttle)
