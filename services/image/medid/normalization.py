from __future__ import annotations

import math
import re
import unicodedata

_DOSAGE_RE = re.compile(
    r"(?<![\d.])"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>MG|MCG|UG|G|ML|L|%|MBQ|GBQ|KBQ|UI|IU|MEQ|MMOL)"
    r"(?![A-Z])"
    r"(?:\s*/\s*(?P<denominator>ML|L|G|MG|DOSE|FLACON|COMPRIME|COMPRIMES))?",
    re.IGNORECASE,
)

_MASS_TO_MG = {"MG": 1.0, "G": 1000.0, "MCG": 0.001, "UG": 0.001}
_VOLUME_TO_ML = {"ML": 1.0, "L": 1000.0}
_RADIO_TO_MBQ = {"MBQ": 1.0, "GBQ": 1000.0, "KBQ": 0.001}
_OTHER_UNITS = {"%": "%", "UI": "UI", "IU": "UI", "MEQ": "MEQ", "MMOL": "MMOL"}
_DENOMINATOR_UNITS = {
    "ML": ("ML", 1.0),
    "L": ("ML", 1000.0),
    "G": ("MG", 1000.0),
    "MG": ("MG", 1.0),
    "DOSE": ("DOSE", 1.0),
    "FLACON": ("FLACON", 1.0),
    "COMPRIME": ("COMPRIME", 1.0),
    "COMPRIMES": ("COMPRIME", 1.0),
}


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""

    text = str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper().replace("\u00b5", "U").replace("\u03bc", "U")
    text = re.sub(r"[^A-Z0-9]+", " ", text)

    return re.sub(r"\s+", " ", text).strip()


def normalize_dosage_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).upper().replace("\u00b5", "U").replace("\u03bc", "U")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return re.sub(r"\s+", " ", text).strip()


def _format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _canonicalize_term(
    value: float, unit: str, denominator: str | None
) -> str | None:
    unit = unit.upper()
    factor = 1.0

    if unit in _MASS_TO_MG:
        canonical_unit = "MG"
        factor = _MASS_TO_MG[unit]
    elif unit in _VOLUME_TO_ML:
        canonical_unit = "ML"
        factor = _VOLUME_TO_ML[unit]
    elif unit in _RADIO_TO_MBQ:
        canonical_unit = "MBQ"
        factor = _RADIO_TO_MBQ[unit]
    elif unit in _OTHER_UNITS:
        canonical_unit = _OTHER_UNITS[unit]
    else:
        return None

    if denominator:
        denominator = denominator.upper()
        denominator_info = _DENOMINATOR_UNITS.get(denominator)
        if denominator_info is None:
            return None
        canonical_denominator, denominator_factor = denominator_info
        canonical_unit = f"{canonical_unit}/{canonical_denominator}"
        factor /= denominator_factor

    return f"{_format_number(value * factor)}{canonical_unit}"


def extract_dosage_terms(value: object) -> frozenset[str]:
    text = normalize_dosage_text(value)
    if not text:
        return frozenset()

    terms: set[str] = set()
    for match in _DOSAGE_RE.finditer(text):
        raw_value = match.group("value").replace(",", ".")
        try:
            number = float(raw_value)
        except ValueError:
            continue
        term = _canonicalize_term(
            number,
            match.group("unit"),
            match.group("denominator"),
        )
        if term:
            terms.add(term)

    return frozenset(terms)


def tokenize(value: object) -> tuple[str, ...]:
    normalized = normalize_text(value)
    return tuple(normalized.split()) if normalized else ()
