import json
from tests.support.groq import extraction
TEXT = 'Wach kayn ABIP 15mg w bch7al?'

def completion(data=None):
    return {'candidates': [{'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [{'text': json.dumps(data or extraction())}]}}], 'modelVersion': 'gemini-3.8-flash-test-version', 'responseId': 'offline-gemini', 'usageMetadata': {'promptTokenCount': 100, 'candidatesTokenCount': 50, 'thoughtsTokenCount': 20, 'totalTokenCount': 170}}
