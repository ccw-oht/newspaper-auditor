import argparse
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urlunparse, urlencode

# Keywords/signals
paywall_keywords = [
    "subscribe",
    "paywall",
    "metered",
    "membership",
    "premium",
    "registration",
]
public_notice_keywords = [
    "public notice",
    "legal notice",
    "legals",
    "notices",
    "obituaries",
]
pdf_homepage_keywords = [
    "e-edition",
    "eedition",
    "e edition",
    "epaper",
    "e-paper",
    "digital edition",
    "digital replica",
    "digital-version",
    "digital version",
    "replica edition",
    "enewspaper",
    "e-newspaper",
    "printed paper",
    "epost",
    "e-post",
    "e post",
    "print archive",
]
pdf_href_keywords = [
    "eedition",
    "epaper",
    "e-edition",
    "enewspaper",
    "digitaledition",
    "digital-version",
    "digital version",
    "replica",
    "print-edition",
    "epost",
    "e-post",
    "newsmemory",
    "magazine",
    "special=",
    "print archive"
]

article_href_keywords = [
    "article",
    "story",
    "news",
    "sports",
    "business",
    "lifestyle",
    "politics",
    "community",
    "feature",
    "opinion",
    "entertainment",
    "/202",
]

article_class_keywords = [
    "article",
    "story",
    "news",
    "post",
    "entry",
    "card",
]

cms_platform_signatures = [
    ("Creative Circle", ["creativecircle", "circle-media", "circleid", "/stories/", "creativecirclecdn"]),
    ("BLOX Digital", ["tncms", "bloximages", "townnews", "bloxcms"]),
    ("WordPress", ["wp-content", "wp-includes", "wordpress", "wp-json", "wp-sitemap"]),
    ("Drupal", ["drupal.settings", "drupal-settings-json", "drupal"]),
    ("Arc XP", ["arc-cdn", "arcpublishing", "thearc", "arc publishing", "washpost"]),
    ("Flatpage/Flatpack", ["flatpage", "flatpack", "wehaa"]),
    ("Presto", ["presto-content", "gannett-cdn", "gdn-presto", "gannettdigital"]),
    ("eType", ["etype.services", "etype1", "etype services"]),
    ("Ellington CMS", ["ellingtoncms"]),
    ("Brightspot", ["brightspot", "bybrightspot"]),
    ("NewsPack", ["newspack", "wpengine"]),
    ("Tecnavia", ["tecnavia", "newsmemory"]),
]

cms_vendor_signatures = [
    ("Creative Circle", ["creativecircle", "circle-media", "circleid", "/stories/", "creativecirclecdn"]),
    ("ePublishing", ["epublishing", "epubcorp", "epublishing.com", "cld.bz", "ellingtoncms"]),
    ("eType", ["etype.services", "etype services", "etype1"]),
    ("Lion's Light", ["lionslight", "lion's light", "lions-light"]),
    ("Surf New Media", ["surfnewmedia", "snmportal", "surf new media"]),
    ("Websites For Newspapers", ["websitesfornewspapers", "wfnpro", "wfnp"]),
    ("BLOX", ["tncms", "bloximages", "townnews", "bloxcms"]),
    ("Gannett", ["gannett", "gannett-cdn", "gannettdigital", "presto-content"]),
    ("NewsPack", ["newspack", "wpengine"]),
    ("StuffSites", ["stuffsites", "stuff sites"]),
    ("PubGenAI", ["pubgenai", "pubgen.ai", "pubgen"]),
    ("Arc Publishing", ["arc-cdn", "arcpublishing", "thearc", "arc publishing"]),
    ("Brightspot", ["brightspot", "bybrightspot"]),
    ("Our Hometown Web Publishing", ["our-hometown", "ourhometown", "oht-"]),
    ("Indiegraf Media", ["indiegrafmedia", "indiegraf", "indiegraf media"]),
]

