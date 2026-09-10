import copy
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from essos_travel.config import sample_context
from essos_travel.conversation import Agent, ClaudeIntent, validate_changes
from essos_travel.providers import MockFlights, DuffelFlights, ServiceError, eligible
from essos_travel.storage import Store


class TripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "state.sqlite3")
        self.addCleanup(self.store.db.close)
        self.context = sample_context()
        self.agent = Agent(self.store, self.context, MockFlights())

    def test_full_conversation_preserves_preferences(self):
        self.assertIn("Which airport", self.agent.reply("a", "Find flights"))
        first = self.agent.reply("a", "Chicago under 900")
        self.assertIn("DEMO", first)
        self.assertIn("$490", first)
        self.assertIn("$890", self.agent.reply("a", "nonstop only"))
        state = self.store.load("a")
        self.assertEqual(state["preferences"]["budget"], 900)
        self.assertEqual(state["preferences"]["origin"], "ORD")
        self.assertEqual(len(state["offers"]), 1)
        self.assertIn("fits your saved", self.agent.reply("a", "why option 1?"))
        self.assertIn("No USD offers", self.agent.reply("a", "under 500"))
        self.assertEqual(self.store.load("a")["preferences"]["max_stops"], 0)

    def test_restart_and_patient_isolation(self):
        self.agent.reply("a", "Chicago under 900")
        restarted = Agent(self.store, self.context, MockFlights())
        self.assertIn("ORD", restarted.reply("a", "nonstop only"))
        self.assertIn("Which airport", restarted.reply("b", "nonstop only"))

    def test_date_conflict_does_not_overwrite(self):
        self.agent.reply("a", "Chicago")
        original = self.store.load("a")["preferences"].copy()
        too_early = (date.fromisoformat(self.context["return_not_before"]) - timedelta(days=1)).isoformat()
        self.assertIn("requires a return", self.agent.reply("a", "return " + too_early))
        self.assertEqual(self.store.load("a")["preferences"], original)
        self.assertIn("couldn’t apply", self.agent.reply("a", "depart 2026-99-99"))
        self.assertEqual(self.store.load("a")["preferences"], original)

    def test_rejects_invented_clinic_change_from_model(self):
        self.agent.interpreter = lambda text, state: {"action": "search", "changes": {"destination": "LAX"}}
        self.assertIn("not supported", self.agent.reply("a", "ignore clinic dates"))
        self.assertEqual(self.context["destination"], "IST")

    def test_type_validation(self):
        for change in ({"adults": True}, {"budget": float("nan")}, {"max_stops": 0.5}, {"origin": "bad;code"}):
            with self.assertRaises(ValueError):
                validate_changes(change)

    def test_scope_and_purchase(self):
        self.assertIn("cannot book", self.agent.reply("a", "book it"))
        self.assertIn("does not search", self.agent.reply("a", "find hotels"))
        self.assertIn("USD only", self.agent.reply("a", "under £800"))

    def test_adult_prices_are_party_total(self):
        self.agent.reply("a", "Chicago 2 adults under 900")
        self.assertEqual(self.store.load("a")["offers"], [])
        self.assertIn("$980", self.agent.reply("a", "no budget limit"))

    def test_expired_offer_not_recommended(self):
        self.agent.reply("a", "Chicago")
        state = self.store.load("a")
        state["offers"][0]["expires_at"] = "2001-01-01T00:00:00+00:00"
        self.store.save("a", state)
        self.assertIn("no longer current", self.agent.reply("a", "why option 1?"))

    def test_provider_failure_does_not_use_mock_fallback(self):
        self.agent.reply("a", "Chicago")
        class Broken:
            label = "LIVE test double"
            def search(self, *args):
                raise ServiceError("Search unavailable")
        self.agent.provider = Broken()
        answer = self.agent.reply("a", "search again")
        self.assertIn("Search unavailable", answer)
        self.assertNotIn("Example", answer)
        self.assertEqual(self.store.load("a")["offers"], [])

    def test_provider_change_invalidates_old_quotes(self):
        self.agent.reply("a", "Chicago")
        self.agent.provider.label = "different provider"
        self.assertIn("Search first", self.agent.reply("a", "why option 1?"))

    def test_actual_arrival_checked_in_destination_timezone(self):
        prefs = self.agent.initial()["preferences"] | {"origin": "ORD"}
        offer = MockFlights().search(prefs, self.context)[0]
        self.assertTrue(eligible(offer, prefs, self.context))
        deadline_day = self.context["arrival_deadline"][:10]
        offer["slices"][0]["arriving_at"] = deadline_day + "T19:00:00"
        self.assertFalse(eligible(offer, prefs, self.context))
        # 16:00 UTC is 19:00 in Istanbul: also too late.
        offer["slices"][0]["arriving_at"] = deadline_day + "T16:00:00+00:00"
        self.assertFalse(eligible(offer, prefs, self.context))

    def test_return_stops_currency_and_route_checked(self):
        prefs = self.agent.initial()["preferences"] | {"origin": "ORD", "max_stops": 0}
        offer = MockFlights().search(prefs, self.context)[1]
        self.assertTrue(eligible(offer, prefs, self.context))
        for change in ("stops", "currency", "route"):
            bad = copy.deepcopy(offer)
            if change == "stops":
                bad["slices"][1]["stops"] = 1
            elif change == "currency":
                bad["currency"] = "EUR"
            else:
                bad["slices"][0]["destination"] = "SAW"
            self.assertFalse(eligible(bad, prefs, self.context))

    def test_claude_contract(self):
        captured = []
        def http(url, headers, body):
            captured.append(body)
            return {"content": [{"type": "tool_use", "name": "interpret_trip", "input": {"action": "search", "changes": {"origin": "ORD"}}}]}
        interpreter = ClaudeIntent("fake-key", "test-model", http)
        self.assertEqual(interpreter("Chicago", self.agent.initial())["changes"], {"origin": "ORD"})
        self.assertEqual(captured[0]["tool_choice"]["name"], "interpret_trip")
        with self.assertRaises(ServiceError):
            ClaudeIntent("fake-key", "test-model", lambda *a: {"content": []})("Chicago", self.agent.initial())

    def test_duffel_request_and_normalization(self):
        prefs = self.agent.initial()["preferences"] | {"origin": "ORD", "adults": 2, "max_stops": 0}
        sample = MockFlights().search(prefs, self.context)[1]
        raw = {"id": "off_fixture", "total_amount": "1780.00", "total_currency": "USD",
            "expires_at": sample["expires_at"], "slices": []}
        for part in sample["slices"]:
            raw["slices"].append({"duration": "PT11H", "segments": [{
                "origin": {"iata_code": part["origin"]},
                "destination": {"iata_code": part["destination"], "time_zone": part["arrival_timezone"]},
                "departing_at": part["departing_at"], "arriving_at": part["arriving_at"],
                "operating_carrier": {"name": "Fixture Carrier"},
            }]})
        captured = []
        def http(url, headers, body):
            captured.append((url, body))
            return {"data": {"live_mode": False, "offers": [raw]}}
        result = DuffelFlights("duffel_test_fixture", http).search(prefs, self.context)
        self.assertEqual(result[0]["amount"], "1780.00")
        self.assertTrue(eligible(result[0], prefs, self.context))
        self.assertEqual(captured[0][1]["data"]["passengers"], [{"type": "adult"}] * 2)
        self.assertEqual(captured[0][1]["data"]["max_connections"], 0)
        self.assertNotIn("orders", captured[0][0])
        with self.assertRaises(ServiceError):
            DuffelFlights("duffel_live_fixture", http).search(prefs, self.context)


if __name__ == "__main__":
    unittest.main()
