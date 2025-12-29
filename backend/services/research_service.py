from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..models import Paper, ResearchFeature, ResearchSession, ResearchSessionPaper
from ..audit import check_sitemap, fetch_url


@dataclass
class PaperArtifacts:
    homepage_text: Optional[str]
    homepage_url: Optional[str]
    rss_entries: List[Dict[str, str]]
    sitemap_urls: List[str]
    errors: List[str]


def _normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    trimmed = url.strip()
    if not trimmed:
        return None
    if trimmed.startswith("http://") or trimmed.startswith("https://"):
        return trimmed
    return f"https://{trimmed.lstrip('/')}"


def _snapshot_from_paper(paper: Paper) -> Dict[str, Any]:
    return {
        "id": paper.id,
        "state": paper.state,
        "city": paper.city,
        "paper_name": paper.paper_name,
        "website_url": paper.website_url,
        "phone": paper.phone,
        "email": paper.email,
        "mailing_address": paper.mailing_address,
        "county": paper.county,
        "chain_owner": paper.chain_owner,
        "cms_platform": paper.cms_platform,
        "cms_vendor": paper.cms_vendor,
        "extra_data": paper.extra_data,
    }


def _collect_rss_entries(base_url: str, limit: int = 50) -> List[Dict[str, str]]:
    from urllib.parse import urlencode, urlparse, urlunparse
    import xml.etree.ElementTree as ET

    rss_paths = ["/feed", "/rss", "/rss.xml", "/index.rss"]
    entries: list[dict[str, str]] = []
    seen_links: set[str] = set()

    trimmed = base_url.rstrip("/")
    candidates = [trimmed + path for path in rss_paths]
    parsed = urlparse(base_url)
    if parsed.netloc:
        path_segments = [segment for segment in parsed.path.strip("/").split("/") if segment]
        if path_segments:
            slug = path_segments[-1]
            query = urlencode(
                {
                    "f": "rss",
                    "t": "article",
                    "c": slug,
                    "l": "50",
                    "s": "start_time",
                    "sd": "desc",
                }
            )
            scheme = parsed.scheme or "https"
            alt_url = urlunparse((scheme, parsed.netloc, "/search/", "", query, ""))
            candidates.append(alt_url)

    for candidate in candidates:
        text, status, _ = fetch_url(candidate, timeout=8)
        if status != 200 or not text:
            continue
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            continue
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "").strip()
            if not link:
                guid = (item.findtext("guid") or "").strip()
                link = guid
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            entries.append({"title": title, "link": link, "description": description})
            if len(entries) >= limit:
                return entries

        atom_ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(f".//{atom_ns}entry"):
            title = (entry.findtext(f"{atom_ns}title") or "").strip()
            link = ""
            for link_elem in entry.findall(f"{atom_ns}link"):
                rel = link_elem.attrib.get("rel")
                if rel in (None, "alternate"):
                    link = link_elem.attrib.get("href", "").strip()
                    if link:
                        break
            summary = (entry.findtext(f"{atom_ns}summary") or "").strip()
            if not link or link in seen_links:
                continue
            seen_links.add(link)
            entries.append({"title": title, "link": link, "description": summary})
            if len(entries) >= limit:
                return entries

    return entries


def _collect_artifacts_for_paper(snapshot: Dict[str, Any]) -> PaperArtifacts:
    base_url = _normalize_url(snapshot.get("website_url"))
    homepage_text = None
    homepage_url = base_url
    errors: list[str] = []
    if base_url:
        homepage_text, status, err = fetch_url(base_url, timeout=10, allow_brotli=True)
        if status != 200 or not homepage_text:
            errors.append(err or f"homepage status {status}")
            homepage_text = None
    sitemap_urls: list[str] = []
    if base_url:
        sitemap_result = check_sitemap(base_url)
        sitemap_urls = sitemap_result.get("urls") or []
    rss_entries: list[dict[str, str]] = []
    if base_url:
        rss_entries = _collect_rss_entries(base_url)
    return PaperArtifacts(
        homepage_text=homepage_text,
        homepage_url=homepage_url,
        rss_entries=rss_entries,
        sitemap_urls=sitemap_urls,
        errors=errors,
    )


def _match_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for keyword in keywords:
        cleaned = keyword.strip().lower()
        if not cleaned:
            continue
        if cleaned in lowered:
            matches.append(keyword)
    return matches


