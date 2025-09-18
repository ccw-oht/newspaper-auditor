import requests
import pandas as pd
import os
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# Keywords/signals
paywall_keywords = ["subscribe", "paywall", "metered", "membership", "premium", "registration"]
public_notice_keywords = ["public notice", "legal notice", "legals", "notices", "classifieds", "obituaries"]

# Helper: fetch a URL safely
def fetch_url(url, timeout=6):
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return resp.text
    except Exception:
        return None
    return None

# Helper: check sitemap.xml
def check_sitemap(base_url):
    sitemap_paths = ["/sitemap.xml", "/sitemap_index.xml", "/sitemap-news.xml"]
    pdf_count, total = 0, 0
    notices_found = False
    urls = []
    used = False

    for path in sitemap_paths:
        sitemap_url = base_url.rstrip("/") + path
        xml_text = fetch_url(sitemap_url, timeout=12)
        if not xml_text:
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

    for path in rss_paths:
        rss_url = base_url.rstrip("/") + path
        xml_text = fetch_url(rss_url, timeout=6)
        if not xml_text:
            continue

        feed_found = True
        xml_lower = xml_text.lower()
        if any(k in xml_lower for k in paywall_keywords):
            paywall_hint = True
        if any(k in xml_lower for k in public_notice_keywords):
            notices_found = True

        break  # first valid feed is enough

    return {"feed_found": feed_found, "paywall_hint": paywall_hint, "notices": notices_found}

# --- Feature Detectors ---

def detect_chain(homepage_html):
    if not homepage_html:
        return None
    html_lower = homepage_html.lower()
    if ("part of the usa today network" in html_lower or 
        "enewspaper" in html_lower or 
        "usa today" in html_lower or 
        "gannett" in html_lower):
        return "Gannett"
    if "hearst newspapers" in html_lower or "© hearst" in html_lower:
        return "Hearst"
    if "lee enterprises" in html_lower:
        return "Lee"
    if "cnhi llc" in html_lower or "cnhi media" in html_lower:
        return "CNHI"
    return None

def detect_pdf(homepage_html, sitemap_data, rss_data, chain_detected):
    sources, notes = [], []
    has_pdf = "No"
    pdf_only = "Manual Review"

    if homepage_html:
        soup = BeautifulSoup(homepage_html, "html.parser")
        pdf_links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].endswith(".pdf")]
        if pdf_links:
            has_pdf = "Yes"
            notes.append(f"Found {len(pdf_links)} PDF links on homepage")
            sources.append("Homepage")

    if sitemap_data["used"]:
        if sitemap_data["pdf_ratio"] > 0:
            has_pdf = "Yes"
            notes.append(f"Sitemap shows {sitemap_data['pdf_ratio']:.0%} PDF URLs")
        sources.append("Sitemap")

    if rss_data["feed_found"]:
        sources.append("RSS")
        notes.append("RSS present (indicates article content)")

    # Decide PDF-only
    if chain_detected:
        pdf_only = "No"
        notes.append(f"Chain heuristic: {chain_detected}, not PDF-only")
    elif has_pdf == "Yes" and not rss_data["feed_found"] and sitemap_data["pdf_ratio"] > 0.8:
        pdf_only = "Yes"
        notes.append("PDF-only: Sitemap dominated by PDFs and no RSS")
    else:
        pdf_only = "No"

    return has_pdf, pdf_only, sources, notes

def detect_paywall(homepage_html, sitemap_data, rss_data, chain_detected):
    sources, notes = [], []
    if chain_detected:
        notes.append(f"Chain heuristic: {chain_detected}, default Paywall=Yes")
        return "Yes", [f"Heuristic:{chain_detected}"], notes

    if homepage_html and any(k in homepage_html.lower() for k in paywall_keywords):
        notes.append("Homepage contains paywall keywords")
        return "Yes", ["Homepage"], notes

    if sitemap_data["used"]:
        if any("subscribe" in loc or "membership" in loc or "registration" in loc or "premium" in loc for loc in sitemap_data.get("urls", [])):
            notes.append("Sitemap contains subscription-related URLs")
            return "Yes", ["Sitemap"], notes

    if rss_data["feed_found"] and rss_data["paywall_hint"]:
        notes.append("RSS feed contains paywall hints")
        return "Yes", ["RSS"], notes

    notes.append("No paywall signals found")
    return "No", sources, notes

