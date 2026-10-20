import unittest
from tests.support.services import connected_apps
from pharmacy_language.config import DEFAULT_OPENCODE_MODEL
from tests.support.configuration import FixtureSettings as Settings
TEXT = 'Wach kayn ABIP 15mg w bch7al?'

class OpenCodeConfigTests(unittest.TestCase):

    def test_health_and_missing_glm_key_never_use_the_existing_groq_key(self):
        with connected_apps(Settings(inference_provider='opencode', groq_api_key='unused-old-key')) as client:
            health = client.get('/health').json()
            self.assertEqual(health['interpretation_provider'], 'opencode')
            self.assertEqual(health['interpretation_model'], DEFAULT_OPENCODE_MODEL)
            self.assertFalse(health['interpretation_configured'])
            result = client.post('/chat', json={'text': TEXT})
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.json()['detail']['code'], 'model_not_configured')
            self.assertNotIn('unused-old-key', result.text)
            self.assertEqual(client.get('/medications/9079').status_code, 200)
