"""Deterministic replies. All product and directory facts come from records."""

from pharmacy_assistant.chat_models import MedicationResult, OrderPricing, PharmacyResult
from pharmacy_assistant.nlu_models import Interpretation
from pharmacy_assistant.pricing import price_amount


# Keys share the same meaning in French, Modern Standard Arabic, and Darija
# in both scripts. Stored French product labels remain verbatim for traceability.
MESSAGES = {
    "choose": (
        "Précisez le médicament, le dosage ou la présentation parmi les choix proposés.",
        "يرجى تحديد الدواء أو التركيز أو العبوة من الخيارات المقترحة.",
        "Khtar smit ddwa, tarkiz wla l3elba men l'ikhtiyarat.",
        "ختار سميت الدوا، التركيز ولا العلبة من الاختيارات."),
    "suggest": (
        "Nom à confirmer : choisissez une proposition, aucune correspondance approximative n'a été sélectionnée.",
        "يرجى تأكيد الاسم باختيار اقتراح؛ لم يتم اختيار تطابق تقريبي تلقائياً.",
        "2akked smit ddwa b chi ikhtiyar; ta wa7ed ma tkhtar automatiquement.",
        "أكد سميت الدوا باختيار اقتراح؛ حتى واحد ما تختار بوحدو."),
    "missing_name": (
        "Quel médicament cherchez-vous ? Précisez son nom et, si possible, son dosage et sa présentation.",
        "ما اسم الدواء الذي تبحث عنه؟ حدد التركيز والعبوة إن أمكن.",
        "Achmen dwa kat9elleb 3lih? 3tini smiyto, tarkiz w l3elba ila 3reftihom.",
        "أشمن دوا كتقلب عليه؟ عطيني سميتو، التركيز والعلبة إلا عرفتيهم."),
    "truncated": (
        "Affinez la recherche ou consultez les présentations suivantes.",
        "حدد التفاصيل لتضييق البحث أو اعرض العبوات التالية.",
        "7dded lma3loumat bach t9ellel l'ikhtiyarat, wla chouf l3elbat lli men be3d.",
        "حدد المعلومات باش تقلل الاختيارات، ولا شوف العلب اللي من بعد."),
    "refine_strength": ("Quel dosage recherchez-vous ?", "ما التركيز الذي تبحث عنه؟", "Achmen tarkiz kat9elleb 3lih?", "أشمن تركيز كتقلب عليه؟"),
    "refine_form": ("Quelle forme recherchez-vous ?", "ما الشكل الدوائي الذي تبحث عنه؟", "Achmen chkel dyal ddwa bghiti?", "أشمن شكل ديال الدوا بغيتي؟"),
    "refine_brand_name": ("Quel nom commercial cherchez-vous ?", "ما الاسم التجاري الذي تبحث عنه؟", "Achmen smiya tijariya kat9elleb 3liha?", "أشمن سمية تجارية كتقلب عليها؟"),
    "refine_presentation": ("Quelle présentation recherchez-vous ?", "ما العبوة التي تبحث عنها؟", "Achmen 3elba bghiti?", "أشمن علبة بغيتي؟"),
    "recorded_options": ("Valeurs enregistrées", "القيم المسجلة", "L9iyam lmsjjlin", "القيم المسجلة"),
    "confirmed_correction": (
        "Vous avez confirmé une présentation différente des précisions initiales.",
        "لقد أكدت عبوة تختلف عن التفاصيل المذكورة في الطلب الأول.",
        "2akkedti wa7ed l3elba lli katkhtelef 3la lma3loumat louwlin.",
        "أكدتي واحد العلبة اللي كتختلف على المعلومات اللولين."),
    "not_found": (
        "Aucune correspondance dans ce catalogue partiel. Cela ne prouve pas que le médicament n'existe pas ou est indisponible.",
        "لم يتم العثور على تطابق في هذا الكتالوج الجزئي. هذا لا يثبت أن الدواء غير موجود أو غير متوفر.",
        "Ma l9itch tatabo9 f had catalogue nna9es. Hadchi ma kay3nich belli ddwa ma kaynch wla ma mtwfferch.",
        "ما لقيتش تطابق فهاد الكاتالوغ الناقص. هادشي ما كيعنيش بلي الدوا ما كاينش ولا ما متوفرش."),
    "filters": (
        "Nom trouvé, mais aucun enregistrement ne correspond au dosage, à la forme ou à la présentation demandés. Vérifiez ces précisions.",
        "تم العثور على الاسم، لكن التركيز أو الشكل أو العبوة المطلوبة لا تطابق السجلات. يرجى التحقق من هذه التفاصيل.",
        "Smiya kayna, walakin tarkiz, chkel wla l3elba ma ttab9ouch. 3awed t2akked men had lma3loumat.",
        "السميّة كاينة، ولكن التركيز، الشكل ولا العلبة ما تطابقوش. عاود تأكد من هاد المعلومات."),
    "price": ("Prix public enregistré", "الثمن العمومي المسجل", "Taman l3omomi lmsjjel", "الثمن العمومي المسجل"),
    "missing_price": ("Prix public non renseigné.", "الثمن العمومي غير مسجل.", "Taman l3omomi ma msjjelch.", "الثمن العمومي ما مسجلش."),
    "status": ("Statut de commercialisation enregistré", "حالة التسويق المسجلة", "Statut dyal commercialisation lmsjjel", "حالة التسويق المسجلة"),
    "substance": ("Substance active", "المادة الفعالة", "Lmada lfa33ala", "المادة الفعالة"),
    "stock": (
        "Le stock en pharmacie est inconnu. Le statut de commercialisation ne confirme pas une disponibilité locale.",
        "مخزون الصيدليات غير معروف. حالة التسويق لا تؤكد توفر الدواء في صيدلية معينة.",
        "Stock f ssaydaliya ma m3roufch. Statut dyal commercialisation ma kay2akkedch belli ddwa kayn f chi saydaliya.",
        "الستوك فالصيدلية ما معروفش. حالة التسويق ما كتأكدش بلي الدوا كاين فشي صيدلية."),
    "conflict": (
        "Des sources divergent sur certaines valeurs ; les valeurs AMMPS sont conservées et les différences figurent dans les détails.",
        "توجد اختلافات بين المصادر؛ تم الاحتفاظ بقيم AMMPS وتظهر الاختلافات في التفاصيل.",
        "Kayn ikhtilaf bin lmasadir; 7tafddna b valeurs AMMPS, lforou9 kaynin f details.",
        "كاين اختلاف بين المصادر؛ احتافظنا بقيم AMMPS، والفروق كاينة فالتفاصيل."),
    "quantity_total": (
        "Total calculé pour {count} présentation(s) complète(s) : {count} × {unit} MAD = {total} MAD.",
        "المجموع المحسوب لـ {count} عبوة كاملة: {count} × {unit} MAD = {total} MAD.",
        "Lmajmou3 lme7soub dyal {count} présentation kamla: {count} × {unit} MAD = {total} MAD.",
        "المجموع المحسوب ديال {count} عبوة كاملة: {count} × {unit} MAD = {total} MAD."),
    "quantity_clarify": (
        "Combien de présentations complètes souhaitez-vous ? Précisez un nombre entier de boîtes/présentations entre 1 et 1000 ; aucun total n'a été calculé pour cette quantité.",
        "كم عبوة كاملة تريد؟ حدد عدداً صحيحاً من العبوات بين 1 و1000؛ لم يتم حساب المجموع لهذه الكمية.",
        "Ch7al men présentation kamla bghiti? 3ti 3adad s7i7 dyal l3lab bin 1 w 1000; ma 7sebna ta total lhad quantité.",
        "شحال من عبوة كاملة بغيتي؟ عطينا عدد صحيح ديال العلب بين 1 و1000؛ ما حسبنا حتى مجموع لهاد الكمية."),
    "quantity_pending": (
        "Le total attend la confirmation du médicament et de sa présentation.",
        "حساب المجموع ينتظر تأكيد الدواء والعبوة.",
        "Ltotal kaytsenna t2kid dyal ddwa w présentation.",
        "المجموع كيتسنى تأكيد الدوا والعبوة."),
    "quantity_no_price": (
        "Total non calculable : le prix public de cette présentation n'est pas renseigné.",
        "لا يمكن حساب المجموع: الثمن العمومي لهذه العبوة غير مسجل.",
        "Ma n9drouch n7esbou ltotal: taman l3omomi dyal had présentation ma msjjelch.",
        "ما نقدروش نحسبو المجموع: الثمن العمومي ديال هاد العبوة ما مسجلش."),
    "order_total": ("Total calculé de toutes les lignes : {total} MAD.", "المجموع المحسوب لجميع الأصناف: {total} MAD.",
        "Lmajmou3 lme7soub dyal ga3 les lignes: {total} MAD.", "المجموع المحسوب ديال جميع الأصناف: {total} MAD."),
    "order_incomplete": (
        "Total global non calculé : chaque ligne doit avoir une quantité explicite, une présentation confirmée et un prix renseigné.",
        "لم يتم حساب المجموع الإجمالي: يجب تحديد الكمية والعبوة والثمن لكل صنف.",
        "Ltotal global ma t7sebch: khas quantité, présentation m2akkda w taman lkol dwa.",
        "المجموع الكامل ما تحسبش: خاص كمية وعبوة مؤكدة وثمن لكل دوا."),
    "directory": (
        "Résultats de l'annuaire partiel de Rabat, triés par nom ; la proximité n'est pas calculée. Coordonnées enregistrées à vérifier par téléphone.",
        "نتائج من دليل جزئي للرباط مرتبة حسب الاسم؛ لم يتم حساب القرب. يرجى تأكيد البيانات المسجلة هاتفياً.",
        "Hadi nata2ij men annuaire nna9es dyal Rabat, mrattbin b smiya, machi b l9orb. 2akked lma3loumat b telephone.",
        "هادي نتائج من دليل ناقص ديال الرباط، مرتبين بالسمية، ماشي بالقرب. أكد المعلومات بالتلفون."),
    "default_city": (
        "Aucune ville précisée : Rabat est utilisée pour cette démo.",
        "لم تحدد المدينة؛ تم استخدام الرباط لهذه النسخة التجريبية.",
        "Ma 7ddedtich lmdina; sta3mlna Rabat f had demo.",
        "ما حددتيش المدينة؛ استعملنا الرباط فهاد الديمو."),
    "outside": (
        "Cette démo dispose uniquement d'un annuaire partiel de Rabat pour les pharmacies.",
        "تتوفر هذه النسخة التجريبية على دليل جزئي لصيدليات الرباط فقط.",
        "Had demo 3ndha ghir annuaire nna9es dyal ssaydaliyat f Rabat.",
        "هاد الديمو عندها غير دليل ناقص ديال الصيدليات فالرباط."),
    "no_pharmacy": (
        "Aucune pharmacie correspondante dans l'annuaire partiel de Rabat. Cela ne signifie pas qu'il n'y en a aucune.",
        "لا توجد صيدلية مطابقة في دليل الرباط الجزئي. هذا لا يعني عدم وجودها.",
        "Ma l9itch saydaliya katttabe9 f annuaire nna9es dyal Rabat. Hadchi ma kay3nich belli ma kaynach.",
        "ما لقيتش صيدلية كتطابق فدليل الرباط الناقص. هادشي ما كيعنيش بلي ما كايناش."),
    "pharmacy_ambiguous": (
        "Plusieurs pharmacies correspondent à ce nom dans l'annuaire partiel. Précisez le nom complet ou le quartier ; aucune pharmacie unique n'a été choisie.",
        "يطابق هذا الاسم عدة صيدليات في الدليل الجزئي. حدد الاسم الكامل أو الحي؛ لم يتم اختيار صيدلية واحدة.",
        "Kaynin ktr men saydaliya b had smiya f l'annuaire nna9es. 3ti smiya kamla wla l7ay; ma khtarnach wa7da bo7dha.",
        "كاينين كثر من صيدلية بهاد السمية فالدليل الناقص. عطينا السمية كاملة ولا الحي؛ ما ختارنا حتى وحدة بوحدها."),
    "hours": (
        "Horaires d'ouverture non vérifiés ; contactez la pharmacie pour confirmation.",
        "ساعات العمل غير مؤكدة؛ اتصل بالصيدلية للتحقق.",
        "Sway3 l7ellan ma m2akkdinch; 3eyyet lssaydaliya bach t2akked.",
        "سوايع الحلان ما مؤكدينش؛ عيط للصيدلية باش تأكد."),
    "duty": (
        "Aucune garde datée et vérifiée n'est disponible. Ces résultats ne désignent pas des pharmacies de garde.",
        "لا تتوفر بيانات حراسة مؤرخة ومؤكدة. هذه النتائج لا تحدد صيدليات الحراسة.",
        "Ma 3ndnach garde b tarikh m2akked. Had nata2ij ma kay7eddouch ssaydaliyat de garde.",
        "ما عندناش حراسة بتاريخ مؤكد. هاد النتائج ما كيحددوش صيدليات الحراسة."),
    "unsupported": (
        "Je peux consulter les médicaments et l'annuaire disponible. Je ne fournis ni diagnostic ni recommandation de traitement ; demandez conseil à un pharmacien ou un médecin.",
        "يمكنني البحث في بيانات الأدوية ودليل الصيدليات المتاح. لا أقدم تشخيصاً أو توصيات علاجية؛ استشر صيدلياً أو طبيباً.",
        "N9der n9elleb f ma3loumat ddwa w annuaire. Ma kan3tich tachkhis wla traitement; swel pharmacien wla tbib.",
        "نقدر نقلب فمعلومات الدوا والدليل. ما كنعطيش تشخيص ولا علاج؛ سول صيدلي ولا طبيب."),
    "unknown": ("non renseigné", "غير مسجل", "ma msjjelch", "ما مسجلش"),
}