def _excerpt_for_match(text: str, keyword: str, window: int = 120) -> str:
    lowered = text.lower()
    idx = lowered.find(keyword.lower())
    if idx == -1:
        snippet = text[: window * 2]
        return snippet.strip()
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    snippet = text[start:end]
    return snippet.strip()


def _build_evidence(
    snapshot: Dict[str, Any],
    artifacts: PaperArtifacts,
    keywords: list[str],
    desired: int,
) -> list[schemas.ResearchEvidenceItem]:
    evidence: list[schemas.ResearchEvidenceItem] = []
    normalized_keywords = [kw for kw in (k.strip() for k in keywords) if kw]
    if not normalized_keywords:
        return evidence

    # Homepage scan
    if artifacts.homepage_text and artifacts.homepage_url:
        homepage_matches = _match_keywords(artifacts.homepage_text, normalized_keywords)
        if homepage_matches:
            excerpt = _excerpt_for_match(artifacts.homepage_text, homepage_matches[0])
            evidence.append(
                schemas.ResearchEvidenceItem(
                    paper_id=snapshot.get("id"),
                    paper_name=snapshot.get("paper_name"),
                    source_type="homepage",
                    title=f"{snapshot.get('paper_name') or 'Paper'} Homepage",
                    url=artifacts.homepage_url,
                    excerpt=excerpt,
                    matched_keywords=homepage_matches,
                )
            )
    if len(evidence) >= desired:
        return evidence[:desired]

    # RSS entries
    for entry in artifacts.rss_entries:
        entry_text = " ".join([entry.get("title") or "", entry.get("description") or ""])
        matches = _match_keywords(entry_text, normalized_keywords)
        if matches:
            evidence.append(
                schemas.ResearchEvidenceItem(
                    paper_id=snapshot.get("id"),
                    paper_name=snapshot.get("paper_name"),
                    source_type="rss",
                    title=entry.get("title"),
                    url=entry.get("link"),
                    excerpt=(entry.get("description") or "")[:280],
                    matched_keywords=matches,
                )
            )
        if len(evidence) >= desired:
            return evidence[:desired]

    # Sitemap URLs
    for url in artifacts.sitemap_urls:
        matches = _match_keywords(url, normalized_keywords)
        if matches:
            evidence.append(
                schemas.ResearchEvidenceItem(
                    paper_id=snapshot.get("id"),
                    paper_name=snapshot.get("paper_name"),
                    source_type="sitemap",
                    title=url,
                    url=url,
                    excerpt=None,
                    matched_keywords=matches,
                )
            )
        if len(evidence) >= desired:
            break

    return evidence[:desired]


def create_research_session(
    db: Session, payload: schemas.ResearchSessionCreateRequest
) -> ResearchSession:
    unique_ids = sorted({int(pid) for pid in payload.paper_ids if pid is not None})
    if not unique_ids:
        raise ValueError("No paper IDs provided")

    stmt: Select[tuple[Paper]] = select(Paper).where(Paper.id.in_(unique_ids))
    papers = db.execute(stmt).scalars().all()
    if not papers:
        raise ValueError("No matching papers found")

    session = ResearchSession(
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        filter_params=payload.filter_params or {},
        query_string=payload.query_string,
    )

    for paper in papers:
        session.papers.append(
            ResearchSessionPaper(
                paper=paper,
                snapshot=_snapshot_from_paper(paper),
            )
        )

    desired_features = payload.features or []
    for feature in desired_features:
        keywords = [kw.strip() for kw in feature.keywords if kw and kw.strip()]
        if not keywords:
            continue
        session.features.append(
            ResearchFeature(
                name=feature.name.strip() or "Untitled Feature",
                keywords=keywords,
                desired_examples=max(1, min(feature.desired_examples, 50)),
            )
        )

    if not session.features:
        session.features.append(
            ResearchFeature(
                name="General Coverage",
                keywords=["news"],
                desired_examples=5,
            )
        )

    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_research_sessions(db: Session) -> list[schemas.ResearchSessionSummary]:
    stmt = (
        select(
            ResearchSession,
            func.count(ResearchSessionPaper.id).label("paper_count"),
            func.count(ResearchFeature.id).label("feature_count"),
        )
        .outerjoin(ResearchSessionPaper, ResearchSession.papers)
        .outerjoin(ResearchFeature, ResearchSession.features)
        .group_by(ResearchSession.id)
        .order_by(ResearchSession.created_at.desc())
    )
    rows = db.execute(stmt).all()
    summaries: list[schemas.ResearchSessionSummary] = []
    for row in rows:
        session: ResearchSession = row[0]
        paper_count = row[1]
        feature_count = row[2]
        summaries.append(
            schemas.ResearchSessionSummary(
                id=session.id,
                name=session.name,
                description=session.description,
                created_at=session.created_at,
                updated_at=session.updated_at,
                filter_params=session.filter_params or {},
                query_string=session.query_string,
                paper_count=paper_count,
                feature_count=feature_count,
            )
        )
    return summaries


