import unittest

from essos_travel.prompts import intent_system_prompt


class PromptPolicyTests(unittest.TestCase):
    def setUp(self):
        self.prompt = intent_system_prompt().lower()

    def test_prompt_keeps_clinic_context_immutable(self):
        self.assertIn("never change clinic destination", self.prompt)
        self.assertIn("procedure dates are already known", self.prompt)

    def test_prompt_forbids_fabricated_flight_facts(self):
        self.assertIn("never invent flight offers", self.prompt)
        self.assertIn("booking status", self.prompt)

    def test_prompt_preserves_existing_preferences(self):
        self.assertIn("do not relax an existing preference", self.prompt)
        self.assertIn("explicitly", self.prompt)

    def test_prompt_rejects_unsupported_mixed_requests(self):
        self.assertIn("unsupported requirement", self.prompt)
        self.assertIn("rather than silently ignoring it", self.prompt)


if __name__ == "__main__":
    unittest.main()
