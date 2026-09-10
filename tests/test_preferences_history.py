import json
import tempfile
import unittest
from pathlib import Path
from essos_travel.config import sample_context
from essos_travel.conversation import Agent
from essos_travel.providers import MockFlights
from essos_travel.storage import Store

class PreferencesHistoryTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store=Store(Path(self.folder.name)/'state.sqlite3')
        self.addCleanup(self.store.db.close)
        self.context=sample_context()
        self.agent=Agent(self.store,self.context,MockFlights())

    def test_preferences_and_reset_do_not_search(self):
        self.agent.reply('a','Chicago 2 adults under 2000 nonstop only')
        response=self.agent.reply('a','show preferences')
        self.assertIn('nonstop only',response)
        self.assertIn('2 adult',response)
        self.assertIn('$2,000',response)
        self.agent.interpreter=lambda *a: self.fail('Control command should not use interpreter')
        response=self.agent.reply('a','reset')
        self.assertIn('no limit',response)
        state=self.store.load('a')
        self.assertIsNone(state['preferences']['origin'])
        self.assertEqual(state['context'],self.context)
        self.assertEqual(state['offers'],[])
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM searches').fetchone()[0],1)

    def test_history_survives_followup_and_reset(self):
        first=self.agent.reply('a','Chicago under 1000')
        snapshot=json.loads(self.store.db.execute('SELECT value FROM searches').fetchone()[0])
        self.assertEqual(snapshot['response_text'],first)
        self.assertEqual(len(snapshot['displayed_offer_snapshot']),3)
        self.agent.reply('a','under 100')
        self.agent.reply('a','reset')
        preserved=json.loads(self.store.db.execute('SELECT value FROM searches ORDER BY id LIMIT 1').fetchone()[0])
        self.assertEqual(snapshot,preserved)
        latest=json.loads(self.store.db.execute('SELECT value FROM searches ORDER BY id DESC LIMIT 1').fetchone()[0])
        self.assertEqual(latest['displayed_offer_snapshot'],[])

    def test_multiple_passengers_and_changed_route(self):
        response=self.agent.reply('a','Boston 2 adults under 2000')
        self.assertIn('BOS',response)
        self.assertIn('$980.00',response)
        self.assertIn('2 adult',response)

    def test_changed_dates_and_invalid_date_preserve_context(self):
        from datetime import date, timedelta
        self.agent.reply('a','Chicago')
        departure=(date.fromisoformat(self.context['outbound_date'])-timedelta(days=1)).isoformat()
        returned=(date.fromisoformat(self.context['return_date'])+timedelta(days=1)).isoformat()
        self.agent.reply('a',f'depart {departure} return {returned}')
        state=self.store.load('a')
        self.assertEqual(state['preferences']['outbound_date'],departure)
        self.assertEqual(state['preferences']['return_date'],returned)
        self.assertEqual(state['context'],self.context)
        self.agent.reply('a','return 2000-01-01')
        self.assertEqual(self.store.load('a')['preferences'],state['preferences'])

    def test_reset_does_not_change_other_session(self):
        self.agent.reply('a','Chicago under 1000')
        self.agent.reply('b','Boston under 1200')
        other=self.store.load('b')
        self.agent.reply('a','reset')
        self.assertEqual(self.store.load('b'),other)