MEDICATION_INTENTS = {"price", "availability", "medication_information", "medication_request"}
PHARMACY_INTENTS = {"pharmacy_search", "pharmacy_contact", "opening_hours", "pharmacy_on_duty"}


def render_answer(interpretation: Interpretation, results: list[MedicationResult], pharmacy: PharmacyResult | None,
                  *, needs_reference=False, order_pricing: OrderPricing | None = None) -> str:
    column = 0 if interpretation.reply_language == "fr" else 1 if interpretation.reply_language == "ar" else 3 if interpretation.reply_script == "arabic" else 2
    def msg(key):
        return MESSAGES[key][column]
    def value(text):
        return msg("unknown") if text.strip().casefold() in {"-", "na", "n/a", "non renseigne", "non renseigné"} else text
    paragraphs = []
    if needs_reference:
        paragraphs.append(("De quel médicament ou de quelle présentation parlez-vous ? Précisez le nom ou utilisez les choix proposés.",
            "أي دواء أو عبوة تقصد؟ وضّح الاسم أو استخدم الخيارات المعروضة.",
            "Achmen dwa wla 3elba kat9sed? 3ti smiya wla khtar men les choix.",
            "أشمن دوا ولا علبة كتقصد؟ عطينا السمية ولا اختار من الاختيارات.")[column])
    intents = set(interpretation.intents)
    for result in results:
        name = result.mention.name or "?"
        if result.status != "resolved":
            key = {"ambiguous": "choose", "suggestions": "suggest", "not_found": "not_found",
                   "missing_name": "missing_name", "filters_not_matched": "filters"}[result.status]
            question = result.clarification
            if question and question.field:
                prefix = msg(key) + " " if result.status in {"filters_not_matched", "suggestions"} else ""
                paragraphs.append(f"{name}: {prefix}{msg('refine_' + question.field)}")
                values = "; ".join(option.value for option in question.options[:8])
                if len(question.options) > 8:
                    values += "; …"
                paragraphs.append(f"{msg('recorded_options')}: {values}")
            else:
                paragraphs.append(f"{name}: {msg(key)}")
            if result.candidates_truncated:
                paragraphs.append(msg("truncated"))
            continue
        record = result.medication
        lines = [f"{record.brand_name} — {value(record.dosage)} — {value(record.form)} — {value(record.presentation)}"]
        if result.conflicting_filters:
            lines.append(msg("confirmed_correction"))
        lines.append(msg("missing_price") if record.ppv_price_mad is None else f"{msg('price')}: {price_amount(record.ppv_price_mad):.2f} MAD.")
        if result.pricing and result.pricing.status == "calculated":
            pricing = result.pricing
            lines.append(msg("quantity_total").format(count=pricing.presentation_count,
                         unit=pricing.unit_price_mad, total=pricing.total_price_mad))
        lines.append(f"{msg('status')}: {value(record.commercialization_status)}.")
        if "medication_information" in intents:
            lines.append(f"{msg('substance')}: {value(record.active_substance)}.")
        if record.data_conflicts:
            lines.append(msg("conflict"))
        paragraphs.append("\n".join(lines))
    if not results and intents & MEDICATION_INTENTS and not needs_reference:
        paragraphs.append(msg("missing_name"))
    for result in results:
        if result.pricing:
            key = {"needs_quantity_clarification": "quantity_clarify", "awaiting_medication": "quantity_pending",
                   "price_unavailable": "quantity_no_price"}.get(result.pricing.status)
            if key:
                paragraphs.append(f"{result.mention.name or '?'}: {msg(key)}")
    if len(results) > 1 and order_pricing:
        if order_pricing.status == "calculated":
            paragraphs.append(msg("order_total").format(total=order_pricing.total_price_mad))
        elif order_pricing.status == "incomplete":
            paragraphs.append(msg("order_incomplete"))
    if intents & {"availability", "medication_request"}:
        paragraphs.append(msg("stock"))
    if pharmacy is not None:
        if pharmacy.city_defaulted:
            paragraphs.append(msg("default_city"))
        paragraphs.append(msg("outside") if pharmacy.status == "outside_coverage" else msg("no_pharmacy") if pharmacy.status == "not_found" else msg("directory"))
        if pharmacy.status == "ambiguous":
            paragraphs.append(msg("pharmacy_ambiguous"))
        for record in pharmacy.pharmacies:
            paragraphs.append(f"{record.name} — {record.phone or msg('unknown')} — {record.address or msg('unknown')}")
        if "opening_hours" in intents:
            paragraphs.append(msg("hours"))
        if "pharmacy_on_duty" in intents:
            paragraphs.append(msg("duty"))
    if "unsupported" in intents:
        paragraphs.append(msg("unsupported"))
    return "\n\n".join(paragraphs)
