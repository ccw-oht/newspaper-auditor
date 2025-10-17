import re
import csv
import json
import requests
from bs4 import BeautifulSoup

URL = "https://inanews.com/find-iowa-newspaper/"
OUTPUT_FILE = "iowa_newspapers.csv"

def extract_newspapers():
    r = requests.get(URL)
    r.raise_for_status()
    html = r.text

    # find the javascript block with map data
    match = re.search(r"var locations\s*=\s*(\[.*?\]);", html, re.DOTALL)
    if not match:
        print("Could not find location data in source.")
        return []

    # parse the JSON-like structure
    raw = match.group(1)

    # Clean up for JSON parsing
    # Some pages have invalid JS (e.g., single quotes), so fix that
    fixed = re.sub(r"(?<=\{|,)\s*([a-zA-Z0-9_]+)\s*:", r'"\1":', raw)  # quote keys if needed
    fixed = fixed.replace("'", '"')

    # parse as JSON if possible
    try:
        data = json.loads(fixed)
    except Exception:
        # fallback: regex parse simpler pattern
        pattern = re.compile(
            r"\['(.*?)','(.*?)','(.*?)','(.*?)','(.*?)','(.*?)','(.*?)','(.*?)','(.*?)','(.*?)','(.*?)'\]"
        )
        data = pattern.findall(raw)

    newspapers = []
    for item in data:
        if isinstance(item, dict):
            name = item.get("name", "")
            city = item.get("city", "")
            county = item.get("county", "")
            address = item.get("address", "")
            phone = item.get("phone", "")
            fax = item.get("fax", "")
            website = item.get("website", "")
            email = item.get("email", "")
            pub_days = item.get("pub_days", "")
            circ = item.get("circulation", "")
            staff = item.get("staff", "")
        else:
            # fallback for tuple-style list
            (name, city, county, address, phone, fax, website,
             email, pub_days, circ, staff, *_rest) = item + ("",)*(12-len(item))

        newspapers.append({
            "Name": name.strip(),
            "City": city.strip(),
            "County": county.strip(),
            "Address": address.strip(),
            "Phone": phone.strip(),
            "Fax": fax.strip(),
            "Website": website.strip(),
            "Email": email.strip(),
            "Publication Days": pub_days.strip(),
            "Circulation": circ.strip(),
            "Staff / Contacts": staff.strip(),
        })

    return newspapers


def save_csv(records):
    if not records:
        print("No data extracted.")
        return

    keys = records[0].keys()
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)

    print(f"✅ Saved {len(records)} records to {OUTPUT_FILE}")


if __name__ == "__main__":
    papers = extract_newspapers()
    save_csv(papers)