# Snapshot limits
MAX_SNAPSHOT_CHARS = 500_000

# Output directory for generated audit CSVs (project_root/audits)
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "audits"

# Helper utilities
def sanitize_homepage_snapshot(
    html: str | None, max_chars: int = MAX_SNAPSHOT_CHARS
) -> tuple[str | None, bool]:
    if not html:
        return None, False

    cleaned = html.strip().replace("\x00", "")  # guard against null bytes in HTML
    if len(cleaned) > max_chars:
        return cleaned[:max_chars], True
    return cleaned, False


# Helper: fetch a URL safely, capturing status information
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/118.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # Requests does not decode Brotli by default, so omit br to avoid binary responses.
    "Accept-Encoding": "gzip, deflate",
}

REQUEST_PAUSE_SECONDS = 0.75
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


class HomepageFetchTimeoutError(RuntimeError):
    """Raised when the homepage request exhausts retries due to a timeout."""

    def __init__(self, url: str, detail: str | None = None, status_code: int | None = None):
        self.url = url
        self.status_code = status_code
        message_detail = (detail or "Request timed out").strip()
        self.detail = message_detail
        super().__init__(f"Homepage fetch timed out for {url}: {message_detail}")


def _is_timeout_error(status_code: int | None, error_message: str | None) -> bool:
    if status_code in {408, 504, 522, 524}:
        return True
    if not error_message:
        return False
    lowered = error_message.lower()
    return ("timed out" in lowered) or ("timeout" in lowered)


def _prefer_https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def fetch_url(url, timeout=8, headers=None, retries=2, backoff=1.5, raise_on_timeout: bool = False):
    headers = headers or DEFAULT_HEADERS
    last_error = None
    current_url = url
    for attempt in range(retries + 1):
        try:
            resp = requests.get(current_url, timeout=timeout, headers=headers, allow_redirects=True)
            if resp.status_code == 403 and current_url.startswith("http://"):
                # retry once with https if forbidden over http
                https_url = "https://" + current_url[len("http://"):]
                current_url = https_url
                continue
            if resp.status_code == 403 and attempt < retries:
                last_error = f"HTTP 403 for {current_url}"
                time.sleep(backoff * (attempt + 1))
                continue
            if resp.status_code == 429 and attempt < retries:
                last_error = f"HTTP 429 for {current_url}"
                time.sleep(backoff * (attempt + 1))
                continue
            if resp.status_code == 200:
                return resp.text, resp.status_code, None
            last_error = f"HTTP {resp.status_code}"
            return None, resp.status_code, None
        except requests.exceptions.Timeout as exc:
            last_error = str(exc)
            if raise_on_timeout:
                raise HomepageFetchTimeoutError(current_url, last_error) from exc
            if attempt == retries:
                return None, None, last_error
        except Exception as exc:
            last_error = str(exc)
            if attempt == retries:
                return None, None, last_error
    return None, None, last_error

# Helper: check sitemap.xml
def check_sitemap(base_url):
    sitemap_paths = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-news.xml"]
    pdf_count, total = 0, 0
    notices_found = False
    urls = []
    used = False

    for path in sitemap_paths:
        sitemap_url = base_url.rstrip("/") + path
        xml_text, status_code, _ = fetch_url(sitemap_url, timeout=12)
        if status_code != 200 or not xml_text:
            continue
        used = True

        try:
            root = ET.fromstring(xml_text)
            for elem in root.iter():
                if elem.tag.endswith("loc") and elem.text:
                    loc = elem.text.lower()
                    urls.append(loc)
                    total += 1
                    if loc.endswith(".pdf"):
                        pdf_count += 1
                    if any(k in loc for k in public_notice_keywords):
                        notices_found = True
        except Exception:
            continue

    return {
        "pdf_ratio": pdf_count / total if total else 0,
        "notices": notices_found,
        "used": used,
        "urls": urls
    }

