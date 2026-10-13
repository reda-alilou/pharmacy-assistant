import argparse
import json
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

DATASET = ROOT / "data/processed/ammps_medications.jsonl"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )
    return " ".join(text.casefold().split())


def search_medications(query: str) -> list[dict]:
    query = normalize(query)

    if not query:
        raise ValueError("Search query cannot be empty.")

    matches = []

    with DATASET.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            medication = json.loads(line)

            brand = normalize(medication["brand_name"])
            substance = normalize(medication["active_substance"])

            if query in brand or query in substance:
                matches.append(medication)

    return matches


def main():
    parser = argparse.ArgumentParser(
        description="Search the Moroccan medication dataset."
    )

    parser.add_argument(
        "query",
        help="Medication name or active substance",
    )

    args = parser.parse_args()

    results = search_medications(args.query)

    output = {
        "query": args.query,
        "result_count": len(results),
        "medications": results,
    }

    print(json.dumps(
        output,
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()