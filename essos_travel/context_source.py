from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import load_context


REQUIRED_CONTEXT_FIELDS = (
    "patient_id",
    "clinic",
    "destination",
    "timezone",
    "procedure_date",
    "arrival_deadline",
    "return_not_before",
    "outbound_date",
    "return_date",
)


def validate_context(value):
    if not isinstance(value, dict):
        raise ValueError("Patient context must be a JSON object.")
    missing = [key for key in REQUIRED_CONTEXT_FIELDS if key not in value]
    if missing:
        raise ValueError("Patient context is missing: " + ", ".join(missing))
    return value


def load_backend_context(url, token=None, timeout=15):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.load(response)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Patient context API returned HTTP {exc.code}.") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise ValueError("Patient context API could not be reached or returned invalid JSON.") from None
    return validate_context(value)


def resolve_context(path=None, url=None, token=None):
    if path and url:
        raise ValueError("Choose either --context or --context-url, not both.")
    if url:
        return load_backend_context(url, token)
    return validate_context(load_context(path))