# Helper: check RSS feed
def check_rss(base_url):
    rss_paths = ["/feed", "/rss", "/rss.xml", "/index.rss"]
    feed_found, paywall_hint, notices_found = False, False, False
    entry_count = 0
    pdf_entry_count = 0

    base_trimmed = base_url.rstrip('/')
    candidates: list[str] = [base_trimmed + path for path in rss_paths]

    parsed = urlparse(base_url)
    if parsed.netloc:
        path_segments = [segment for segment in parsed.path.strip('/').split('/') if segment]
        if path_segments:
            slug = path_segments[-1]
            query = urlencode({
                "f": "rss",
                "t": "article",
                "c": slug,
                "l": "50",
                "s": "start_time",
                "sd": "desc",
            })
            scheme = parsed.scheme or "https"
            alt_url = urlunparse((scheme, parsed.netloc, "/search/", "", query, ""))
            candidates.append(alt_url)

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        xml_text, status_code, _ = fetch_url(candidate, timeout=8)
        if status_code != 200 or not xml_text:
            continue

        feed_found = True
        xml_lower = xml_text.lower()
        if any(k in xml_lower for k in paywall_keywords):
            paywall_hint = True
        if any(k in xml_lower for k in public_notice_keywords):
            notices_found = True

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            root = None

        if root is not None:
            for item in root.findall('.//item'):
                link_text = None
                link_elem = item.find('link')
                if link_elem is not None and link_elem.text:
                    link_text = link_elem.text.strip()
                if not link_text:
                    guid_elem = item.find('guid')
                    if guid_elem is not None and guid_elem.text:
                        link_text = guid_elem.text.strip()
                if not link_text:
                    enclosure = item.find('enclosure')
                    if enclosure is not None:
                        link_text = enclosure.attrib.get('url') or enclosure.attrib.get('href')
                if link_text:
                    entry_count += 1
                    lowered_link = link_text.lower()
                    if lowered_link.endswith('.pdf') or any(keyword in lowered_link for keyword in pdf_href_keywords):
                        pdf_entry_count += 1

            atom_ns = '{http://www.w3.org/2005/Atom}'
            for entry in root.findall(f'.//{atom_ns}entry'):
                href = None
                for link in entry.findall(f'{atom_ns}link'):
                    rel = link.attrib.get('rel')
                    if rel in (None, 'alternate'):
                        href = link.attrib.get('href')
                        if href:
                            break
                if not href:
                    id_elem = entry.find(f'{atom_ns}id')
                    if id_elem is not None and id_elem.text:
                        href = id_elem.text.strip()
                if href:
                    entry_count += 1
                    lowered_href = href.lower()
                    if lowered_href.endswith('.pdf') or any(keyword in lowered_href for keyword in pdf_href_keywords):
                        pdf_entry_count += 1

        break  # first valid feed is enough

    return {
        "feed_found": feed_found,
        "paywall_hint": paywall_hint,
        "notices": notices_found,
        "entry_count": entry_count,
        "pdf_entry_count": pdf_entry_count,
    }

# --- Feature Detectors ---

def detect_chain(homepage_html):
    if not homepage_html:
        return "Independent", [], ["No homepage HTML available"]

    html_lower = homepage_html.lower()
    chain_patterns = {
        "Gannett": [
            "part of the usa today network",
            "usa today",
            "gannett",
        ],
        "Hearst": ["hearst newspapers", "© hearst", "hearst media"],
        "Lee": ["lee enterprises", "lee enterprises inc"],
        "CNHI": ["cnhi llc", "cnhi media"],
        "McClatchy": ["mcclatchy"],
        "Ogden": ["ogden newspapers", "ogdennews"],
        "Adams Publishing": ["adams publishing group", "apgnews"],
    }

    for chain, tokens in chain_patterns.items():
        matches = [token for token in tokens if token in html_lower]
        if matches:
            note = f"Detected chain indicators ({chain}): {', '.join(matches)}"
            return chain, ["Homepage"], [note]

    return "Independent", [], []


