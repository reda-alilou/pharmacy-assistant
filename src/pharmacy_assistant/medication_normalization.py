"""Reviewed lexical equivalences; unknown qualifiers and units stay significant."""

import re
import unicodedata
from decimal import Decimal

from pharmacy_assistant.catalog import normalize


def arabic_normalize(value: str) -> str:
    value = normalize(unicodedata.normalize("NFKC", value))
    return value.translate(str.maketrans("أإآىؤئ", "ااايوي")).replace("ـ", "")


def digits(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return value.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789."))


# Arabic entries are reviewed identity aliases. Latin/Arabizi spelling variants
# are proposals requiring explicit record confirmation, never fuzzy auto-selection.
NAME_ALIASES = {
    "دوليبران": "DOLIPRANE", "دوليبْران": "DOLIPRANE",
    "باراسيتامول": "PARACETAMOL", "الباراسيتامول": "PARACETAMOL",
    "أبيب": "ABIP", "ابيب": "ABIP", "ايركورت": "AIRCORT", "إيركورت": "AIRCORT",
    "أموكسيسيلين": "AMOXICILLINE", "اموكسيسيلين": "AMOXICILLINE",
    "أموكسيسلين": "AMOXICILLINE", "اموكسيسلين": "AMOXICILLINE",
    # Brand identity only: strength/form/package still resolve independently.
    "فنتولين": "VENTOLINE", "فينتولين": "VENTOLINE",
    "ڤنتولين": "VENTOLINE", "ڤينتولين": "VENTOLINE",
    "أوغمنتين": "AUGMENTIN", "أوجمنتين": "AUGMENTIN",
}
CONFIRMATION_ALIASES = {
    "airkort": "AIRCORT", "amoksisilin": "AMOXICILLINE",
    "amoxiciline": "AMOXICILLINE", "paracetamoul": "PARACETAMOL",
}
_ALIASES = {arabic_normalize(k): v for k, v in NAME_ALIASES.items()}
_PROPOSALS = {arabic_normalize(k): v for k, v in CONFIRMATION_ALIASES.items()}


def lookup_name(value: str) -> str:
    return _ALIASES.get(arabic_normalize(value), _PROPOSALS.get(arabic_normalize(value), value))


def alias_requires_confirmation(value: str) -> bool:
    return arabic_normalize(value) in _PROPOSALS


UNIT_WORDS = {
    "ميكروغرام": "ug", "ميكروجرام": "ug", "mcg": "ug",
    "ميليغرام": "mg", "مليغرام": "mg", "ملغ": "mg", "مغ": "mg", "مجم": "mg",
    "غرام": "g", "جرام": "g", "غ": "g",
    "ميليلتر": "ml", "ملليلتر": "ml", "مل": "ml", "لتر": "l",
    "جرعة": "dose", "جرعات": "dose", "doses": "dose",
}


def decimal_key(value: Decimal) -> str:
    return format(value.normalize(), "f")


def unit_text(value: str) -> str:
    value = arabic_normalize(digits(value)).replace(",", ".").replace("μ", "u")
    for word, unit in sorted(UNIT_WORDS.items(), key=lambda item: -len(item[0])):
        value = re.sub(r"(?<![^\W\d_])" + re.escape(arabic_normalize(word)) + r"(?![^\W\d_])", unit, value)
    return value


def strength_key(value: str) -> str:
    text = re.sub(r"\s+", "", unit_text(value))
    number = r"\d+(?:\.\d+)?"
    mass = {"g": Decimal(1000), "mg": Decimal(1), "ug": Decimal("0.001")}
    single = re.fullmatch(f"({number})(ug|mg|g)", text)
    if single:
        return decimal_key(Decimal(single[1]) * mass[single[2]]) + "mg"
    ratio = re.fullmatch(f"({number})(ug|mg|g)/({number})?(ml|l|dose)", text)
    if ratio:
        denominator = Decimal(ratio[3] or "1") * (1000 if ratio[4] == "l" else 1)
        if denominator:
            return decimal_key(Decimal(ratio[1]) * mass[ratio[2]] / denominator) + "mg/" + ("dose" if ratio[4] == "dose" else "ml")
    # Mass/mass denotes ordered component strengths, not a concentration to
    # reduce: 1000mg/125mg must not equal 8mg/1mg.
    parts = re.split(r"([/+])", text)
    if len(parts) > 1 and all(re.fullmatch(f"({number})(ug|mg|g)", part) for part in parts[::2]):
        return "components:" + "".join(strength_key(part) if i % 2 == 0 else part for i, part in enumerate(parts))
    return text  # Includes unitless numbers: never infer a missing unit.


FORM_GROUPS = {
    "comprime": ("comprime", "comprimes", "cp", "cps", "cpr", "قرص", "أقراص", "الأقراص", "الاقراص", "l9ras"),
    "gelule": ("gelule", "gelules", "كبسولة", "كبسولات", "الكبسولات"),
    "sirop": ("sirop", "شراب", "الشراب"),
    "sachet": ("sachet", "sachets", "كيس", "أكياس", "الأكياس"),
    "suppositoire": ("suppositoire", "suppositoires", "تحميلة", "تحاميل"),
    "inhalation": ("inhalation", "استنشاق", "الاستنشاق", "للاستنشاق"),
    "injectable": ("injectable", "حقن", "للحقن"),
    "effervescent": ("effervescent", "effervescents", "فوار", "فوارة"),
    "pellicule": ("pellicule", "pellicules", "مغلف", "مغلفة"),
    "suspension": ("suspension", "معلق"),
    "solution": ("solution", "محلول"),
    "creme": ("creme", "كريم"), "pommade": ("pommade", "مرهم"),
}
_FORM_WORDS = sorted(((arabic_normalize(word), canonical) for canonical, words in FORM_GROUPS.items()
                      for word in words), key=lambda item: -len(item[0]))


def form_key(value: str) -> str:
    value = arabic_normalize(value)
    for word, canonical in _FORM_WORDS:
        value = re.sub(r"(?<!\w)" + re.escape(word) + r"(?!\w)", canonical, value)
    return " ".join(re.sub(r"(?<!\d)\.|\.(?!\d)|[^\w.]+", " ", value).split())


def form_matches(stored: str, requested: str) -> bool:
    connectors = {"l", "de", "d", "pour", "en", "a"}
    query = set(form_key(requested).split()) - connectors
    return bool(query) and query <= set(form_key(stored).split()) - connectors


PACK_WORDS = {
    "boite": ("boite", "boites", "box", "علبة", "علب", "العلبة", "العلب", "lboita", "boita", "l3elba"),
    "flacon": ("flacon", "flacons", "قارورة", "قنينة", "القارورة", "القنينة"),
    "ampoule": ("ampoule", "ampoules", "امبولة", "امبولات"),
    "poche": ("poche", "poches"), "tube": ("tube", "tubes", "انبوب"),
}
CONNECTORS = {"de", "du", "des", "d", "l", "of", "dyal", "ديال", "من", "فيها", "في", "un", "une"}


def package_key(value: str) -> list[str]:
    text = form_key(unit_text(value))
    for canonical, words in PACK_WORDS.items():
        for word in words:
            text = re.sub(r"(?<!\w)" + re.escape(arabic_normalize(word)) + r"(?!\w)", canonical, text)
    tokens = re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+", text)
    # Explicit package volumes are equivalent across ml/l. Counts and mass
    # units stay distinct; a count of 20 never matches 200 or a volume of 20 ml.
    result, i = [], 0
    while i < len(tokens):
        token = tokens[i]
        if re.fullmatch(r"\d+(?:\.\d+)?", token):
            amount = Decimal(token)
            if i + 1 < len(tokens) and tokens[i + 1] in {"ml", "l"}:
                result.extend([decimal_key(amount * (1000 if tokens[i + 1] == "l" else 1)), "ml"])
                i += 2
                continue
            token = decimal_key(amount)
        if token not in CONNECTORS:
            result.append(token)
        i += 1
    return result


def presentation_matches(stored: str, requested: str, stored_form: str = "") -> bool:
    source, query = package_key(stored), package_key(requested)
    if not query:
        return False
    numeric = lambda values: [v for v in values if re.fullmatch(r"\d+(?:\.\d+)?", v)]
    if numeric(query) and numeric(query) != numeric(source):
        return False
    return set(query) <= set(source + form_key(stored_form).split())
