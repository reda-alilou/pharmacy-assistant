from pharmacy_contracts.interpretation import InterpretationResponse, MedicationMention

def mention(name='ABIP', **kwargs):
    return MedicationMention(name=name, strength=kwargs.get('strength'), quantity=kwargs.get('quantity'), form=kwargs.get('form'), presentation=kwargs.get('presentation'))

def response(medications=None, intents=None, language='fr', script='latin', **context):
    return InterpretationResponse.model_validate({'interpretation': {'language': language, 'reply_language': language, 'reply_script': script, 'intents': intents or ['price'], 'entities': {'medications': [m.model_dump() for m in (medications if medications is not None else [mention()])], **{key: context.get(key) for key in ('pharmacy', 'city', 'area', 'date', 'time', 'symptom')}}}, 'metadata': {'requested_model': 'offline', 'model': 'offline', 'prompt_version': 'test', 'latency_ms': 1, 'attempts': 1, 'completion_id': None, 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}})
