"""Run with: python -m streamlit run src/pharmacy_assistant/demo.py"""

from dataclasses import asdict
from html import escape
import time
import uuid
from urllib.parse import urlsplit

import streamlit as st

from pharmacy_assistant.chat_models import ChatResponse
from pharmacy_assistant.demo_client import DemoClient, DemoError
from pharmacy_assistant.pricing import price_amount


EXAMPLES = [
    ("Français", "Quel est le prix de AIRCORT ?"),
    ("العربية", "ما ثمن AIRCORT؟"),
    ("Darija", "Wach kayn AIRCORT w bch7al?"),
    ("Mixte", "Bghit deux boîtes de ABIP 15mg, boîte de 20, شحال الثمن؟"),
    ("Choix ABIP", "Quel est le prix de ABIP ?"),
]


def prose(text: str, direction="auto"):
    st.markdown(f'<div class="pharmacy-prose" dir="{direction}">{escape(text)}</div>', unsafe_allow_html=True)


def queue_new(text: str):
    payload = {"text": text}
    # The rendered history is authoritative. A separately cached token can lag
    # behind a completed turn across Streamlit reruns and reopen an older branch.
    latest = next((turn["response"] for turn in reversed(st.session_state.get("turns", []))
                   if turn.get("response")), None)
    if latest and latest.get("session_id"):
        payload["session_id"] = latest["session_id"]
    st.session_state.pending_action = {"kind": "new", "text": text, "payload": payload}


def queue_restart(text: str):
    st.session_state.session_id = None
    st.session_state.pending_action = {"kind": "new", "text": text, "payload": {"text": text}}


def queue_reference(turn_id, index, name):
    parent = next(t for t in st.session_state.turns if t["id"] == turn_id)
    st.session_state.pending_action = {
        "kind": "reference", "text": f"Contexte : {name}", "original_text": parent["original_text"],
        "payload": {"session_id": parent["response"]["session_id"], "reference_index": index},
    }


def queue_selection(turn_id, index, record):
    parent = next(t for t in st.session_state.turns if t["id"] == turn_id)
    st.session_state.pending_action = {
        "kind": "selection", "text": f"Choix : {record['brand_name']} · {record['dosage']} · {record['presentation']}",
        "original_text": parent["original_text"],
        "payload": {"continuation_id": parent["response"]["continuation_id"],
                    "selections": [{"mention_index": index, "record_id": record["source_record_id"]}]},
    }


def queue_retry(turn_id):
    turn = next(t for t in st.session_state.turns if t["id"] == turn_id)
    remaining = turn.get("retry_at", 0) - time.time()
    if remaining > 0:
        st.session_state.notice = f"Veuillez attendre encore {int(remaining) + 1} seconde(s)."
    else:
        st.session_state.pending_action = {"kind": "retry", "turn_id": turn_id}


def queue_refinement(turn_id, index, field, value):
    parent = next(t for t in st.session_state.turns if t["id"] == turn_id)
    st.session_state.pending_action = {
        "kind": "refinement", "text": f"Précision : {value}", "original_text": parent["original_text"],
        "payload": {"continuation_id": parent["response"]["continuation_id"],
                    "refinements": [{"mention_index": index, "field": field, "value": value}]},
    }


def clear_history():
    st.session_state.turns = []
    st.session_state.pending_action = None
    st.session_state.pop("notice", None)
    st.session_state.session_id = None


def price(record):
    amount = record.ppv_price_mad
    return "Prix non renseigné" if amount is None else f"{price_amount(amount):.2f} MAD"


def source_link(label, url):
    parsed = urlsplit(url)
    if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username:
        st.link_button(label, url)


