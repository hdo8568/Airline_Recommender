import unittest
from essos_travel.config import sample_context
from essos_travel.evaluate import evaluate
from essos_travel.providers import ServiceError


class EvaluationTests(unittest.TestCase):
    def test_zero_results_is_success_and_one_search_only(self):
        calls = []
        def http(url, headers, body):
            calls.append(url)
            return {'data': {'live_mode': True, 'offers': []}}
        result = evaluate('duffel_live_fixture', sample_context(), http)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['offers_received'], 0)
        self.assertEqual(result['offers_eligible'], 0)
        self.assertEqual(len(calls), 1)
        self.assertIn('/offer_requests?', calls[0])

    def test_failure_is_not_reported_as_no_matches(self):
        def http(*args):
            raise ServiceError('Provider returned HTTP 401')
        result = evaluate('duffel_live_fixture', sample_context(), http)
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('offers_eligible', result)
        self.assertIn('401', result['error'])

    def test_mode_mismatch_fails(self):
        result = evaluate('duffel_live_fixture', sample_context(),
                          lambda *a: {'data': {'live_mode': False, 'offers': []}})
        self.assertEqual(result['status'], 'failed')