def get_research_session(db: Session, session_id: int) -> schemas.ResearchSessionDetail:
    session = db.get(ResearchSession, session_id)
    if not session:
        raise ValueError("Research session not found")

    papers = [
        schemas.ResearchSessionPaper(
            id=paper.id,
            paper_id=paper.paper_id,
            snapshot=paper.snapshot or {},
        )
        for paper in sorted(session.papers, key=lambda p: (p.snapshot or {}).get("paper_name") or "")
    ]

    features = [
        schemas.ResearchFeature(
            id=feature.id,
            session_id=session.id,
            name=feature.name,
            keywords=feature.keywords or [],
            desired_examples=feature.desired_examples,
            status=feature.status,
            last_evaluated_at=feature.last_evaluated_at,
            evidence=feature.evidence or {},
            error=feature.error,
        )
        for feature in session.features
    ]

    return schemas.ResearchSessionDetail(
        id=session.id,
        name=session.name,
        description=session.description,
        created_at=session.created_at,
        updated_at=session.updated_at,
        filter_params=session.filter_params or {},
        query_string=session.query_string,
        papers=papers,
        features=features,
    )


def run_feature_scans(
    db: Session, session_id: int, feature_ids: Optional[list[int]] = None, paper_ids: Optional[list[int]] = None
) -> list[schemas.ResearchFeature]:
    session = db.get(ResearchSession, session_id)
    if not session:
        raise ValueError("Research session not found")

    selected_features: list[ResearchFeature]
    if feature_ids:
        selected_features = [f for f in session.features if f.id in feature_ids]
    else:
        selected_features = list(session.features)

    if not selected_features:
        raise ValueError("No features found for session")

    selected_papers: list[ResearchSessionPaper]
    if paper_ids:
        paper_id_set = {int(pid) for pid in paper_ids}
        selected_papers = [p for p in session.papers if p.id in paper_id_set]
        if not selected_papers:
            raise ValueError("No matching papers found for this session")
    else:
        selected_papers = list(session.papers)

    artifact_cache: dict[int, PaperArtifacts] = {}

    results: list[schemas.ResearchFeature] = []
    for feature in selected_features:
        feature.status = "running"
        db.add(feature)
    db.commit()

    for feature in selected_features:
        try:
            matches: list[schemas.ResearchEvidenceItem] = []
            desired = feature.desired_examples or 5
            for paper in selected_papers:
                if paper.id not in artifact_cache:
                    artifact_cache[paper.id] = _collect_artifacts_for_paper(paper.snapshot or {})
                artifacts = artifact_cache[paper.id]
                paper_matches = _build_evidence(paper.snapshot or {}, artifacts, feature.keywords or [], desired)
                matches.extend(paper_matches)
                if len(matches) >= desired:
                    break

            feature.evidence = {"matches": [match.dict() for match in matches[:desired]]}
            feature.status = "completed"
            feature.last_evaluated_at = datetime.utcnow()
            feature.error = None
            db.add(feature)
        except Exception as exc:  # pragma: no cover - network heavy path
            feature.status = "error"
            feature.error = str(exc)
            feature.last_evaluated_at = datetime.utcnow()
            feature.evidence = {"matches": []}
            db.add(feature)
        db.commit()
        results.append(
            schemas.ResearchFeature(
                id=feature.id,
                session_id=session.id,
                name=feature.name,
                keywords=feature.keywords or [],
                desired_examples=feature.desired_examples,
                status=feature.status,
                last_evaluated_at=feature.last_evaluated_at,
                evidence=feature.evidence or {},
                error=feature.error,
            )
        )

    return results