def render_response(body: ChatResponse, turn: dict, active: bool):
    prose(body.answer, "rtl" if body.interpretation.reply_script == "arabic" else "ltr")
    if body.context and body.context.needs_reference:
        for option in body.context.reference_options:
            medication = option.medication
            label = " · ".join(v for v in (medication.name, medication.strength, medication.presentation) if v)
            st.button(f"Parler de : {label}", key=f"reference_{turn['id']}_{option.mention_index}",
                on_click=queue_reference, args=(turn["id"], option.mention_index, label), disabled=not active)
    for result in body.medications:
        if result.medication:
            record = result.medication
            with st.container(border=True):
                prose(f"{record.brand_name} · {record.dosage}")
                left, right = st.columns([3, 1])
                with left:
                    st.write(record.presentation)
                    st.caption(record.form)
                    st.caption(f"Commercialisation enregistrée : {record.commercialization_status}")
                with right:
                    st.metric("Prix public enregistré", price(record))
                    if result.pricing and result.pricing.status == "calculated":
                        st.metric(f"Total · {result.pricing.presentation_count} présentation(s)", f"{result.pricing.total_price_mad} MAD")
                st.caption("Stock en pharmacie : inconnu")
                if record.data_conflicts:
                    st.warning("Des sources divergent. Les valeurs AMMPS sont conservées.")
                    with st.expander("Différences entre les sources"):
                        st.json([c.model_dump() for c in record.data_conflicts])
        question = result.clarification
        if question and question.field and question.options:
            labels = {"strength": "Dosage", "form": "Forme", "brand_name": "Nom commercial", "presentation": "Présentation"}
            counts = {option.value: option.candidate_count for option in question.options}
            selected = st.selectbox(labels[question.field], options=list(counts), index=None,
                format_func=lambda v, option_counts=counts: f"{v} · {option_counts[v]} présentation(s)",
                key=f"refine_{turn['id']}_{result.mention_index}", disabled=not active,
                placeholder="Choisir une valeur enregistrée")
            st.button("Affiner", key=f"apply_refine_{turn['id']}_{result.mention_index}",
                      on_click=queue_refinement, args=(turn["id"], result.mention_index, question.field, selected),
                      disabled=not active or selected is None)
        if result.candidates and not (question and question.field and result.candidate_count > 5):
            st.markdown("**Choisir une présentation**")
            if not active:
                st.caption("Ces choix appartiennent à une demande précédente. Relancez la question pour de nouveaux choix.")
            for record in result.candidates:
                label = f"{record.brand_name} · {record.dosage} · {record.presentation} — {price(record)}"
                st.button(label, key=f"choice_{turn['id']}_{result.mention_index}_{record.source_record_id}",
                          on_click=queue_selection, args=(turn["id"], result.mention_index, record.model_dump()),
                          disabled=not active, width="stretch")
            if body.continuation_expires_at_utc:
                st.caption("Ces choix expirent après 15 minutes ou au redémarrage de l'API.")
            if result.next_candidate_offset is not None:
                st.button("Présentations suivantes", key=f"more_{turn['id']}_{result.mention_index}",
                          on_click=queue_refinement,
                          args=(turn["id"], result.mention_index, "page", str(result.next_candidate_offset)), disabled=not active)
    if len(body.medications) > 1 and body.order_pricing.status == "calculated":
        st.metric("Total de toutes les lignes", f"{body.order_pricing.total_price_mad} MAD")
    if body.pharmacy and body.pharmacy.pharmacies:
        if body.pharmacy.status == "ambiguous":
            st.info("Plusieurs pharmacies correspondent : précisez le nom complet ou le quartier.")
        with st.expander(f"Coordonnées des pharmacies · {body.pharmacy.result_count} correspondance(s)"):
            if body.pharmacy.results_truncated:
                st.caption(f"{len(body.pharmacy.pharmacies)} sur {body.pharmacy.result_count} correspondances affichées. Précisez le nom ou le quartier pour affiner.")
            for record in body.pharmacy.pharmacies:
                with st.container(border=True):
                    st.write(record.name)
                    st.write(record.phone or "Téléphone non renseigné")
                    st.write(record.address or "Adresse non renseignée")
                    st.caption(f"Rabat · {record.latitude}, {record.longitude}")
            st.caption("Annuaire partiel · Horaires inconnus · Garde non vérifiée · Classement par nom")
    with st.expander("Extraction JSON"):
        st.json(body.interpretation.model_dump())
        if body.context and (body.context.inherited_fields or body.context.needs_reference):
            st.caption("Contexte utilisé séparément de l'extraction du message actuel")
            st.json(body.context.model_dump())
        if any(r.pricing and r.pricing.status != "not_requested" for r in body.medications):
            st.caption("Calcul local à partir des prix enregistrés")
            st.json({"medications": [{"mention_index": r.mention_index, "pricing": r.pricing.model_dump()}
                                      for r in body.medications if r.pricing], "order_pricing": body.order_pricing.model_dump()})
    with st.expander(f"Sources et détails · {len(body.sources)} référence(s)"):
        if not body.sources:
            st.caption("Aucune donnée de catalogue utilisée pour cette réponse.")
        for source in body.sources:
            source_link(source.source, source.url)
            st.caption(f"Collecté : {source.fetched_at_utc or 'date inconnue'} · Enregistrements : {', '.join(source.record_ids)}")
        st.caption(f"Fournisseur : {body.inference.provider} · Modèle : {body.inference.model}")
        st.caption(f"Format demandé : {body.inference.output_mode} · Prompt : {body.inference.prompt_version}")
        if body.inference_performed:
            st.caption(f"Interprétation : {body.inference.latency_ms:.0f} ms · Tentatives : {body.inference.attempts} · Tokens : {body.inference.usage.total_tokens}")
        else:
            st.caption("Choix traité sans nouvel appel au modèle. Métadonnées conservées de la question initiale.")


