# Newspaper Auditor Specification

## 🎯 Purpose

Automates the auditing of newspaper websites to classify digital publishing practices.
The script accepts a CSV of papers and enriches it with audit columns based on signals from:

* Homepage HTML
* Sitemap XML
* RSS feeds
* Chain-level heuristics (publisher-specific patterns)

---

## 📥 Input

* **CSV file** containing (at minimum):

  * `Paper Name`
  * `Website Url`
* May also include:

  * `City`, `State`, `Phone Number`, `Mailing Address`, `County`
* Script called as:

  ```bash
  python audit_newspapers.py %3Cinput_csv%3E [--force]
  ```

---

## 📤 Output

* A new CSV:

  ```
  <basename>_Audit.csv
  ```
* Contains all input columns plus audit fields:

  * `Has PDF Edition?` (Yes/No)
  * `PDF-Only?` (Yes/No/Manual Review)
  * `Paywall?` (Yes/No/Manual Review)
  * `Free Public Notices?` (Yes/No/Manual Review)
  * `Mobile Responsive?` (Yes/No/Manual Review)
  * `Audit Sources` (Homepage/Sitemap/RSS/Heuristic markers)
  * `Audit Notes` (text explanations for decisions)

---

## 🔄 Processing Flow

### 1. **Fetch Sources**

* Homepage HTML (`fetch_url`, timeout=6s)
* Sitemap(s): `/sitemap.xml`, `/sitemap_index.xml`, `/sitemap-news.xml` (timeout=12s)
* RSS feed(s): `/feed`, `/rss`, `/rss.xml`, `/index.rss` (timeout=6s)

### 2. **Detect Publisher Chain (Heuristics)**

* Homepage text scanned for:

  * `"Part of the USA TODAY Network"`, `"eNewspaper"`, `"USA Today"`, `"Gannett"` → Gannett
  * `"Hearst Newspapers"`, `"© Hearst"` → Hearst
  * `"Lee Enterprises"` → Lee
  * `"CNHI LLC"`, `"CNHI Media"` → CNHI
* If detected:

  * Force `PDF-Only? = No`
  * Force `Paywall? = Yes`
  * Add `Heuristic:<Chain>` to `Audit Sources`

### 3. **Feature Detectors**

Each detector returns a value, contributing sources, and explanatory notes.

#### a) **Has PDF Edition? / PDF-Only?**

* Homepage: `.pdf` links → `Has PDF Edition? = Yes`
* Sitemap: `.pdf` URLs → `Has PDF Edition? = Yes`
* RSS present → overrides PDF-only = No
* PDF-Only = Yes if:

  * PDFs detected
  * Sitemap ≥ 80% PDF links
  * No RSS feed

#### b) **Paywall?**

* Homepage keywords: `subscribe`, `paywall`, `membership`, etc.
* Sitemap URLs containing `subscribe`, `membership`, `registration`, `premium`.
* RSS feed containing paywall hints.
* Chain heuristic override = Yes.

#### c) **Free Public Notices?**

* Homepage keywords: `public notice`, `legal notice`, `legals`, `classifieds`.
* Sitemap URLs containing notice terms.
* RSS items containing notice terms.

#### d) **Mobile Responsive?**

* Homepage `<meta name="viewport">` → Yes
* Homepage CSS contains `@media screen and (max-width` → Yes
* Homepage references responsive frameworks (`bootstrap`, `tailwind`, `foundation`) → Yes

---

## ⚙️ Execution Rules

* **Resume mode:** If `<basename>_Audit.csv` already exists, script resumes from it (skips rows with already-completed audit values).
* **Force mode (`--force`):** Overwrites any existing audit file and re-runs all entries.
* Saves progress every 5 rows.

---

## 🧩 Example Output (row)

