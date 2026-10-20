"""Reviewed package-count grammar and Decimal arithmetic over retrieved prices.

No dose/unit conversion, implicit purchase quantity or model arithmetic is used.
Generic boxes/packages mean complete selected catalogue presentations. Specific
containers are accepted only when the presentation itself is that container.
"""

from decimal import Decimal, ROUND_HALF_UP
import re

from pharmacy_assistant.core.chat_models import MedicationPricing, OrderPricing
from pharmacy_assistant.core.medication_normalization import arabic_normalize, digits


MAX_PRESENTATIONS = 1000
CENT = Decimal("0.01")


def lexical(value):
    return arabic_normalize(value).replace("’", "'")


NUMBER_WORDS = {
    1: ("un", "une", "واحد", "واحدة", "واحده", "wa7ed", "wa7d", "wahed", "wahd"),
    2: ("deux", "اثنان", "اثنين", "اثنتان", "اثنتين", "جوج", "jouj", "jooj", "joj"),
    3: ("trois", "ثلاث", "ثلاثة", "تلاتة", "tlata", "tleta"),
    4: ("quatre", "أربع", "أربعة", "ربعة", "rb3a", "reb3a"),
    5: ("cinq", "خمس", "خمسة", "khmsa", "khamsa"),
    6: ("six", "ست", "ستة", "stta", "setta"),
    7: ("sept", "سبع", "سبعة", "sb3a"),
    8: ("huit", "ثمان", "ثماني", "ثمانية", "تمنية", "tmnya"),
    9: ("neuf", "تسع", "تسعة", "تسعود", "ts3od"),
    10: ("dix", "عشر", "عشرة", "3chra", "3achra"),
    11: ("onze",), 12: ("douze",), 13: ("treize",), 14: ("quatorze",),
    15: ("quinze",), 16: ("seize",), 17: ("dix-sept", "dix sept"),
    18: ("dix-huit", "dix huit"), 19: ("dix-neuf", "dix neuf"), 20: ("vingt",),
    30: ("trente",), 40: ("quarante",), 50: ("cinquante",),
    60: ("soixante",), 100: ("cent",),
}
NUMBERS = {lexical(word): number for number, words in NUMBER_WORDS.items() for word in words}
UNITS = {
    "package": ("boite", "boites", "box", "boxes", "pack", "packs", "paquet", "paquets",
        "presentation", "presentations", "علبة", "علب", "العلبة", "العلب", "عبوة", "عبوات",
        "lboita", "boita", "boitat", "l3elba", "3elba", "l3lab", "3lab"),
    "flacon": ("flacon", "flacons", "قارورة", "قوارير", "قنينة", "قنينات"),
    "tube": ("tube", "tubes", "أنبوب", "أنابيب"),
}
UNIT_MAP = {lexical(word): unit for unit, words in UNITS.items() for word in words}
DUALS = {lexical(word): unit for unit, words in {
    "package": ("علبتين", "علبتان", "عبوتين", "عبوتان"),
    "flacon": ("قارورتين", "قارورتان", "قنينتين", "قنينتان"),
    "tube": ("أنبوبين", "أنبوبان"),
}.items() for word in words}
SINGULARS = {lexical(word): unit for unit, words in {
    # Explicit Arabic indefinite singulars in the quantity slot mean one.
    # Missing quantities and definite references such as "lboita" stay unknown.
    "package": ("علبة", "عبوة", "علبة واحدة", "عبوة واحدة"),
    "flacon": ("قارورة", "قنينة", "قارورة واحدة", "قنينة واحدة"),
    "tube": ("أنبوب", "أنبوب واحد"),
}.items() for word in words}


def price_amount(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_quantity(value):
    """Return (positive presentation count, unit) or None for unclear quantities."""
    if value is None:
        return None
    text = lexical(value).strip()
    if text in DUALS:
        return 2, DUALS[text]
    if text in SINGULARS:
        return 1, SINGULARS[text]
    # Numeric counts can use any Unicode decimal digits; Arabizi words retain
    # their digits as letters, so '3lab' alone is never interpreted as count 3.
    for unit_word in sorted(UNIT_MAP, key=len, reverse=True):
        match = re.fullmatch(r"(.+?)\s*" + re.escape(unit_word), text)
        if not match:
            continue
        count_text = match[1].strip()
        count_text = re.sub(r"\s+(?:dyal|ديال)$", "", count_text)
        if count_text in NUMBERS:
            return NUMBERS[count_text], UNIT_MAP[unit_word]
        numeric = digits(count_text)
        if re.fullmatch(r"[0-9]+", numeric):
            count = int(numeric)
            if 1 <= count <= MAX_PRESENTATIONS:
                return count, UNIT_MAP[unit_word]
    return None


def container_matches(record, unit):
    if unit == "package":
        return True
    # A box containing N flacons is not priced per flacon. Require the source
    # presentation to start with the requested container, without a leading count.
    text = lexical(record.presentation)
    return re.match(r"^" + re.escape(unit) + r"\b", text) is not None


def apply_pricing(results):
    """Attach line arithmetic; publish an order total only when every line is clear."""
    for result in results:
        raw = result.mention.quantity
        if raw is None:
            result.pricing = MedicationPricing(status="not_requested")
            continue
        parsed = parse_quantity(raw)
        if parsed is None:
            result.pricing = MedicationPricing(status="needs_quantity_clarification", requested_quantity=raw,
                                                clarification_reason="unclear_package_count")
            continue
        count, unit = parsed
        if result.medication is None:
            result.pricing = MedicationPricing(status="awaiting_medication", requested_quantity=raw, presentation_count=count)
            continue
        record = result.medication
        if not container_matches(record, unit):
            result.pricing = MedicationPricing(status="needs_quantity_clarification", requested_quantity=raw,
                                                clarification_reason="container_mismatch")
            continue
        if record.ppv_price_mad is None:
            result.pricing = MedicationPricing(status="price_unavailable", requested_quantity=raw, presentation_count=count)
            continue
        unit_price = price_amount(record.ppv_price_mad)
        total = (unit_price * count).quantize(CENT, rounding=ROUND_HALF_UP)
        result.pricing = MedicationPricing(status="calculated", requested_quantity=raw, presentation_count=count,
                                          unit_price_mad=format(unit_price, ".2f"), total_price_mad=format(total, ".2f"))
    if not any(r.mention.quantity is not None for r in results):
        return OrderPricing()
    if all(r.pricing.status == "calculated" for r in results):
        total = sum((Decimal(r.pricing.total_price_mad) for r in results), Decimal(0))
        return OrderPricing(status="calculated", total_price_mad=format(total, ".2f"))
    return OrderPricing(status="incomplete")
