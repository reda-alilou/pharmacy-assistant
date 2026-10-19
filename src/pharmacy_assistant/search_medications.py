"""CLI and backwards-compatible Python entry point for catalogue search."""

import argparse
import json
from functools import lru_cache

from pharmacy_assistant.catalog import DATASET, MedicationCatalog, normalize
from pharmacy_assistant.models import MedicationSearchRequest


@lru_cache(maxsize=1)
def get_catalog() -> MedicationCatalog:
    return MedicationCatalog.from_path(DATASET)


def search_medications(
    query: str,
    *,
    strength: str | None = None,
    form: str | None = None,
    presentation: str | None = None,
) -> list[dict]:
    """Keep the original list-of-dictionaries interface for Python callers."""
    request = MedicationSearchRequest(
        query=query, strength=strength, form=form, presentation=presentation
    )
    result = get_catalog().search(request)
    return [record.model_dump(mode="json") for record in result.medications]


def main():
    parser = argparse.ArgumentParser(description="Search the partial Moroccan medication catalogue.")
    parser.add_argument("query", help="Medication name or active substance")
    parser.add_argument("--strength", help="Strength, e.g. '15 mg'")
    parser.add_argument("--form", help="Pharmaceutical form")
    parser.add_argument("--presentation", help="Package presentation, e.g. '20'")
    args = parser.parse_args()
    try:
        request = MedicationSearchRequest(**vars(args))
    except ValueError as error:
        parser.error(str(error))
    result = get_catalog().search(request)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