def detect_cms(homepage_html, sitemap_data):
    if not homepage_html:
        return "Manual Review", "Manual Review", [], ["No homepage HTML available"]

    html_lower = homepage_html.lower()
    platform = "Manual Review"
    vendor = "Manual Review"
    sources: list[str] = []
    notes: list[str] = []

    def _find_signature(signatures, label_type: str) -> tuple[str, list[str]] | None:
        for label, tokens in signatures:
            matches = [token for token in tokens if token in html_lower]
            if matches:
                note = f"Detected {label_type} indicators ({label}): {', '.join(matches)}"
                return label, [note]
        return None

    platform_match = _find_signature(cms_platform_signatures, "platform")
    if platform_match:
        platform, platform_notes = platform_match
        sources.append("Homepage")
        notes.extend(platform_notes)

    vendor_match = _find_signature(cms_vendor_signatures, "vendor")
    if vendor_match:
        vendor, vendor_notes = vendor_match
        if "Homepage" not in sources:
            sources.append("Homepage")
        notes.extend(vendor_notes)

    if vendor == "Lion's Light":
        platform = "ROAR"

    if platform == "Manual Review":
        sitemap_urls = sitemap_data.get("urls", [])
        for url in sitemap_urls:
            if "wp-sitemap" in url:
                platform = "WordPress"
                notes.append("Sitemap contains wp-sitemap entries")
                sources.append("Sitemap")
                break

    # If a vendor strongly implies a platform, set a best guess
    if vendor != "Manual Review" and platform == "Manual Review":
        implied_platforms = {
            "Creative Circle": "Creative Circle",
            "BLOX": "BLOX Digital",
            "Gannett": "Presto",
            "eType": "eType",
            "Arc Publishing": "Arc XP",
            "Brightspot": "Brightspot",
            "NewsPack": "WordPress",
            "Our Hometown Web Publishing": "WordPress",
            "StuffSites": "StuffSites",
            "PubGenAI": "PubGenAI",
            "ePublishing": "ePublishing",
            "Lion's Light": "ROAR",
            "Surf New Media": "Surf New Media",
            "Websites For Newspapers": "Websites For Newspapers",
        }
        platform = implied_platforms.get(vendor, platform)

    if not sources and (platform != "Manual Review" or vendor != "Manual Review"):
        sources.append("Homepage")

    sources = list(dict.fromkeys(sources))

    return platform, vendor, sources, notes

