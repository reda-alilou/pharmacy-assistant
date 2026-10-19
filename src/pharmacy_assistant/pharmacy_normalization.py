"""Reviewed lexical equivalents for this partial directory, not transliteration."""

import re

from pharmacy_assistant.medication_normalization import arabic_normalize


LABELS = {"pharmacie", "pharmacy", "صيدلية", "صيدليه", "الصيدلية", "الصيدليه",
          "saydaliya", "ssaydaliya", "saydalia"}
ARTICLES = {"de", "du", "des", "la", "le", "les", "l", "d"}


def directory_term(value: str) -> str:
    text = arabic_normalize(value)
    text = re.sub(r"^(?:ال)?صيدلي[ةه]", "", text).strip()
    words = re.sub(r"[^\w]+", " ", text).split()
    return " ".join(word for word in words if word not in LABELS | ARTICLES)


# Assistant-reviewed spellings of names present in pharmacies_rabat.jsonl.
# Unknown spellings are never transliterated, translated or fuzzily selected.
PHARMACY_NAME_ALIASES = {
    "ابن نفيس": "ibn nafis", "ابننفيس": "ibn nafis", "ibnou nafis": "ibn nafis",
    "ابن سينا": "ibn sina", "ابنسينا": "ibn sina", "ibnou sina": "ibn sina",
    "باب جديد": "bab jdid", "باب مراكش": "bab marrakech",
    "فاطمة الزهراء": "fatima zahraa", "النهضة": "nahda", "الحكمة": "al hikma",
}
NAME_ALIASES = {directory_term(key): directory_term(value) for key, value in PHARMACY_NAME_ALIASES.items()}
AREA_ALIASES = {"اكدال": "agdal", "حي اكدال": "agdal", "حسان": "hassan",
                "حي الرياض": "riad", "حيالرياض": "riad", "hay riad": "riad", "hay ryad": "riad", "ryad": "riad"}


def pharmacy_name(value):
    term = directory_term(value)
    return NAME_ALIASES.get(term, term)


def area_term(value):
    text = directory_term(value)
    for source, target in sorted(AREA_ALIASES.items(), key=lambda item: -len(item[0])):
        text = re.sub(r"(?<!\w)" + re.escape(source) + r"(?!\w)", target, text)
    return text


def contains_tokens(text, query):
    return bool(query) and f" {query} " in f" {text} "
