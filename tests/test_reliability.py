import io
import json
import ssl
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from essos_travel.providers import request_json, ServiceError, MockFlights
from essos_travel.messages import readable_text
from essos_travel.storage import Store
from essos_travel.config import sample_context
from essos_travel.conversation import Agent

SEARCH='https://api.duffel.com/air/offer_requests?return_offers=true'

class ReliabilityTests(unittest.TestCase):
    def test_search_recovers_from_one_temporary_failure(self):
        error=urllib.error.HTTPError(SEARCH,503,'bad',{},None)
        with patch('urllib.request.urlopen', side_effect=[error,io.BytesIO(b'{"data": {}}')]) as call, patch('time.sleep'):
            self.assertEqual(request_json(SEARCH,{},{}), {'data':{}})
        self.assertEqual(call.call_count,2)
        self.assertEqual(call.call_args.kwargs['context'].verify_mode, ssl.CERT_REQUIRED)

    def test_bad_key_is_not_retried_or_leaked(self):
        error=urllib.error.HTTPError(SEARCH,401,'secret response',{},None)
        with patch('urllib.request.urlopen', side_effect=error) as call:
            with self.assertRaises(ServiceError) as caught:
                request_json(SEARCH,{}, {})
        self.assertEqual(call.call_count,1)
        self.assertNotIn('secret',str(caught.exception))

    def test_timeout_retry_is_bounded(self):
        with patch('urllib.request.urlopen',side_effect=TimeoutError) as call, patch('time.sleep'):
            with self.assertRaises(ServiceError): request_json(SEARCH,{}, {})
        self.assertEqual(call.call_count,2)

    def test_nonsearch_operation_never_retries(self):
        with patch('urllib.request.urlopen',side_effect=TimeoutError) as call:
            with self.assertRaises(ServiceError): request_json('https://api.duffel.com/air/orders',{}, {})
        self.assertEqual(call.call_count,1)

    def test_long_retry_after_does_not_block(self):
        error=urllib.error.HTTPError(SEARCH,429,'bad',{'Retry-After':'60'},None)
        with patch('urllib.request.urlopen', side_effect=error) as call, patch('time.sleep') as sleep:
            with self.assertRaises(ServiceError): request_json(SEARCH,{}, {})
        self.assertEqual(call.call_count,1)
        sleep.assert_not_called()

    def test_unreadable_response_fails_without_retry(self):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'not json')) as call:
            with self.assertRaisesRegex(ServiceError,'unreadable'): request_json(SEARCH,{}, {})
        self.assertEqual(call.call_count,1)

    def test_certificate_failure_is_not_retried(self):
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError(ssl.SSLCertVerificationError('bad'))) as call:
            with self.assertRaisesRegex(ServiceError,'certificate'): request_json(SEARCH,{}, {})
        self.assertEqual(call.call_count,1)

    def test_invisible_messages_cleaned_without_losing_words(self):
        for text in ('\ufffc','\u200b\ufeff','\u00a0\ufffc\u200d',None):
            self.assertEqual(readable_text(text),'')
        self.assertEqual(readable_text('Chicago\u200b under 900'),'Chicago under 900')

    def test_conversation_search_audit_records_failure_and_filtering(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'state.sqlite3')
            self.addCleanup(store.db.close)
            agent=Agent(store,sample_context(),MockFlights())
            agent.reply('one','Chicago under 500')
            entry=json.loads(store.db.execute('SELECT value FROM searches').fetchone()[0])
            self.assertEqual(entry['eligible_offers'],1)
            self.assertEqual(entry['rejection_counts'],{'over_budget':3})
            class Broken:
                label='broken'
                def search(self,*a): raise ServiceError('Temporary failure')
            agent.provider=Broken()
            answer=agent.reply('one','search again')
            self.assertIn('Temporary failure',answer)
            entry=json.loads(store.db.execute('SELECT value FROM searches ORDER BY id DESC LIMIT 1').fetchone()[0])
            self.assertEqual(entry['status'],'failed')
            self.assertNotIn('eligible_offers',entry)