def detect_pdf(homepage_html, sitemap_data, rss_data, chain_detected, cms_vendor):
    sources, notes = [], []
    has_pdf = None
    pdf_only = "Manual Review"
    data_observed = False

    total_anchors = 0
    pdf_hint_links: list[str] = []
    pdf_links: list[str] = []
    article_hint_links: list[str] = []
    article_dom_signals = 0

    if homepage_html:
        data_observed = True
        soup = BeautifulSoup(homepage_html, "html.parser")
        anchors = soup.find_all("a", href=True)
        total_anchors = len(anchors)
        pdf_links = [a["href"] for a in anchors if a["href"].strip().lower().endswith(".pdf")]
        for anchor in anchors:
            anchor_text = (anchor.get_text() or "").strip().lower()
            href_lower = anchor["href"].strip().lower()
            if not anchor_text and not href_lower:
                continue

            text_match = any(keyword in anchor_text for keyword in pdf_homepage_keywords)
            href_match = any(keyword in href_lower for keyword in pdf_href_keywords)
            if not pdf_links and (text_match or href_match):
                pdf_hint_links.append(anchor["href"])

            if not href_lower.endswith(".pdf"):
                article_text_match = any(keyword in anchor_text for keyword in article_href_keywords)
                article_href_match = any(keyword in href_lower for keyword in article_href_keywords)
                if article_text_match or article_href_match:
                    article_hint_links.append(anchor["href"])

        if pdf_hint_links and not pdf_links:
            has_pdf = "Yes"
            notes.append(
                "Homepage contains e-edition style link(s): "
                + ", ".join(sorted(set(pdf_hint_links))[:3])
            )
            sources.append("Homepage")

        if pdf_links:
            has_pdf = "Yes"
            notes.append(f"Found {len(pdf_links)} PDF links on homepage")
            sources.append("Homepage")

        article_elements = soup.find_all("article")
        article_dom_signals += len(article_elements)

        for element in soup.find_all(class_=True):
            if element.name == "article":
                continue
            classes = element.get("class") or []
            for class_name in classes:
                class_lower = str(class_name).lower()
                if any(keyword in class_lower for keyword in article_class_keywords):
                    article_dom_signals += 1
                    break

    if sitemap_data["used"]:
        data_observed = True
        if sitemap_data["pdf_ratio"] > 0:
            has_pdf = "Yes"
            notes.append(f"Sitemap shows {sitemap_data['pdf_ratio']:.0%} PDF URLs")
        sources.append("Sitemap")

    pdf_like_count = len(pdf_links) + len(pdf_hint_links)
    pdf_like_ratio = pdf_like_count / total_anchors if total_anchors else 0.0
    article_hint_links = list(dict.fromkeys(article_hint_links))
    article_like_count = len(article_hint_links) + article_dom_signals
    article_like_ratio = article_like_count / total_anchors if total_anchors else 0.0

    rss_entries = rss_data.get("entry_count", 0)
    rss_pdf_entries = rss_data.get("pdf_entry_count", 0)
    rss_has_articles = rss_data.get("feed_found") and (rss_entries - rss_pdf_entries) > 0
    vendor_is_tecnavia = (cms_vendor or "").strip().lower().startswith("tecnavia")

    article_signals = article_like_count >= 3 or article_dom_signals >= 2 or article_like_ratio >= 0.2
    if article_signals:
        if article_hint_links:
            notes.append(
                "Homepage contains article-style link(s): "
                + ", ".join(article_hint_links[:3])
            )
        if "Homepage contains article-style content" not in notes:
            notes.append("Homepage contains article-style content")
        sources.append("Homepage")
        rss_has_articles = True

    if rss_data["feed_found"]:
        data_observed = True
        sources.append("RSS")
        if rss_entries == 0:
            notes.append("RSS present but contains no entries")
        elif rss_pdf_entries >= rss_entries:
            notes.append("RSS entries appear to link to PDFs")
        else:
            notes.append("RSS present (indicates article content)")

    # Decide PDF-only
    pdf_only_reasons: list[str] = []
    homepage_pdf_heavy = pdf_like_count >= 3 and pdf_like_ratio >= 0.15

    if chain_detected:
        pdf_only = "No"
        notes.append(f"Chain heuristic: {chain_detected}, not PDF-only")
    elif has_pdf == "Yes":
        pdf_dominated = sitemap_data["pdf_ratio"] > 0.75
        rss_lacks_articles = not rss_has_articles

        if pdf_dominated:
            pdf_only_reasons.append(f"sitemap {sitemap_data['pdf_ratio']:.0%} PDF URLs")
        if rss_lacks_articles:
            if rss_entries == 0 and rss_data["feed_found"]:
                pdf_only_reasons.append("RSS has no entries")
            elif rss_pdf_entries >= rss_entries and rss_entries > 0:
                pdf_only_reasons.append("RSS entries point to PDFs")
            else:
                pdf_only_reasons.append("RSS lacks article entries")
        if not sitemap_data["used"]:
            pdf_only_reasons.append("no sitemap detected")
        if vendor_is_tecnavia:
            pdf_only_reasons.append("Tecnavia platform detected")
            if pdf_like_count:
                pdf_only_reasons.append("Tecnavia navigation links to PDF viewer")
            if rss_lacks_articles:
                pdf_only_reasons.append("Tecnavia feed lacks article entries")
        if homepage_pdf_heavy:
            pdf_only_reasons.append("homepage navigation dominated by PDF links")

        if not pdf_only_reasons and vendor_is_tecnavia and rss_lacks_articles:
            pdf_only_reasons.append("Tecnavia feed lacks article entries")

        if (pdf_only_reasons and rss_lacks_articles) or (vendor_is_tecnavia and (rss_lacks_articles or homepage_pdf_heavy)):
            pdf_only = "Yes"
            notes.append("PDF-only: " + "; ".join(dict.fromkeys(pdf_only_reasons)))
        elif data_observed:
            pdf_only = "No"
    elif data_observed:
        pdf_only = "No"

    if has_pdf is None:
        has_pdf = "No"

    sources = list(dict.fromkeys(sources))
    notes = list(dict.fromkeys(notes))

    return has_pdf, pdf_only, sources, notes