def main():
    st.set_page_config(page_title="Pharma | Assistant multilingue", page_icon="💊", layout="wide")
    st.markdown("""<style>
      .block-container {max-width: 1060px; padding-top: 2.4rem; padding-bottom: 5rem;}
      .pharmacy-prose {white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.75; font-size: 1.03rem;}
      [data-testid="stChatInputTextArea"] {unicode-bidi: plaintext;}
      [data-testid="stMetricValue"] {font-size: 1.35rem;}
      [data-testid="stChatMessage"] {border-radius: 14px;}
    </style>""", unsafe_allow_html=True)
    for key, default in (("turns", []), ("pending_action", None), ("session_id", None)):
        if key not in st.session_state:
            st.session_state[key] = default
    try:
        client = DemoClient()
    except ValueError:
        st.error("PHARMACY_API_URL est invalide. Utilisez une URL comme http://127.0.0.1:8000.")
        st.stop()
    busy = st.session_state.pending_action is not None
    with st.sidebar:
        st.title("💊 Pharma")
        st.caption("Assistant patient–pharmacie · Maroc")
        refresh = st.button("Actualiser la connexion", disabled=busy)
        if "health" not in st.session_state or refresh:
            try:
                st.session_state.health = client.health().model_dump()
                st.session_state.health_error = None
            except DemoError as error:
                st.session_state.health = None
                st.session_state.health_error = error.message
        if st.session_state.health:
            health = st.session_state.health
            st.success("API connectée")
            st.metric("Présentations enregistrées", f"{health['catalog_record_count']:,}".replace(",", " "))
            if not health["interpretation_configured"]:
                st.warning("Clé du modèle non configurée sur le serveur.")
            if health.get("interpretation_provider"):
                st.caption(f"Modèle : {health['interpretation_provider']} / {health['interpretation_model']}")
            st.caption("AMMPS · Medicament.ma · Saydalia")
            st.caption("Pharmacies : annuaire partiel de Rabat")
        else:
            st.error(st.session_state.health_error)
            st.button("Reconnexion", on_click=lambda: st.session_state.pop("health", None), disabled=busy)
        st.divider()
        st.write("Prix enregistrés et informations issues des sources collectées.")
        st.caption("Stock inconnu. Horaires et gardes non vérifiés.")
        st.button("Nouvelle conversation", on_click=clear_history, disabled=busy, width="stretch")
        st.caption("Les précisions précédentes restent disponibles pendant 15 minutes. Nouvelle conversation efface le contexte.")
    st.title("Votre question, votre langue.")
    st.write("Prix, médicaments et pharmacies — en français, العربية ou darija.")
    st.caption("Démonstration avec données collectées · Réponses en direct")
    columns = st.columns(len(EXAMPLES))
    for column, (label, text) in zip(columns, EXAMPLES):
        with column:
            st.button(label, on_click=queue_new, args=(text,), disabled=busy, width="stretch")
    if "notice" in st.session_state:
        st.info(st.session_state.pop("notice"))
    prompt = st.chat_input("Écrivez votre question… / كتب سؤالك", max_chars=2000, disabled=busy, key="question")
    if prompt:
        queue_new(prompt)
        st.rerun()
    action = st.session_state.pop("pending_action", None)
    working_turn = None
    if action:
        if action["kind"] == "retry":
            working_turn = next(t for t in st.session_state.turns if t["id"] == action["turn_id"])
            working_turn["error"] = None
        else:
            working_turn = {"id": uuid.uuid4().hex, "text": action["text"],
                            "original_text": action.get("original_text", action["text"]),
                            "payload": action.get("payload", {"text": action["text"]}),
                            "response": None, "error": None}
            st.session_state.turns.append(working_turn)
            st.session_state.turns = st.session_state.turns[-20:]
    if not st.session_state.turns:
        st.info("Essayez une question ci-dessus, ou saisissez la vôtre. Les présentations ambiguës vous seront proposées au choix.")
    for turn in st.session_state.turns:
        with st.chat_message("user"):
            prose(turn["text"])
        with st.chat_message("assistant"):
            if turn["response"]:
                render_response(ChatResponse.model_validate(turn["response"]), turn,
                                turn is st.session_state.turns[-1] and working_turn is None)
            elif turn["error"]:
                error = DemoError(**turn["error"])
                st.error(error.message)
                st.caption(f"Erreur : {error.code}" + (f" · HTTP {error.status}" if error.status else ""))
                if error.retry_after_seconds:
                    st.caption(f"Délai demandé par le serveur : {error.retry_after_seconds:g} s.")
                if turn is st.session_state.turns[-1] and working_turn is None:
                    if error.code in {"clarification_expired", "invalid_selection"}:
                        st.button("Relancer la question initiale", on_click=queue_restart, args=(turn["original_text"],))
                    elif error.code == "session_expired":
                        st.button("Nouvelle conversation", on_click=clear_history, key="reset_expired_session")
                    elif error.retryable:
                        st.button("Réessayer", on_click=queue_retry, args=(turn["id"],), key=f"retry_{turn['id']}")
    if working_turn is not None:
        with st.spinner("Interprétation et recherche en cours…", show_time=True):
            try:
                working_turn["response"] = client.chat(working_turn["payload"]).model_dump(mode="json")
                st.session_state.session_id = working_turn["response"].get("session_id")
            except DemoError as error:
                working_turn["error"] = asdict(error)
                working_turn["retry_at"] = time.time() + (error.retry_after_seconds or 0)
        st.rerun()


if __name__ == "__main__":
    main()
