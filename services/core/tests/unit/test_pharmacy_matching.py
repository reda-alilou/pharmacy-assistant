import unittest
from pharmacy_core.pharmacies.directory import PharmacyDirectory
from pharmacy_core.pharmacies.normalization import NAME_ALIASES, directory_term, pharmacy_name
from tests.support.chat import response

def entities(**values):
    return response([], ['pharmacy_contact'], **values).interpretation.entities

class PharmacyMatchingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.directory = PharmacyDirectory.from_path()

    def test_reviewed_alias_targets_exist_and_raw_fields_are_preserved(self):
        for alias, target in NAME_ALIASES.items():
            self.assertIn(target, self.directory.name_index)
            result = self.directory.search(entities(pharmacy=alias))
            self.assertEqual(result.status, 'matches', alias)
            self.assertTrue(all((directory_term(r.name) == target for r in result.pharmacies)))
        raw = entities(pharmacy='صيدلية ابن نفيس', city='الرباط')
        result = self.directory.search(raw)
        self.assertEqual(raw.pharmacy, 'صيدلية ابن نفيس')
        self.assertEqual(result.name_alias, 'ibn nafis')
        self.assertEqual(result.match_method, 'reviewed_alias')
        self.assertEqual(result.pharmacies[0].pharmacy_id, 'saydalia:5256')
        self.assertEqual(result.pharmacies[0].phone, '0537720657')

    def test_punctuation_diacritics_attached_arabic_labels_and_lexical_variants(self):
        for name in ('Pharmacie: IBN-NAFIS', 'ibn nafis', 'IbNou Nafis', 'صيدلية إِبْن نَفِيس', 'الصيدلية ابن نفيس', 'صيدليةابننفيس', 'saydaliya Ibn Nafis'):
            with self.subTest(name=name):
                result = self.directory.search(entities(pharmacy=name))
                self.assertEqual(result.result_count, 1)
                self.assertEqual(result.pharmacies[0].pharmacy_id, 'saydalia:5256')

    def test_exact_names_win_over_real_directory_substring_collisions(self):
        for name, identifier in (('City Center', 'saydalia:4114'), ('Rabat', 'saydalia:4319'), ("De l'Agdal", 'saydalia:4301'), ('City Center Ryad', 'saydalia:4123')):
            result = self.directory.search(entities(pharmacy=name))
            self.assertEqual(result.result_count, 1)
            self.assertEqual(result.pharmacies[0].pharmacy_id, identifier)
            self.assertEqual(result.match_method, 'exact_name')

    def test_whole_tokens_do_not_match_substrings_or_numbers_inside_names(self):
        for name in ('naf', 'ibn naffis', 'sinaaa', 'XYZZZ999999', '6 novembre', 'pharmacie', '???'):
            result = self.directory.search(entities(pharmacy=name))
            self.assertEqual(result.status, 'not_found', name)
            self.assertFalse(result.pharmacies)
        self.assertEqual(self.directory.search(entities(pharmacy='16 novembre')).pharmacies[0].pharmacy_id, 'saydalia:4539')

    def test_broad_name_returns_ambiguity_and_retains_all_duplicate_identities(self):
        result = self.directory.search(entities(pharmacy='Ibn'))
        self.assertEqual(result.status, 'ambiguous')
        self.assertGreater(result.result_count, 1)
        self.assertLessEqual(len(result.pharmacies), 5)
        record = self.directory.name_index['ibn nafis'][0]
        other = record.model_copy(update={'pharmacy_id': 'synthetic:duplicate', 'phone': '0000000000'})
        duplicate = PharmacyDirectory([record, other]).search(entities(pharmacy='ابن نفيس'))
        self.assertEqual(duplicate.status, 'ambiguous')
        self.assertEqual(duplicate.result_count, 2)
        self.assertEqual({r.pharmacy_id for r in duplicate.pharmacies}, {record.pharmacy_id, other.pharmacy_id})

    def test_name_and_area_are_both_required_and_never_fall_back(self):
        result = self.directory.search(entities(pharmacy='Ibn Nafis', area='XYZZZ999999'))
        self.assertEqual(result.status, 'not_found')
        self.assertEqual(result.result_count, 0)
        result = self.directory.search(entities(pharmacy='ابن نفيس', city='Casablanca'))
        self.assertEqual(result.status, 'outside_coverage')
        self.assertFalse(result.pharmacies)

    def test_area_aliases_are_separate_from_pharmacy_names(self):
        for first, second in (('اكدال', 'Agdal'), ('حي الرياض', 'Hay Ryad'), ('حسان', 'Hassan')):
            one = self.directory.search(entities(area=first))
            two = self.directory.search(entities(area=second))
            self.assertEqual(one.result_count, two.result_count)
            self.assertEqual([r.pharmacy_id for r in one.pharmacies], [r.pharmacy_id for r in two.pharmacies])
            self.assertGreater(one.result_count, 0)
        self.assertEqual(pharmacy_name('حسان'), 'حسان')
        self.assertNotIn('hassan', self.directory.name_index)

    def test_browse_truncation_and_scope_are_explicit_and_records_are_unmodified(self):
        result = self.directory.search(entities())
        self.assertEqual(result.result_count, len(self.directory.records))
        self.assertEqual(len(result.pharmacies), 5)
        self.assertTrue(result.results_truncated)
        self.assertEqual(result.status, 'matches')
        self.assertTrue(result.city_defaulted)
        self.assertEqual(result.match_method, 'browse')
        self.assertEqual(result.duty_status, 'unverified')
        self.assertEqual(result.opening_hours_status, 'unknown')
        self.assertEqual(result.stock_status, 'unknown')
        self.assertTrue(all((r in self.directory.records for r in result.pharmacies)))
        self.assertEqual(PharmacyDirectory([]).search(entities()).status, 'not_found')