def detect_public_notices(homepage_html, sitemap_data, rss_data):
    sources, notes = [], []
    if homepage_html and any(k in homepage_html.lower() for k in public_notice_keywords):
        notes.append("Homepage contains public notice keywords")
        return "Yes", ["Homepage"], notes

    if sitemap_data["used"] and sitemap_data["notices"]:
        notes.append("Sitemap contains notice-related URLs")
        return "Yes", ["Sitemap"], notes

    if rss_data["feed_found"] and rss_data["notices"]:
        notes.append("RSS feed contains notice keywords")
        return "Yes", ["RSS"], notes

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

def quick_audit(url):
    audit = {
        "Has PDF Edition?": "Manual Review",
        "PDF-Only?": "Manual Review",
        "Paywall?": "Manual Review",
        "Free Public Notices?": "Manual Review",
        "Mobile Responsive?": "Manual Review",
        "Audit Sources": "",
        "Audit Notes": ""
    }

    if not isinstance(url, str) or not url.strip():
        return audit

    if not url.startswith("http"):
        url = "http://" + url

    homepage_html = fetch_url(url)
    sitemap_data = check_sitemap(url)
    rss_data = check_rss(url)
    chain_detected = detect_chain(homepage_html)

    has_pdf, pdf_only, pdf_sources, pdf_notes = detect_pdf(homepage_html, sitemap_data, rss_data, chain_detected)
    paywall, paywall_sources, paywall_notes = detect_paywall(homepage_html, sitemap_data, rss_data, chain_detected)
    notices, notice_sources, notice_notes = detect_public_notices(homepage_html, sitemap_data, rss_data)
    responsive, resp_sources, resp_notes = detect_responsive(homepage_html)

    all_sources = pdf_sources + paywall_sources + notice_sources + resp_sources
    all_notes = pdf_notes + paywall_notes + notice_notes + resp_notes

    audit.update({
        "Has PDF Edition?": has_pdf,
        "PDF-Only?": pdf_only,
        "Paywall?": paywall,
        "Free Public Notices?": notices,
        "Mobile Responsive?": responsive,
        "Audit Sources": "+".join(set(all_sources)) if all_sources else "None",
        "Audit Notes": " | ".join(all_notes) if all_notes else ""
    })

    return audit

def process_csv(input_file, force=False):
    df = pd.read_csv(input_file)

    audit_columns = ["Has PDF Edition?", "PDF-Only?", "Paywall?", "Free Public Notices?", "Mobile Responsive?", "Audit Sources", "Audit Notes"]
    for col in audit_columns:
        if col not in df.columns:
            df[col] = ""

    base = os.path.splitext(os.path.basename(input_file))[0]
    out_file = f"{base}_Audit.csv"

    if os.path.exists(out_file) and not force:
        print(f"🔄 Resuming audit from cache: {out_file}")
        df = pd.read_csv(out_file)
    elif os.path.exists(out_file) and force:
        print(f"⚠️ Overwriting existing audit file: {out_file}")

    total = len(df)
    for idx, row in df.iterrows():
        if not force and all(str(row.get(col, "")).strip() not in ["", "Manual Review", "Manual Review (Timeout)", "Manual Review (Error)", ""] for col in audit_columns[:-1]):
            continue

        url = row.get("Website Url", "")
        results = quick_audit(url)
        for col, val in results.items():
            df.loc[idx, col] = val

        print(f"[{idx+1}/{total}] Audited: {row.get('Paper Name', 'Unknown')} ({url}) → Sources: {results['Audit Sources']}")

        if idx % 5 == 0:
            df.to_csv(out_file, index=False)

    df.to_csv(out_file, index=False)
    print(f"\n✅ Audit complete. Results saved to {out_file}")
    
def run_audit(url: str):
    return quick_audit(url)
