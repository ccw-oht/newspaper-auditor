import argparse
import csv

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

URL = "https://inanews.com/find-iowa-newspaper/"
DEFAULT_OUTPUT = "iowa_newspapers.csv"

def fetch_html(source_file: str | None = None) -> str:
    if source_file:
        with open(source_file, "r", encoding="utf-8") as handle:
            return handle.read()

    session = requests.Session()
    session.headers.update(HEADERS)

    r = session.get(URL, timeout=10)
    r.raise_for_status()
    return r.text


def extract_newspapers(html: str):
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.map-list-item")

    newspapers = []
    for li in items:
        name_el = li.select_one(".neon-result-title strong") or li.select_one(".neon-result-title")
        name = name_el.get_text(strip=True) if name_el else ""

        address_lines = []
        for address_class in [".mailing-address", ".mailing-address2"]:
            addr_el = li.select_one(address_class)
            if addr_el:
                address_lines.extend(list(addr_el.stripped_strings))
        address = ", ".join(address_lines)

        phone = fax = website = email = ""
        contact_block = li.select_one(".contact")
        if contact_block:
            for entry in contact_block.find_all("div", recursive=False):
                text = entry.get_text(" ", strip=True)
                if text.startswith("Phone:"):
                    phone = text.split("Phone:", 1)[1].strip()
                elif text.startswith("Fax:"):
                    fax = text.split("Fax:", 1)[1].strip()
                elif text.startswith("Website:"):
                    link = entry.find("a")
                    website = link.get("href", "").strip() if link else text.split("Website:", 1)[1].strip()
                elif text.startswith("Email:"):
                    link = entry.find("a")
                    if link and link.get("href", "").startswith("mailto:"):
                        email = link.get("href")[7:].strip()
                    else:
                        email = (link.get_text(strip=True) if link else text.split("Email:", 1)[1]).strip()

        pub_days = circ = ""
        pub_block = li.select_one(".publication-info")
        if pub_block:
            for entry in pub_block.find_all("div", recursive=False):
                text = entry.get_text(strip=True)
                if text.startswith("Publication Days:"):
                    pub_days = text.split("Publication Days:", 1)[1].strip()
                elif text.startswith("Circulation:"):
                    circ = text.split("Circulation:", 1)[1].strip()

        staff_entries = []
        for contact in li.select(".contact-content .account-contact"):
            name_part = contact.select_one(".contact-name")
            dept_part = contact.select_one(".contact-department")
            name_value = name_part.get_text(strip=True) if name_part else ""
            dept_value = dept_part.get_text(strip=True) if dept_part else ""
            if name_value or dept_value:
                if dept_value:
                    staff_entries.append(f"{name_value} ({dept_value})" if name_value else dept_value)
                else:
                    staff_entries.append(name_value)
        staff = "; ".join(staff_entries)

        city = li.get("data-city", "").strip()
        county = li.get("data-county", "").strip()

        newspapers.append(
            {
                "Name": name,
                "City": city,
                "County": county,
                "Address": address,
                "Phone": phone,
                "Fax": fax,
                "Website": website,
                "Email": email,
                "Publication Days": pub_days,
                "Circulation": circ,
                "Staff / Contacts": staff,
            }
        )

    return newspapers


def save_csv(records, output_path: str):
    if not records:
        print("No data extracted.")
        return

    keys = records[0].keys()
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)

    print(f"✅ Saved {len(records)} records to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Iowa newspaper listings")
    parser.add_argument(
        "--source-file",
        dest="source_file",
        help="Optional local HTML file to parse instead of fetching from the web",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default=DEFAULT_OUTPUT,
        help=f"Where to write CSV results (default: {DEFAULT_OUTPUT})",
    )

    args = parser.parse_args()

    html_text = fetch_html(args.source_file)
    papers = extract_newspapers(html_text)
    save_csv(papers, args.output)