from unittest.mock import AsyncMock
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_core.conversation.service import ChatService
from pharmacy_core.conversation.models import ChatRequest

class PharmacyChatTests(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        cls.catalog, cls.directory = (MedicationCatalog.from_path(), PharmacyDirectory.from_path())

    def service(self, *interpretations):
        interpreter = AsyncMock()
        interpreter.interpret.side_effect = list(interpretations)
        return ChatService(self.catalog, interpreter, self.directory)

    async def test_multilingual_alias_returns_only_retrieved_contact_and_sources(self):
        for language, script, name in (('fr', 'latin', 'Pharmacie Ibn Nafis'), ('ar', 'arabic', 'صيدلية ابن نفيس'), ('darija', 'latin', 'Ibnou Nafis'), ('darija', 'arabic', 'صيدليةابننفيس')):
            service = self.service(response([], ['pharmacy_contact', 'opening_hours', 'pharmacy_on_duty'], language, script, pharmacy=name, city='Rabat'))
            body = await service.respond(ChatRequest(text='synthetic multilingual contact request'))
            self.assertEqual(body.pharmacy.result_count, 1)
            self.assertIn('0537720657', body.answer)
            self.assertEqual(body.interpretation.entities.pharmacy, name)
            self.assertEqual(body.pharmacy.duty_status, 'unverified')
            self.assertEqual(body.pharmacy.opening_hours_status, 'unknown')
            self.assertEqual(body.sources[0].record_ids, ['saydalia:5256'])
            self.assertFalse(body.medications)

    async def test_partial_name_clarifies_then_exact_name_targets_one_record(self):
        service = self.service(response([], ['pharmacy_contact'], pharmacy='Ibn', city='Rabat'), response([], ['pharmacy_contact'], pharmacy='صيدلية ابن نفيس'))
        first = await service.respond(ChatRequest(text='Téléphone pharmacie Ibn Rabat'))
        self.assertEqual(first.status, 'needs_clarification')
        self.assertEqual(first.pharmacy.status, 'ambiguous')
        self.assertIn('Plusieurs pharmacies', first.answer)
        second = await service.respond(ChatRequest(text='صيدلية ابن نفيس', session_id=first.session_id))
        self.assertEqual(second.status, 'answered')
        self.assertEqual(second.pharmacy.result_count, 1)
        self.assertEqual(second.pharmacy.pharmacies[0].pharmacy_id, 'saydalia:5256')
        self.assertIn('city', second.context.inherited_fields)
        self.assertEqual(service.interpreter.interpret.await_count, 2)