def detect_paywall(homepage_html, sitemap_data, rss_data, chain_detected):
    sources, notes = [], []
    has_signal = False

    if chain_detected:
        notes.append(f"Chain heuristic: {chain_detected}, default Paywall=Yes")
        return "Yes", [f"Heuristic:{chain_detected}"], notes

    if homepage_html and any(k in homepage_html.lower() for k in paywall_keywords):
        notes.append("Homepage contains paywall keywords")
        has_signal = True
        sources.append("Homepage")

    if sitemap_data["used"]:
        if any("subscribe" in loc or "membership" in loc or "registration" in loc or "premium" in loc for loc in sitemap_data.get("urls", [])):
            notes.append("Sitemap contains subscription-related URLs")
            has_signal = True
            sources.append("Sitemap")

    if rss_data["feed_found"] and rss_data["paywall_hint"]:
        notes.append("RSS feed contains paywall hints")
        has_signal = True
        sources.append("RSS")

    if has_signal:
        return "Yes", sources or ["Homepage"], notes

    notes.append("No paywall signals found")
    return "No", sources, notes

def detect_public_notices(homepage_html, sitemap_data, rss_data):
    sources, notes = [], []
    has_signal = False

    if homepage_html and any(k in homepage_html.lower() for k in public_notice_keywords):
        notes.append("Homepage contains public notice keywords")
        has_signal = True
        sources.append("Homepage")

    if sitemap_data["used"] and sitemap_data["notices"]:
        notes.append("Sitemap contains notice-related URLs")
        has_signal = True
        sources.append("Sitemap")

    if rss_data["feed_found"] and rss_data["notices"]:
        notes.append("RSS feed contains notice keywords")
        has_signal = True
        sources.append("RSS")

    if has_signal:
        return "Yes", sources or ["Homepage"], notes

    notes.append("No notices found")
    return "No", sources, notes

def detect_responsive(homepage_html):
    sources, notes = [], []
    if not homepage_html:
        notes.append("No homepage HTML available")
        return "Manual Review", sources, notes

    soup = BeautifulSoup(homepage_html, "html.parser")
    html_lower = homepage_html.lower()

    if soup.find("meta", {"name": "viewport"}):
        notes.append("Viewport meta tag present")
        return "Yes", ["Homepage"], notes

    if "@media screen and (max-width" in html_lower:
        notes.append("CSS media queries found")
        return "Yes", ["Homepage"], notes

    if any(framework in html_lower for framework in ["bootstrap", "tailwind", "foundation"]):
        notes.append("Responsive framework detected")
        return "Yes", ["Homepage"], notes

    notes.append("No responsive indicators")
    return "No", ["Homepage"], notes

# --- Main Audit ---

