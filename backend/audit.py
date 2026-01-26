import argparse
import os
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

try:
    import brotli  # type: ignore[import]
except ModuleNotFoundError:
    try:
        import brotlicffi as brotli  # type: ignore[import]
    except ModuleNotFoundError:
        brotli = None
try:
    from playwright.sync_api import sync_playwright  # type: ignore[import]
except ModuleNotFoundError:
    sync_playwright = None

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
    "e-Edition",
    "eedition",
    "e edition",
    "epaper",
    "e-paper",
    "digital edition",
    "digital replica",
    "digital-version",
    "digital version",
    "digital-issues",
    "replica edition",
    "enewspaper",
    "e-newspaper",
    "printed paper",
    "epost",
    "e-post",
    "e post",
    "issuu",
    "print archive",
    "online paper",
    "online-newspaper",
]
pdf_href_keywords = [
    "eedition",
    "e-Edition",
    "epaper",
    "ePaper",
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
    "print archive",
    "online paper",
    "online-newspaper",
    "issue=",
    "digital-issues",
    "issuu.com",
    "isu.pub/",
    "pagesuite-professional.co.uk",
    "pagesuite.com",
]

ISSUU_TOKENS = ("issuu.com", "isu.pub/")
PAGESUITE_TOKENS = ("pagesuite-professional.co.uk", "pagesuite.com")


def _is_pdf_like_link(link: str | None) -> bool:
    if not link:
        return False
    lowered = link.lower()
    if lowered.endswith(".pdf"):
        return True
    return any(keyword in lowered for keyword in pdf_href_keywords)


def _is_issuu_link(link: str | None) -> bool:
    if not link:
        return False
    lowered = link.lower()
    return any(token in lowered for token in ISSUU_TOKENS)


def _is_pagesuite_link(link: str | None) -> bool:
    if not link:
        return False
    lowered = link.lower()
    return any(token in lowered for token in PAGESUITE_TOKENS)


def _collect_embed_links(soup: BeautifulSoup) -> list[str]:
    links: list[str] = []
    for tag in soup.find_all(["iframe", "embed", "object"]):
        for attr in ("src", "data", "data-src", "data-url"):
            value = tag.get(attr)
            if isinstance(value, str) and value.strip():
                links.append(value.strip())
    for script in soup.find_all("script", src=True):
        src = script.get("src")
        if isinstance(src, str) and src.strip():
            links.append(src.strip())
    for tag in soup.find_all(attrs={"data-issuu-id": True}):
        issuu_id = tag.get("data-issuu-id")
        if isinstance(issuu_id, str) and issuu_id.strip():
            links.append(f"issuu-id:{issuu_id.strip()}")
    return links

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
    ("Creative Circle", ["creativecircle", "circle-media", "circleid", "creativecirclecdn"]),
    ("BLOX Digital", ["tncms", "bloximages", "townnews", "bloxcms"]),
    ("Joomla", ["joomla", "joomla!", "jooomla-"]),
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
    ("Locable Community Content Engine", ["locable", "locable.com", "locable media"]),
    ("SquareSpace", ["squarespace", "squarespace-cdn", "squarespace media"]),
    ("SNworks", ["SNworks", "solutions by state news", "snworks", "snworsceo"]),
    ("Ghost", ["/ghost"]),
]

cms_vendor_signatures = [
    ("Creative Circle", ["creativecircle", "circle-media", "circleid", "creativecirclecdn"]),
    ("Joomla", ["joomla", "joomla!", "jooomla-"]),
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
    ("Locable", ["locable", "locable.com", "locable media"]),
    ("SquareSpace", ["squarespace", "squarespace-cdn", "squarespace media"]),
    ("Solutions by State News", ["SNworks", "solutions by state news", "snworks", "snworsceo"]),
    ("Ghost", ["/ghost"]),

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
        separator = "\n<!-- SNIPPED MIDDLE -->\n"
        tail_len = min(100_000, max_chars // 4)
        head_len = max_chars - tail_len - len(separator)
        if head_len <= 0:
            return cleaned[:max_chars], True
        return f"{cleaned[:head_len]}{separator}{cleaned[-tail_len:]}", True
    return cleaned, False


def _inject_base_href(html: str, base_url: str) -> str:
    if "<base" in html.lower():
        return html
    lower_html = html.lower()
    head_index = lower_html.find("<head")
    if head_index == -1:
        return f'<base href="{base_url}">\n{html}'
    head_close = lower_html.find(">", head_index)
    if head_close == -1:
        return html
    insert_at = head_close + 1
    return f'{html[:insert_at]}<base href="{base_url}">{html[insert_at:]}'


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

MODERN_CHROME_HEADERS = {
    **DEFAULT_HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.6422.142 Safari/537.36"
    ),
    "Sec-Ch-Ua": '"Not/A)Brand";v="99", "Google Chrome";v="125", "Chromium";v="125"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

MODERN_FIREFOX_HEADERS = {
    **DEFAULT_HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:126.0) "
        "Gecko/20100101 Firefox/126.0"
    ),
    "Upgrade-Insecure-Requests": "1",
}

