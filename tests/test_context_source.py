import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from essos_travel.config import sample_context
from essos_travel.context_source import load_backend_context, resolve_context, validate_context


class FakeResponse:
    def __init__(self, value):
        self.stream = io.BytesIO(json.dumps(value).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args):
        return self.stream.read(*args)


class ContextSourceTests(unittest.TestCase):
    def test_validate_context_accepts_trip_shape(self):
        value = sample_context()
        self.assertEqual(validate_context(value)["patient_id"], value["patient_id"])

    def test_validate_context_rejects_missing_fields(self):
        value = sample_context()
        del value["destination"]
        with self.assertRaises(ValueError):
            validate_context(value)

    def test_rejects_invalid_backend_values(self):
        for key, bad in (("destination", "NEW YORK"), ("timezone", "Invalid/Zone"),
                         ("arrival_deadline", "2026-10-14T18:00:00"),
                         ("return_date", "2000-01-01"), ("clinic", None)):
            with self.subTest(key=key):
                value = sample_context()
                value[key] = bad
                with self.assertRaises(ValueError):
                    validate_context(value)

    def test_backend_context_loader(self):
        value = sample_context()
        with patch("urllib.request.urlopen", return_value=FakeResponse(value)) as mocked:
            loaded = load_backend_context("https://example.test/patient", token="secret")
        self.assertEqual(loaded["destination"], "IST")
        request = mocked.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer secret")

    def test_file_context_still_works(self):
        value = sample_context()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "patient.json"
            path.write_text(json.dumps(value))
            loaded = resolve_context(path=str(path))
        self.assertEqual(loaded["clinic"], value["clinic"])

    def test_cannot_choose_file_and_url_together(self):
        with self.assertRaises(ValueError):
            resolve_context(path="patient.json", url="https://example.test/patient")


if __name__ == "__main__":
    unittest.main()