| Paper Name         | Website Url                                                    | Has PDF Edition? | PDF-Only? | Paywall? | Free Public Notices? | Mobile Responsive? | Audit Sources                           | Audit Notes                                                                                                                                                                                                   |
| ------------------ | -------------------------------------------------------------- | ---------------- | --------- | -------- | -------------------- | ------------------ | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Abernathy Advocate | [https://abernathyadvocate.com](https://abernathyadvocate.com) | Yes              | No        | Yes      | No                   | Yes                | Homepage+Sitemap+RSS+Heuristic\:Gannett | Found PDF links on homepage \| Sitemap shows 10% PDFs \| RSS present (indicates article content) \| Chain heuristic: Gannett, not PDF-only \| Homepage contains paywall keywords \| Viewport meta tag present |

---

## 🚀 Next Steps (Future Ideas)

* Add **scoring system** (weights per feature, confidence scores).
* Add **summary stats** at end of run (counts per column).
* Support **multi-threading** for faster audits.
* Expand heuristics for more chains (Lee, McClatchy, Ogden, etc.).
* Integrate with Flask/DB UI for browsing & re-runs.
---
# 👩‍💻 Developer Guide: Extending the Newspaper Audit CLI

This guide explains how to **add new checks or extend existing ones** in the audit script.

---

## 🏗️ Architecture Overview

The script has three main layers:

1. **Source Fetchers**

   * `fetch_url(url, timeout)` → grabs raw HTML/XML text
   * `check_sitemap(url)` → extracts sitemap URLs, counts PDFs, finds notice keywords
   * `check_rss(url)` → checks for RSS feeds, paywall hints, and notices

2. **Feature Detectors**

   * Each detector answers a specific **audit question** (`Has PDF?`, `Paywall?`, etc.)
   * Signature:

     ```python
     def detect_feature(homepage_html, sitemap_data, rss_data, chain_detected):
         return value, sources, notes
     ```

     * `value`: "Yes", "No", or "Manual Review"
     * `sources`: list of which inputs were used (`Homepage`, `Sitemap`, `RSS`, `Heuristic`)
     * `notes`: human-readable explanation

3. **Audit Orchestrator**

   * `quick_audit(url)` runs all detectors and merges results into a dict.
   * `process_csv(input_file)` iterates through a CSV and saves results.

---

## 🛠️ How to Add a New Detector

### Example: Detect Social Media Links

1. **Create detector function** in the same style:

   ```python
   def detect_social_links(homepage_html):
       sources, notes = [], []
       if not homepage_html:
           return "Manual Review", sources, ["No homepage HTML available"]

       if "facebook.com" in homepage_html.lower():
           notes.append("Facebook link detected")
           sources.append("Homepage")
       if "twitter.com" in homepage_html.lower():
           notes.append("Twitter link detected")
           sources.append("Homepage")

       return ("Yes" if sources else "No"), sources, notes
   ```

2. **Add to quick\_audit**:

   ```python
   social, social_sources, social_notes = detect_social_links(homepage_html)
   all_sources += social_sources
   all_notes += social_notes
   audit["Social Media Links?"] = social
   ```

3. **Update audit\_columns** in `process_csv` so it appears in the CSV:

   ```python
   audit_columns = [
       "Has PDF Edition?", "PDF-Only?", "Paywall?",
       "Free Public Notices?", "Mobile Responsive?",
       "Audit Sources", "Audit Notes", "Social Media Links?"
   ]
   ```

---

## 🔑 Tips for Extending

* **Keep detectors independent**: Each detector should only worry about its feature.
* **Return notes** generously: The `Audit Notes` column is your debugging tool.
* **Use sources wisely**: Mark which inputs contributed to the result.
* **Fail gracefully**: If no signal is found, return `"Manual Review"`.

---

## 🚦 Testing Changes

1. Run on a **small CSV** (5–10 papers).
2. Inspect the `Audit Notes` column — verify logic matches human expectations.
3. Incrementally expand to bigger lists (100+ papers).

---

## 📌 Where to Add Heuristics

Publisher/chain heuristics live in:

```python
def detect_chain(homepage_html):
    ...
```

To add a new chain, e.g. **McClatchy**:

```python
if "mcclatchy" in html_lower or "part of mcclatchy" in html_lower:
    return "McClatchy"
```

Then the `detect_pdf` and `detect_paywall` functions will automatically respect it.

---

## 🧭 Future-Proofing

* Want scoring? → Each detector can return `(value, confidence, notes)`.
* Want multi-threading? → Wrap `quick_audit(url)` in `concurrent.futures`.
* Want DB/UI integration? → Reuse detectors unchanged; just replace CSV I/O with database queries.

---

✅ With this structure, you (or any dev) can safely extend the system by **adding detectors** or **expanding existing ones**, without touching the whole script.

---