MODERN_SAFARI_HEADERS = {
    **DEFAULT_HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_0) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Safari/605.1.15"
    ),
    "Upgrade-Insecure-Requests": "1",
}

BROWSER_HEADER_VARIANTS = [
    DEFAULT_HEADERS,
    MODERN_CHROME_HEADERS,
    MODERN_FIREFOX_HEADERS,
    MODERN_SAFARI_HEADERS,
]

REQUEST_PAUSE_SECONDS = 0.75
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
MANUAL_REVIEW_STATUSES = {
    "manual review",
    "manual review (timeout)",
    "manual review (error)",
}

_AUDIT_DEBUG = os.getenv("AUDIT_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
_AUDIT_PLAYWRIGHT_FALLBACK = os.getenv("AUDIT_PLAYWRIGHT_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}
_AUDIT_PLAYWRIGHT_TIMEOUT_MS = int(os.getenv("AUDIT_PLAYWRIGHT_TIMEOUT_MS", "15000"))
_AUDIT_PLAYWRIGHT_ONLY = os.getenv("AUDIT_PLAYWRIGHT_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}

REQUEST_PAUSE_SECONDS = 0.75
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
MANUAL_REVIEW_STATUSES = {
    "manual review",
    "manual review (timeout)",
    "manual review (error)",
}


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


def _should_try_playwright(status_code: int | None, error_message: str | None) -> bool:
    if status_code in {401, 403, 429}:
        return True
    if not error_message:
        return False
    lowered = error_message.lower()
    return "connection reset" in lowered or "connection aborted" in lowered or "tls" in lowered


def _fetch_with_playwright(url: str) -> tuple[str | None, int | None, str | None]:
    if sync_playwright is None:
        return None, None, "Playwright not installed"
    if _AUDIT_DEBUG:
        print(f"[audit] playwright fallback start url={url}")
    try:
        with sync_playwright() as playwright:
            browser = playwright.firefox.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            response = page.goto(url, timeout=_AUDIT_PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
            content = page.content()
            status = response.status if response else None
            browser.close()
            if _AUDIT_DEBUG:
                print(f"[audit] playwright fallback ok url={url} status={status} bytes={len(content)}")
            return content, status or 200, None
    except Exception as exc:  # pragma: no cover - runtime-specific
        if _AUDIT_DEBUG:
            print(f"[audit] playwright fallback error url={url} error={exc}")
        message = str(exc)
        if "Executable doesn't exist" in message or "browser_type.launch" in message:
            return None, None, "Playwright browsers not installed (run `playwright install`)"
        return None, None, str(exc)


def _prefer_https(url: str) -> str:
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def _ensure_amp_variant(url: str) -> str:
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if query_params.get("output") == "amp":
        return url
    query_params["output"] = "amp"
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _decode_html_bytes(data: bytes, encoding_hint: str | None) -> str:
    if encoding_hint:
        try:
            return data.decode(encoding_hint, errors="replace")
        except LookupError:
            pass
    try:
        return data.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def fetch_url(
    url,
    timeout=8,
    headers=None,
    header_variants=None,
    retries=2,
    backoff=1.5,
    raise_on_timeout: bool = False,
    allow_brotli: bool = False,
):
    if _AUDIT_DEBUG:
        print(f"[audit] fetch_url start url={url} timeout={timeout} retries={retries} allow_brotli={allow_brotli}")
    base_headers = headers or DEFAULT_HEADERS
    if header_variants is None:
        raw_variants = BROWSER_HEADER_VARIANTS if headers is None else [base_headers]
    else:
        raw_variants = header_variants

    normalized_variants = []
    for variant in raw_variants:
        merged = dict(variant or base_headers)
        if allow_brotli:
            merged["Accept-Encoding"] = "gzip, deflate, br"
        normalized_variants.append(merged)

    last_error = None
    for variant_index, variant_headers in enumerate(normalized_variants):
        current_url = url
        for attempt in range(retries + 1):
            try:
                if _AUDIT_DEBUG:
                    print(
                        f"[audit] request attempt={attempt + 1}/{retries + 1} "
                        f"variant={variant_index + 1}/{len(normalized_variants)} url={current_url}"
                    )
                resp = requests.get(current_url, timeout=timeout, headers=variant_headers, allow_redirects=True)
                if resp.status_code == 403 and current_url.startswith("http://"):
                    # retry once with https if forbidden over http
                    https_url = "https://" + current_url[len("http://"):]
                    current_url = https_url
                    continue
                if resp.status_code == 403:
                    last_error = f"HTTP 403 for {current_url}"
                    if _AUDIT_DEBUG:
                        print(f"[audit] fetch blocked {last_error}")
                    if attempt < retries:
                        time.sleep(backoff * (attempt + 1))
                        continue
                    if variant_index < len(normalized_variants) - 1:
                        break  # try next browser header variant
                    return None, resp.status_code, last_error
                if resp.status_code == 429:
                    last_error = f"HTTP 429 for {current_url}"
                    if _AUDIT_DEBUG:
                        print(f"[audit] fetch throttled {last_error}")
                    if attempt < retries:
                        time.sleep(backoff * (attempt + 1))
                        continue
                    if variant_index < len(normalized_variants) - 1:
                        break
                    return None, resp.status_code, last_error
                if resp.status_code == 200:
                    content = resp.content
                    encoding_header = (resp.headers.get("Content-Encoding") or "").lower()
                    if encoding_header == "br":
                        if not allow_brotli or brotli is None:
                            last_error = "Received Brotli-compressed response but Brotli support unavailable"
                            if _AUDIT_DEBUG:
                                print(f"[audit] brotli unavailable for url={current_url}")
                            return None, resp.status_code, last_error
                        try:
                            content = brotli.decompress(content)
                        except Exception as exc:  # pragma: no cover - depends on remote data
                            last_error = f"Brotli decode failed: {exc}"
                            if _AUDIT_DEBUG:
                                print(f"[audit] brotli decode failed url={current_url} error={exc}")
                            return None, resp.status_code, last_error
                    text = _decode_html_bytes(content, resp.encoding or getattr(resp, "apparent_encoding", None))
                    if _AUDIT_DEBUG:
                        print(f"[audit] fetch ok url={current_url} bytes={len(content)}")
                    return text, resp.status_code, None
                last_error = f"HTTP {resp.status_code}"
                if _AUDIT_DEBUG:
                    print(f"[audit] fetch failed status={resp.status_code} url={current_url}")
                return None, resp.status_code, None
            except requests.exceptions.Timeout as exc:
                last_error = str(exc)
                if _AUDIT_DEBUG:
                    print(f"[audit] fetch timeout url={current_url} error={exc}")
                if raise_on_timeout:
                    raise HomepageFetchTimeoutError(current_url, last_error) from exc
                if attempt == retries:
                    return None, None, last_error
            except Exception as exc:
                last_error = str(exc)
                if _AUDIT_DEBUG:
                    print(f"[audit] fetch error url={current_url} error={exc}")
                if attempt == retries:
                    return None, None, last_error
        else:
            continue
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
        if _AUDIT_PLAYWRIGHT_ONLY:
            xml_text, status_code, _ = _fetch_with_playwright(sitemap_url)
        else:
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
                    if _is_pdf_like_link(loc):
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
        if _AUDIT_PLAYWRIGHT_ONLY:
            xml_text, status_code, _ = _fetch_with_playwright(candidate)
        else:
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
                    if _is_pdf_like_link(lowered_link):
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
                    if _is_pdf_like_link(lowered_href):
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
            "Joomla": "Joomla",
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
            "Solutions by State News": "SNworks"
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
            href_match = _is_pdf_like_link(href_lower)
            if not pdf_links and (text_match or href_match):
                pdf_hint_links.append(anchor["href"])

            if not href_lower.endswith(".pdf"):
                article_text_match = any(keyword in anchor_text for keyword in article_href_keywords)
                article_href_match = any(keyword in href_lower for keyword in article_href_keywords)
                if article_text_match or article_href_match:
                    article_hint_links.append(anchor["href"])

        embed_links = _collect_embed_links(soup)
        issuu_embeds = [link for link in embed_links if _is_issuu_link(link)]
        pagesuite_embeds = [link for link in embed_links if _is_pagesuite_link(link)]
        pdf_embed_links = [link for link in embed_links if _is_pdf_like_link(link)]

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

        if issuu_embeds:
            has_pdf = "Yes"
            notes.append(
                "Homepage contains Issuu embed(s): "
                + ", ".join(sorted(set(issuu_embeds))[:3])
            )
            sources.append("Homepage")

        if pagesuite_embeds:
            has_pdf = "Yes"
            notes.append(
                "Homepage contains PageSuite embed(s): "
                + ", ".join(sorted(set(pagesuite_embeds))[:3])
            )
            sources.append("Homepage")

        if pdf_embed_links and not issuu_embeds:
            has_pdf = "Yes"
            notes.append(
                "Homepage contains PDF-style embed(s): "
                + ", ".join(sorted(set(pdf_embed_links))[:3])
            )
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

PRIVACY_SIGNATURES = [
    {
        "vendor": "Google Analytics",
        "category": "analytics",
        "patterns": {
            "script_src": [
                "googletagmanager.com/gtag/js",
                "google-analytics.com/analytics.js",
                "google-analytics.com/ga.js",
            ],
            "inline": ["gtag(", "ga(", "google-analytics.com"],
            "img_src": ["google-analytics.com/collect"],
        },
    },
    {
        "vendor": "Google Tag Manager",
        "category": "tag_manager",
        "patterns": {
            "script_src": ["googletagmanager.com/gtm.js"],
            "inline": ["dataLayer", "gtm.start", "googletagmanager.com/gtm.js"],
        },
    },
    {
        "vendor": "Meta Pixel",
        "category": "pixel",
        "patterns": {
            "script_src": ["connect.facebook.net/en_US/fbevents.js"],
            "inline": ["fbq('init'", "fbq(\"init\"", "fbq('track'", "fbq(\"track\""],
            "img_src": ["facebook.com/tr"],
        },
    },
    {
        "vendor": "TikTok Pixel",
        "category": "pixel",
        "patterns": {
            "script_src": ["analytics.tiktok.com", "tiktok.com/i18n/pixel"],
            "inline": ["ttq.load", "ttq.page", "ttq.track"],
        },
    },
    {
        "vendor": "Bing UET",
        "category": "analytics",
        "patterns": {
            "script_src": ["bat.bing.com/bat.js"],
            "inline": ["uetq", "bat.bing.com"],
        },
    },
    {
        "vendor": "LinkedIn Insight",
        "category": "pixel",
        "patterns": {
            "script_src": ["snap.licdn.com/li.lms-analytics/insight.min.js"],
            "inline": ["linkedin insight", "lms-analytics"],
        },
    },
    {
        "vendor": "Twitter/X Pixel",
        "category": "pixel",
        "patterns": {
            "script_src": ["static.ads-twitter.com/uwt.js"],
            "inline": ["twq(", "twttr.conversion"],
        },
    },
    {
        "vendor": "Pinterest Tag",
        "category": "pixel",
        "patterns": {"script_src": ["ct.pinterest.com/v3/"], "inline": ["pintrk("]},
    },
    {
        "vendor": "Snap Pixel",
        "category": "pixel",
        "patterns": {"script_src": ["sc-static.net/scevent.min.js"], "inline": ["snaptr("]},
    },
    {
        "vendor": "Adobe Analytics",
        "category": "analytics",
        "patterns": {"script_src": ["omtrdc.net", "2o7.net"], "inline": ["s.t(", "adobe analytics"]},
    },
    {
        "vendor": "Adobe Launch",
        "category": "tag_manager",
        "patterns": {"script_src": ["assets.adobedtm.com", "adobedtm.com"], "inline": ["adobedtm"]},
    },
    {
        "vendor": "Tealium",
        "category": "tag_manager",
        "patterns": {"script_src": ["tags.tiqcdn.com", "tiqcdn.com"], "inline": ["utag"]},
    },
    {
        "vendor": "Segment",
        "category": "analytics",
        "patterns": {"script_src": ["cdn.segment.com/analytics.js"], "inline": ["analytics.load("]},
    },
    {
        "vendor": "Mixpanel",
        "category": "analytics",
        "patterns": {"script_src": ["cdn.mxpnl.com/libs/mixpanel"], "inline": ["mixpanel.init("]},
    },
    {
        "vendor": "Matomo",
        "category": "analytics",
        "patterns": {"script_src": ["/matomo.js", "/piwik.js"], "inline": ["matomoTracker", "_paq"]},
    },
    {
        "vendor": "Plausible",
        "category": "analytics",
        "patterns": {"script_src": ["plausible.io/js/plausible.js"], "inline": ["plausible("]},
    },
    {
        "vendor": "Fathom",
        "category": "analytics",
        "patterns": {"script_src": ["cdn.usefathom.com", "fathom.js"], "inline": ["fathom.trackGoal"]},
    },
    {
        "vendor": "Cloudflare Web Analytics",
        "category": "analytics",
        "patterns": {"script_src": ["static.cloudflareinsights.com/beacon.min.js"], "inline": ["cloudflareinsights"]},
    },
    {
        "vendor": "Hotjar",
        "category": "session_replay",
        "patterns": {"script_src": ["static.hotjar.com/c/hotjar-", "hotjar.com"], "inline": ["hj(", "hotjar"]},
    },
    {
        "vendor": "FullStory",
        "category": "session_replay",
        "patterns": {"script_src": ["fullstory.com/s/fs.js"], "inline": ["FS.identify", "fullstory"]},
    },
    {
        "vendor": "LogRocket",
        "category": "session_replay",
        "patterns": {"script_src": ["cdn.logrocket.io"], "inline": ["LogRocket.init"]},
    },
    {
        "vendor": "Microsoft Clarity",
        "category": "session_replay",
        "patterns": {"script_src": ["clarity.ms/tag/"], "inline": ["clarity("]},
    },
    {
        "vendor": "Crazy Egg",
        "category": "session_replay",
        "patterns": {"script_src": ["crazyegg.com/pages/scripts"], "inline": ["crazyegg"]},
    },
    {
        "vendor": "Inspectlet",
        "category": "session_replay",
        "patterns": {"script_src": ["inspectlet.com/wrm"], "inline": ["__insp"]},
    },
    {
        "vendor": "Lucky Orange",
        "category": "session_replay",
        "patterns": {"script_src": ["luckyorange.com", "lo.js"], "inline": ["luckyorange"]},
    },
    {
        "vendor": "Cookiebot",
        "category": "consent",
        "patterns": {"script_src": ["consent.cookiebot.com/uc.js"], "inline": ["Cookiebot"]},
    },
    {
        "vendor": "OneTrust",
        "category": "consent",
        "patterns": {"script_src": ["cdn.cookielaw.org", "cookie-cdn.cookiepro.com"], "inline": ["Optanon", "OneTrust"]},
    },
    {
        "vendor": "TrustArc",
        "category": "consent",
        "patterns": {"script_src": ["trustarc.com", "truste.com"], "inline": ["truste", "trustarc"]},
    },
    {
        "vendor": "Didomi",
        "category": "consent",
        "patterns": {"script_src": ["didomi.io"], "inline": ["didomi"]},
    },
    {
        "vendor": "Quantcast CMP",
        "category": "consent",
        "patterns": {"script_src": ["quantcast.mgr.consensu.org", "quantcast.com/choice"], "inline": ["__cmp", "quantcast"]},
    },
    {
        "vendor": "IAB TCF",
        "category": "consent",
        "patterns": {"inline": ["__tcfapi", "tcfapi"]},
    },
    {
        "vendor": "LiveRamp",
        "category": "ads",
        "patterns": {"script_src": ["liveramp.com", "idsync.rlcdn.com"], "inline": ["liveramp"]},
    },
    {
        "vendor": "Criteo",
        "category": "ads",
        "patterns": {"script_src": ["static.criteo.net", "criteo.com"], "inline": ["criteo"]},
    },
    {
        "vendor": "Taboola",
        "category": "ads",
        "patterns": {"script_src": ["taboola.com"], "inline": ["taboola"]},
    },
    {
        "vendor": "Outbrain",
        "category": "ads",
        "patterns": {"script_src": ["outbrain.com"], "inline": ["outbrain"]},
    },
    {
        "vendor": "Amazon Publisher Services",
        "category": "ads",
        "patterns": {"script_src": ["c.amazon-adsystem.com"], "inline": ["apstag"]},
    },
    {
        "vendor": "OpenX",
        "category": "ads",
        "patterns": {"script_src": ["openx.net"], "inline": ["openx"]},
    },
]

PRIVACY_SCORE_WEIGHTS = {
    "analytics": 10,
    "tag_manager": 15,
    "pixel": 20,
    "session_replay": 25,
    "ads": 20,
    "consent": 0,
}


def _find_pattern_matches(values: list[str], patterns: list[str]) -> list[str]:
    matches: list[str] = []
    for value in values:
        for pattern in patterns:
            if pattern.lower() in value:
                matches.append(value)
                break
    return matches


def _find_pattern_tokens(values: list[str], patterns: list[str]) -> list[str]:
    tokens: list[str] = []
    for value in values:
        for pattern in patterns:
            lowered = pattern.lower()
            if lowered in value:
                tokens.append(lowered)
    return tokens


def detect_privacy_features(homepage_html: str | None):
    if not homepage_html:
        flags = {
            "has_tracking": False,
            "has_consent_tool": False,
            "has_session_replay": False,
            "has_pixels": False,
            "has_tag_manager": False,
            "has_analytics": False,
            "has_ad_network": False,
        }
        return [], flags, 0, "No homepage HTML available"

    soup = BeautifulSoup(homepage_html, "html.parser")
    script_srcs = [
        (script.get("src") or "").strip().lower()
        for script in soup.find_all("script")
        if script.get("src")
    ]
    inline_scripts = [
        script.get_text(" ", strip=True).lower()
        for script in soup.find_all("script")
        if not script.get("src") and script.get_text(strip=True)
    ]
    img_srcs = [
        (img.get("src") or "").strip().lower()
        for img in soup.find_all("img")
        if img.get("src")
    ]
    noscripts = [
        noscript.get_text(" ", strip=True).lower()
        for noscript in soup.find_all("noscript")
        if noscript.get_text(strip=True)
    ]

    features: list[dict[str, str]] = []
    for signature in PRIVACY_SIGNATURES:
        patterns = signature.get("patterns", {})
        evidence: list[tuple[str, str]] = []
        confidence = None

        if patterns.get("script_src"):
            matches = _find_pattern_matches(script_srcs, patterns["script_src"])
            if matches:
                evidence.extend([("script_src", match) for match in matches])
                confidence = "high"

        if patterns.get("img_src"):
            matches = _find_pattern_matches(img_srcs, patterns["img_src"])
            if matches:
                evidence.extend([("img_src", match) for match in matches])
                confidence = confidence or "high"

        if patterns.get("inline"):
            inline_matches = _find_pattern_tokens(inline_scripts, patterns["inline"])
            noscript_matches = _find_pattern_tokens(noscripts, patterns["inline"])
            if inline_matches or noscript_matches:
                evidence.extend([("inline", match) for match in inline_matches])
                evidence.extend([("inline", match) for match in noscript_matches])
                confidence = confidence or "medium"

        if evidence:
            used_evidence = evidence[:3]
            for source_type, match in used_evidence:
                features.append(
                    {
                        "vendor": signature["vendor"],
                        "category": signature["category"],
                        "signal": source_type,
                        "evidence": match,
                        "confidence": confidence or "low",
                    }
                )

    flags = {
        "has_tracking": any(feature["category"] != "consent" for feature in features),
        "has_consent_tool": any(feature["category"] == "consent" for feature in features),
        "has_session_replay": any(feature["category"] == "session_replay" for feature in features),
        "has_pixels": any(feature["category"] == "pixel" for feature in features),
        "has_tag_manager": any(feature["category"] == "tag_manager" for feature in features),
        "has_analytics": any(feature["category"] == "analytics" for feature in features),
        "has_ad_network": any(feature["category"] == "ads" for feature in features),
    }

    categories_seen = {feature["category"] for feature in features}
    score = sum(PRIVACY_SCORE_WEIGHTS.get(category, 0) for category in categories_seen)
    score = min(score, 100)

    summary_parts: list[str] = []
    ordered_categories = [
        "tag_manager",
        "analytics",
        "pixel",
        "session_replay",
        "ads",
        "consent",
    ]
    for category in ordered_categories:
        vendors = []
        for feature in features:
            if feature["category"] == category and feature["vendor"] not in vendors:
                vendors.append(feature["vendor"])
        if vendors:
            label = category.replace("_", " ").title()
            summary_parts.append(f"{label}: {', '.join(vendors)}")
    summary = "; ".join(summary_parts) if summary_parts else "None detected"

    return features, flags, score, summary

# --- Main Audit ---

def quick_audit(url: str, *, strict: bool = False):
    if _AUDIT_DEBUG:
        print(f"[audit] quick_audit start url={url} strict={strict}")
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
        "Privacy Features": None,
        "Privacy Flags": None,
        "Privacy Score": None,
        "Privacy Summary": None,
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
            "Privacy Features": None,
            "Privacy Flags": None,
            "Privacy Score": None,
            "Privacy Summary": None,
        }

    if not url.startswith("http"):
        url = "http://" + url

    def _attempt_fetch(
        target: str,
        retries: int,
        backoff: float,
        allow_brotli: bool = False,
        header_variants: list[dict[str, str]] | None = None,
    ):
        try:
            return fetch_url(
                target,
                retries=retries,
                backoff=backoff,
                raise_on_timeout=strict,
                allow_brotli=allow_brotli,
                header_variants=header_variants,
            )
        except HomepageFetchTimeoutError as exc:
            return None, exc.status_code, exc.detail

    fetch_target = url
    base_url_for_aux = fetch_target
    used_amp_variant = False
    used_brotli_variant = False
    blocked_for_aux = False

    fast_fallback = _AUDIT_PLAYWRIGHT_FALLBACK
    primary_retries = 0 if fast_fallback else 3
    primary_variants = [DEFAULT_HEADERS] if fast_fallback else None
    use_playwright_only = _AUDIT_PLAYWRIGHT_ONLY
    if use_playwright_only:
        homepage_html, homepage_status, homepage_error = _fetch_with_playwright(fetch_target)
    else:
        homepage_html, homepage_status, homepage_error = _attempt_fetch(
            fetch_target,
            primary_retries,
            2.0,
            False,
            header_variants=primary_variants,
        )
    if _AUDIT_DEBUG:
        print(f"[audit] homepage fetch status={homepage_status} error={homepage_error}")
    if homepage_status in {401, 403, 429}:
        blocked_for_aux = True
        if homepage_html is not None:
            homepage_html = None
        if not homepage_error:
            homepage_error = f"HTTP {homepage_status}"
    if homepage_html is None and homepage_status in REDIRECT_STATUS_CODES and not use_playwright_only:
        upgraded = _prefer_https(fetch_target)
        if upgraded != fetch_target:
            fetch_target = upgraded
            base_url_for_aux = fetch_target
            homepage_html, homepage_status, homepage_error = _attempt_fetch(
                fetch_target,
                2,
                2.0,
                False,
                header_variants=None,
            )
            if _AUDIT_DEBUG:
                print(f"[audit] https retry status={homepage_status} error={homepage_error}")

    if homepage_html is None and not (_AUDIT_PLAYWRIGHT_FALLBACK and homepage_status == 403) and not use_playwright_only:
        amp_candidate = _ensure_amp_variant(fetch_target)
        if amp_candidate != fetch_target:
            fetch_target = amp_candidate
            amp_html, amp_status, amp_error = _attempt_fetch(
                fetch_target,
                2,
                2.5,
                False,
                header_variants=None,
            )
            if amp_html:
                homepage_html = amp_html
                homepage_status = amp_status
                homepage_error = amp_error
                used_amp_variant = True
            else:
                homepage_status = amp_status
                homepage_error = amp_error
            if _AUDIT_DEBUG:
                print(f"[audit] amp retry status={homepage_status} error={homepage_error}")

    if homepage_html is None and not (_AUDIT_PLAYWRIGHT_FALLBACK and homepage_status == 403) and not use_playwright_only:
        brotli_candidate = _prefer_https(url)
        homepage_html, homepage_status, homepage_error = _attempt_fetch(
            brotli_candidate,
            2,
            3.0,
            True,
            header_variants=None,
        )
        if homepage_html:
            fetch_target = brotli_candidate
            base_url_for_aux = fetch_target
            used_brotli_variant = True
        if _AUDIT_DEBUG:
            print(f"[audit] brotli retry status={homepage_status} error={homepage_error}")

    if (
        homepage_html is None
        and _AUDIT_PLAYWRIGHT_FALLBACK
        and not use_playwright_only
        and _should_try_playwright(homepage_status, homepage_error)
    ):
        if sync_playwright is None:
            if _AUDIT_DEBUG:
                print("[audit] playwright fallback skipped: Playwright not installed")
            homepage_error = "Playwright fallback unavailable: Playwright not installed"
        else:
            homepage_html, homepage_status, homepage_error = _fetch_with_playwright(fetch_target)
            if _AUDIT_DEBUG:
                print(f"[audit] playwright fallback status={homepage_status} error={homepage_error}")

    time.sleep(REQUEST_PAUSE_SECONDS)
    if strict and homepage_html is None and _is_timeout_error(homepage_status, homepage_error):
        raise HomepageFetchTimeoutError(fetch_target, homepage_error, homepage_status)
    if blocked_for_aux:
        if _AUDIT_DEBUG:
            print(f"[audit] skipping sitemap/rss due to access restrictions url={base_url_for_aux}")
        sitemap_data = {"used": False, "notices": False, "urls": []}
        rss_data = {"feed_found": False, "notices": False, "urls": []}
    else:
        if _AUDIT_DEBUG:
            print(f"[audit] sitemap check url={base_url_for_aux}")
        sitemap_data = check_sitemap(base_url_for_aux)
        time.sleep(REQUEST_PAUSE_SECONDS)
        if _AUDIT_DEBUG:
            print(f"[audit] rss check url={base_url_for_aux}")
        rss_data = check_rss(base_url_for_aux)
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
    privacy_features, privacy_flags, privacy_score, privacy_summary = detect_privacy_features(homepage_html)

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
    if used_amp_variant:
        all_notes.append("Used AMP fallback (?output=amp) to fetch homepage")
    if used_brotli_variant:
        all_notes.append("Used Brotli fallback to decode homepage HTML")

    if homepage_html and base_url_for_aux:
        homepage_html = _inject_base_href(homepage_html, base_url_for_aux)
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
        "Privacy Features": privacy_features,
        "Privacy Flags": privacy_flags,
        "Privacy Score": privacy_score,
        "Privacy Summary": privacy_summary,
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
        "Privacy Summary",
        "Privacy Score",
        "Privacy Flags",
        "Privacy Features",
        "Audit Sources",
        "Audit Notes",
    ]
    for col in audit_columns:
        if col not in df.columns:
            df[col] = ""

    columns_in_order = list(df.columns)

    def _resolve_column_name(name: str) -> str | None:
        target = name.strip().lower()
        for existing in columns_in_order:
            if existing.strip().lower() == target:
                return existing
        return None

    def _clean_entry(value) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _get_existing_value(row: pd.Series, primary: str, aliases: list[str] | None = None) -> str:
        search_keys = [primary]
        if aliases:
            search_keys.extend(aliases)
        for key in search_keys:
            resolved = _resolve_column_name(key)
            if not resolved:
                continue
            raw_value = row.get(resolved, "")
            cleaned = _clean_entry(raw_value)
            if cleaned:
                return cleaned
        return ""

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

        existing_chain_value = _get_existing_value(
            row,
            "Chain Owner",
            aliases=["Chain", "Owner", "Chain owner", "ChainOwner", "Owner Chain"],
        )
        normalized_chain = existing_chain_value.lower()
        if normalized_chain and normalized_chain not in MANUAL_REVIEW_STATUSES and not normalized_chain.startswith("manual review"):
            results["Chain Owner"] = existing_chain_value

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
