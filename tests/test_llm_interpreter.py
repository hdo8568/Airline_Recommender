import json
import unittest

from essos_travel.config import sample_context
from essos_travel.llm_interpreter import SafeClaudeIntent, context_for_model


class SafeClaudeIntentTests(unittest.TestCase):
    def test_context_projection_keeps_only_trip_fields(self):
        context = sample_context()
        context["patient_name"] = "Should Not Be Sent"
        context["phone"] = "+15555555555"
        projected = context_for_model(context)
        self.assertNotIn("patient_name", projected)
        self.assertNotIn("phone", projected)
        self.assertEqual(projected["destination"], context["destination"])
        self.assertEqual(projected["arrival_deadline"], context["arrival_deadline"])

    def test_request_payload_excludes_unneeded_patient_fields(self):
        captured = []

        def http(url, headers, body):
            captured.append(body)
            return {
                "content": [{
                    "type": "tool_use",
                    "name": "interpret_trip",
                    "input": {"action": "search", "changes": {"origin": "ORD"}},
                }]
            }

        context = sample_context()
        context["patient_name"] = "Should Not Be Sent"
        context["phone"] = "+15555555555"
        state = {
            "context": context,
            "preferences": {
                "origin": None,
                "budget": None,
                "max_stops": None,
                "adults": 1,
                "sort": "cheapest",
                "outbound_date": context["outbound_date"],
                "return_date": context["return_date"],
            },
            "history": [],
        }
        result = SafeClaudeIntent("fake-key", "fake-model", http)("Chicago", state)
        payload = json.loads(captured[0]["messages"][0]["content"])
        self.assertEqual(result["changes"]["origin"], "ORD")
        self.assertNotIn("patient_name", payload["clinic_context"])
        self.assertNotIn("phone", payload["clinic_context"])
        self.assertEqual(payload["clinic_context"]["destination"], context["destination"])


if __name__ == "__main__":
    unittest.main()