def quick_audit(url: str, *, strict: bool = False):
    audit = {
        "Has PDF Edition?": "Manual Review",
        "PDF-Only?": "Manual Review",
        "Paywall?": "Manual Review",
        "Free Public Notices?": "Manual Review",
        "Mobile Responsive?": "Manual Review",
        "Audit Sources": "",
        "Audit Notes": "",
        "Homepage HTML": None,
        "Chain Owner": "Manual Review",
        "CMS Platform": "Manual Review",
        "CMS Vendor": "Manual Review",
    }

    if not isinstance(url, str) or not url.strip():
        return {
            "Has PDF Edition?": "",
            "PDF-Only?": "",
            "Paywall?": "",
            "Free Public Notices?": "",
            "Mobile Responsive?": "",
            "Audit Sources": "",
            "Audit Notes": "",
            "Homepage HTML": None,
            "Chain Owner": "",
            "CMS Platform": "",
            "CMS Vendor": "",
        }

    if not url.startswith("http"):
        url = "http://" + url

    fetch_target = url
    homepage_html, homepage_status, homepage_error = fetch_url(
        fetch_target, retries=3, backoff=2.0, raise_on_timeout=strict
    )
    if homepage_html is None and homepage_status in REDIRECT_STATUS_CODES:
        upgraded = _prefer_https(fetch_target)
        if upgraded != fetch_target:
            fetch_target = upgraded
            homepage_html, homepage_status, homepage_error = fetch_url(
                fetch_target, retries=2, backoff=2.0, raise_on_timeout=strict
            )
    time.sleep(REQUEST_PAUSE_SECONDS)
    if strict and homepage_html is None and _is_timeout_error(homepage_status, homepage_error):
        raise HomepageFetchTimeoutError(fetch_target, homepage_error, homepage_status)
    sitemap_data = check_sitemap(fetch_target)
    time.sleep(REQUEST_PAUSE_SECONDS)
    rss_data = check_rss(fetch_target)
    chain_value, chain_sources, chain_notes = detect_chain(homepage_html)
    cms_platform, cms_vendor, cms_sources, cms_notes = detect_cms(homepage_html, sitemap_data)

    chain_for_rules = None if chain_value in ("Manual Review", "Independent") else chain_value

    has_pdf, pdf_only, pdf_sources, pdf_notes = detect_pdf(
        homepage_html, sitemap_data, rss_data, chain_for_rules, cms_vendor
    )
    paywall, paywall_sources, paywall_notes = detect_paywall(
        homepage_html, sitemap_data, rss_data, chain_for_rules
    )
    notices, notice_sources, notice_notes = detect_public_notices(homepage_html, sitemap_data, rss_data)
    responsive, resp_sources, resp_notes = detect_responsive(homepage_html)

    all_sources = (
        pdf_sources
        + paywall_sources
        + notice_sources
        + resp_sources
        + chain_sources
        + cms_sources
    )
    all_notes = (
        pdf_notes + paywall_notes + notice_notes + resp_notes + chain_notes + cms_notes
    )

    sanitized_homepage_html, snapshot_truncated = sanitize_homepage_snapshot(homepage_html)

    if homepage_html is None:
        if homepage_error:
            all_notes.append(f"Homepage fetch failed: {homepage_error}")
        elif homepage_status:
            all_notes.append(f"Homepage fetch returned HTTP {homepage_status}")
        else:
            all_notes.append("Homepage fetch failed (unknown error)")
    elif snapshot_truncated:
        all_notes.append(
            f"Homepage snapshot truncated to {MAX_SNAPSHOT_CHARS:,} characters"
        )

    if cms_vendor == "BLOX" and cms_platform == "Manual Review":
        cms_platform = "BLOX Digital"
    if cms_vendor == "eType" and cms_platform == "Manual Review":
        cms_platform = "eType"

    if chain_value == "Gannett" and cms_vendor == "Manual Review" and cms_platform == "Manual Review":
        cms_vendor = "Gannett"
        cms_platform = "Presto"

    audit.update({
        "Has PDF Edition?": has_pdf,
        "PDF-Only?": pdf_only,
        "Paywall?": paywall,
        "Free Public Notices?": notices,
        "Mobile Responsive?": responsive,
        "Audit Sources": "+".join(sorted(set(all_sources))) if all_sources else "None",
        "Audit Notes": " | ".join(all_notes) if all_notes else "",
        "Homepage HTML": sanitized_homepage_html,
        "Chain Owner": chain_value,
        "CMS Platform": cms_platform,
        "CMS Vendor": cms_vendor,
    })

    return audit

