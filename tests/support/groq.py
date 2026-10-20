import json
from pharmacy_language.config import DEFAULT_MODEL

def extraction():
    return {'language': 'darija', 'reply_language': 'darija', 'reply_script': 'latin', 'intents': ['price', 'availability'], 'entities': {'medications': [{'name': 'ABIP', 'strength': '15mg', 'quantity': None, 'form': None, 'presentation': None}], 'pharmacy': None, 'city': None, 'area': None, 'date': None, 'time': None, 'symptom': None}}

def completion(data=None, finish='stop', **message_extra):
    return {'id': 'offline-completion', 'object': 'chat.completion', 'created': 1, 'model': DEFAULT_MODEL, 'choices': [{'index': 0, 'finish_reason': finish, 'message': {'role': 'assistant', 'content': json.dumps(data or extraction()), **message_extra}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150}}
