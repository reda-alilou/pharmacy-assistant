"""Parse and collect bounded medication samples from the two secondary sources."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from pharmacy_assistant.collection_http import SourceClient, atomic_replace, write_json
from pharmacy_assistant.process_ammps import normalize_price


ROOT = Path(__file__).resolve().parents[2]
DOSE_PATTERN = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:MCG|MG|MBQ|GBQ|µG|μG|UG|UI|U\.I\.|ML|G|%)\b|\d+(?:[.,]\d+)?\s*%",
    re.I,
)


def text(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "get_text"):
        value = value.get_text(" ", strip=True)
    return " ".join(str(value).split()) or None


def source_price(value: str | None) -> float | None:
    if not value:
        return None
    value = re.sub(r"\s*(?:dhs?|mad)\s*$", "", value, flags=re.I).replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+,\d{2}", value):
        value = value.replace(".", "").replace(",", ".")
    return normalize_price(value)


def split_title(title: str) -> tuple[str, str | None]:
    head, separator, form = title.partition(", ")
    dose = DOSE_PATTERN.search(head)
    brand = head[:dose.start()].strip() if dose else head.strip()
    if not brand:
        raise ValueError(f"Cannot identify brand in title: {title!r}")
    return brand, form.strip() if separator else None


def medication_observation(source: str, identifier: str, title: str, fields: dict,
                           url: str, fetched_at: str, updated_at: str | None = None) -> dict:
    brand, form = split_title(title)
    return {
        "source": source, "source_record_id": identifier, "source_url": url,
        "fetched_at_utc": fetched_at, "source_updated_at_raw": updated_at,
        "title": title, "brand_name": brand, "dosage": fields.get("Dosage"),
        "form": form, "presentation": fields.get("Présentation"),
        "active_substance": fields.get("Composition"),
        "manufacturer": fields.get("Distributeur ou fabriquant"),
        "commercialization_status": fields.get("Statut"),
        "therapeutic_class": fields.get("Classe thérapeutique"),
        "ppv_price_mad": source_price(fields.get("PPV")),
        "hospital_price_mad": source_price(fields.get("Prix hospitalier")),
        "atc_code": fields.get("Code ATC"), "reimbursement_raw": fields.get("Remboursement"),
        "reimbursement_base_mad": source_price(fields.get("Base de remboursement / PPV")),
        "product_nature": fields.get("Nature du Produit"), "raw_fields": fields,
    }


def parse_medicament_detail(html: str, url: str, fetched_at: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = text(soup.select_one("h1.main-title"))
    fields = {}
    for item in soup.select(".medicine-details .detail-item"):
        label, value = text(item.select_one(".detail-header")), text(item.select_one(".detail-content"))
        if label and value:
            if label in fields and fields[label] != value:
                raise ValueError(f"Conflicting detail labels at {url}")
            fields[label] = value
    if not title or not fields:
        raise ValueError(f"Medication detail structure missing at {url}")
    updated = next((text(a).removeprefix("Mise à jour le:").strip()
                    for a in soup.select(".report-link") if (text(a) or "").startswith("Mise à jour le:")), None)
    return medication_observation("medicament.ma", urlparse(url).path.strip("/").split("/")[-1],
                                  title, fields, url, fetched_at, updated)


def parse_saydalia_listing(html: str, fetched_at: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for item in soup.select("article.w-grid-item.product"):
        title_node = item.select_one(".post_title a")
        title = text(title_node)
        if not title_node or not title or not item.get("data-id"):
            raise ValueError("Malformed Saydalia product")
        fields = {}
        # Desktop and expandable attributes repeat the same information.
        for attribute in item.select("[class*='woocommerce-product-attributes-item--attribute_']"):
            label = (text(attribute.select_one(".w-post-elm-before")) or "").rstrip(": ")
            value = text(attribute.select_one(".woocommerce-product-attributes-item__value"))
            label = {"remboursement": "Remboursement", "Nature": "Nature du Produit"}.get(label, label)
            if label and value:
                if label in fields and fields[label] != value:
                    raise ValueError("Saydalia repeated attributes disagree")
                fields[label] = value
        price = text(item.select_one(".price .woocommerce-Price-amount"))
        if price:
            fields["PPV"] = price
        records.append(medication_observation(
            "saydalia.ma", item["data-id"], title, fields,
            title_node["href"], fetched_at,
        ))
    if not records:
        raise ValueError("No Saydalia medication products found")
    return records


def write_jsonl(path: Path, records: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    atomic_replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["medicament", "saydalia"], required=True)
    parser.add_argument("--letters", nargs="+", default=["A", "B", "D"])
    parser.add_argument("--limit-per-letter", type=int, default=20)
    parser.add_argument("--pages", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.limit_per_letter <= 20 or not 1 <= args.pages <= 10:
        parser.error("Use a bounded sample: 1–20 records per letter, 1–10 Saydalia pages")
    if any(not re.fullmatch("[A-Z]", letter) for letter in args.letters):
        parser.error("Letters must be A through Z")
    records = []
    if args.source == "medicament":
        directory = ROOT / "data/raw/medicament_ma"
        with SourceClient("https://medicament.ma", directory) as client:
            seen = set()
            for letter in args.letters:
                html, _ = client.get(f"https://medicament.ma/listing-des-medicaments/?lettre={letter}", f"listing_{letter}")
                soup = BeautifulSoup(html, "html.parser")
                urls = list(dict.fromkeys(a["href"] for a in soup.select('a[href*="/medicament/"]')))
                if not urls:
                    raise ValueError(f"No medication links for {letter}")
                for url in urls[:args.limit_per_letter]:
                    if url in seen:
                        continue
                    seen.add(url)
                    name = "detail_" + hashlib.sha256(url.encode()).hexdigest()[:16]
                    detail, meta = client.get(url, name)
                    record = parse_medicament_detail(detail, url, meta["fetched_at_utc"])
                    write_json(directory / f"{name}.json", record)
                    records.append(record)
                    print(f"Medicament.ma: {len(records)} records ({record['brand_name']})", flush=True)
    else:
        directory = ROOT / "data/raw/saydalia_medications"
        with SourceClient("https://saydalia.ma", directory) as client:
            for page in range(1, args.pages + 1):
                url = "https://saydalia.ma/fr/medicaments/" + (f"page/{page}/" if page > 1 else "")
                html, meta = client.get(url, f"page_{page}")
                parsed = parse_saydalia_listing(html, meta["fetched_at_utc"])
                write_json(directory / f"page_{page}.json", parsed)
                records.extend(parsed)
                print(f"Saydalia medication sample: page {page}, {len(records)} records", flush=True)
    identifiers = [record["source_record_id"] for record in records]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate secondary medication IDs")
    write_jsonl(ROOT / f"data/processed/{args.source}_medications.jsonl", records)
    write_json(directory / "manifest.json", {"source": args.source, "scope": "sample",
               "record_count": len(records), "complete_catalogue": False})


if __name__ == "__main__":
    main()