def process_csv(input_file, force=False):
    input_path = Path(input_file)
    df = pd.read_csv(input_path)

    def _find_url_column(frame: pd.DataFrame) -> str | None:
        column_lookup = {col.lower(): col for col in frame.columns}
        candidates = ["website url", "website_url", "url", "site", "website"]
        for candidate in candidates:
            if candidate in column_lookup:
                return column_lookup[candidate]
        return None

    url_column = _find_url_column(df)
    if not url_column:
        raise ValueError(
            "No website URL column found. Expected one of: 'Website Url', 'URL', 'Site', 'Website'."
        )

    audit_columns = [
        "Has PDF Edition?",
        "PDF-Only?",
        "Paywall?",
        "Free Public Notices?",
        "Mobile Responsive?",
        "Chain Owner",
        "CMS Platform",
        "CMS Vendor",
        "Audit Sources",
        "Audit Notes",
    ]
    for col in audit_columns:
        if col not in df.columns:
            df[col] = ""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = input_path.stem
    out_file = OUTPUT_DIR / f"{base}_Audit.csv"

    if out_file.exists():
        if force:
            print(f"⚠️ Overwriting existing audit file: {out_file}")
        else:
            print(f"🔄 Resuming audit from cache: {out_file}")
            cached_df = pd.read_csv(out_file)
            merge_key = None
            for candidate in ["Website Url", "Paper Name"]:
                if candidate in df.columns and candidate in cached_df.columns:
                    merge_key = candidate
                    break

            if merge_key:
                cache_map = cached_df.set_index(merge_key)
                shared_columns = [col for col in audit_columns if col in cache_map.columns]
                for idx, row in df.iterrows():
                    key_val = row.get(merge_key)
                    if pd.isna(key_val) or key_val not in cache_map.index:
                        continue
                    for col in shared_columns:
                        df.at[idx, col] = cache_map.at[key_val, col]
            else:
                shared_columns = [col for col in audit_columns if col in cached_df.columns]
                rows_to_copy = min(len(df), len(cached_df))
                if rows_to_copy:
                    df.loc[:rows_to_copy - 1, shared_columns] = cached_df.loc[:rows_to_copy - 1, shared_columns].values

    total = len(df)
    for idx, row in df.iterrows():
        if not force and all(str(row.get(col, "")).strip() not in ["", "Manual Review", "Manual Review (Timeout)", "Manual Review (Error)", ""] for col in audit_columns[:-1]):
            continue

        url_value = row.get(url_column, "")
        url = url_value if isinstance(url_value, str) else str(url_value or "")
        results = quick_audit(url)
        for col, val in results.items():
            df.loc[idx, col] = val

        safe_paper = row.get('Paper Name', 'Unknown')
        display_url = url or 'No URL'
        print(f"[{idx+1}/{total}] Audited: {safe_paper} ({display_url}) → Sources: {results['Audit Sources']}")

        if idx % 5 == 0:
            df.to_csv(out_file, index=False)

    df.to_csv(out_file, index=False)
    print(f"\n✅ Audit complete. Results saved to {out_file}")
    
def run_audit(url: str):
    return quick_audit(url, strict=True)


def main():
    parser = argparse.ArgumentParser(description="Audit newspaper websites from a CSV input")
    parser.add_argument("input_csv", help="Path to the CSV file containing newspaper records")
    parser.add_argument("--force", action="store_true", help="Re-run audits even if cached results exist")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        parser.error(f"Input file not found: {input_path}")

    process_csv(input_path, force=args.force)


if __name__ == "__main__":
    main()
