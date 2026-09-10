import tempfile
import unittest
from pathlib import Path

from essos_travel.config import sample_context
from essos_travel.conversation import Agent, basic_intent
from essos_travel.providers import MockFlights
from essos_travel.storage import Store


class AgentEvalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "state.sqlite3")
        self.addCleanup(self.store.db.close)
        self.agent = Agent(self.store, sample_context(), MockFlights())

    def test_appointment_request_uses_known_context(self):
        answer = self.agent.reply("a", "Help me with travel for my appointment")
        self.assertIn("already have your clinic destination", answer)
        self.assertIn("Which airport", answer)

    def test_faster_followup_keeps_existing_filters(self):
        self.agent.reply("a", "Chicago under 900 nonstop only")
        self.agent.reply("a", "anything faster?")
        state = self.store.load("a")
        self.assertEqual(state["preferences"]["origin"], "ORD")
        self.assertEqual(state["preferences"]["budget"], 900)
        self.assertEqual(state["preferences"]["max_stops"], 0)
        self.assertEqual(state["preferences"]["sort"], "fastest")

    def test_cheaper_followup_changes_only_sorting(self):
        self.agent.reply("a", "Chicago")
        self.agent.reply("a", "anything cheaper?")
        state = self.store.load("a")
        self.assertEqual(state["preferences"]["origin"], "ORD")
        self.assertEqual(state["preferences"]["sort"], "cheapest")

    def test_baggage_mixed_request_is_not_silently_dropped(self):
        intent = basic_intent("nonstop under $900 with two checked bags", self.agent.initial())
        self.assertEqual(intent["action"], "unsupported")
        self.assertEqual(intent["changes"], {})

    def test_new_york_is_ambiguous(self):
        answer = self.agent.reply("a", "I'm leaving from New York")
        self.assertIn("Which departure airport", answer)
        self.assertIsNone(self.store.load("a")["preferences"]["origin"])

    def test_new_york_does_not_get_parsed_as_new_airport_code(self):
        intent = basic_intent("I'm leaving from New York", self.agent.initial())
        self.assertEqual(intent["action"], "airport")
        self.assertEqual(intent["changes"], {})

    def test_scope_does_not_change_trip_state(self):
        self.agent.reply("a", "Chicago under 900")
        before = self.store.load("a")["preferences"].copy()
        answer = self.agent.reply("a", "Can you find me a hotel too?")
        after = self.store.load("a")["preferences"]
        self.assertIn("Hotels", answer)
        self.assertEqual(before, after)

    def test_purchase_request_never_changes_state(self):
        self.agent.reply("a", "Chicago")
        before = self.store.load("a")["preferences"].copy()
        answer = self.agent.reply("a", "Buy option 1")
        after = self.store.load("a")["preferences"]
        self.assertIn("cannot book", answer)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
