import tempfile
import unittest
from pathlib import Path

from essos_travel.advanced_agent import AdvancedAgent
from essos_travel.config import sample_context
from essos_travel.providers import MockFlights
from essos_travel.ranking import recommend_offer
from essos_travel.storage import Store


class AdvancedAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "state.sqlite3")
        self.addCleanup(self.store.db.close)
        self.agent = AdvancedAgent(self.store, sample_context(), MockFlights())

    def test_recommendation_requires_search(self):
        answer = self.agent.reply("a", "which one would you recommend?")
        self.assertIn("current shortlist", answer)

    def test_recommendation_uses_current_filtered_options(self):
        self.agent.reply("a", "Chicago under 900")
        answer = self.agent.reply("a", "which one should I pick?")
        state = self.store.load("a")
        self.assertIn("I’d pick option", answer)
        self.assertTrue(state["offers"])
        chosen = recommend_offer(state["offers"])
        self.assertIn(chosen["airline"], answer)
        self.assertIn("Nothing is booked", answer)

    def test_recommendation_respects_nonstop_filter(self):
        self.agent.reply("a", "Chicago under 900 nonstop only")
        answer = self.agent.reply("a", "best option?")
        self.assertIn("Example Direct", answer)
        self.assertNotIn("Example Budget", answer)

    def test_compare_two_options(self):
        self.agent.reply("a", "Chicago")
        answer = self.agent.reply("a", "compare 1 and 2")
        self.assertIn("1.", answer)
        self.assertIn("2.", answer)
        self.assertIn("total", answer)
        self.assertIn("outbound", answer)

    def test_compare_all_current_options(self):
        self.agent.reply("a", "Chicago")
        answer = self.agent.reply("a", "compare the options")
        self.assertIn("quick comparison", answer)
        self.assertIn("recommend", answer)

    def test_direct_agent_actions_preserve_preferences(self):
        self.agent.reply("a", "Chicago under 900")
        before = self.store.load("a")["preferences"].copy()
        self.agent.reply("a", "which one would you recommend?")
        after = self.store.load("a")["preferences"]
        self.assertEqual(before, after)

    def test_date_question_uses_known_clinic_context(self):
        answer = self.agent.reply("a", "when do I need to arrive?")
        context = self.agent.context
        self.assertIn(context["arrival_deadline"], answer)
        self.assertIn(context["return_not_before"], answer)
        self.assertNotIn("Which airport", answer)

    def test_destination_question_uses_known_clinic_context(self):
        answer = self.agent.reply("a", "where am I going?")
        context = self.agent.context
        self.assertIn(context["clinic"], answer)
        self.assertIn(context["destination"], answer)

    def test_context_questions_do_not_change_preferences(self):
        self.agent.reply("a", "Chicago under 900")
        before = self.store.load("a")["preferences"].copy()
        self.agent.reply("a", "what are my dates?")
        self.agent.reply("a", "what is my destination?")
        after = self.store.load("a")["preferences"]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
