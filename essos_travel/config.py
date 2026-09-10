from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from .travel_policy import apply_policy

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / ".local"


def private_dir(path=LOCAL):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def write_private(path, value):
    private_dir(path.parent)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
    tmp.replace(path)
    path.chmod(0o600)


def settings():
    path = LOCAL / "settings.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "DUFFEL_ACCESS_TOKEN"):
        if os.environ.get(key):
            data[key] = os.environ[key]
    return data


def sample_context():
    procedure = date.today() + timedelta(days=35)
    return apply_policy({
        "patient_id": "fictional-patient",
        "fictional": True,
        "clinic": "Example Clinic — fictional",
        "destination": "IST",
        "timezone": "Europe/Istanbul",
        "procedure_date": procedure.isoformat(),
        "arrival_deadline": f"{procedure - timedelta(days=1)}T18:00:00+03:00",
        "return_not_before": (procedure + timedelta(days=2)).isoformat(),
        "outbound_date": (procedure - timedelta(days=2)).isoformat(),
        "return_date": (procedure + timedelta(days=2)).isoformat(),
        "policy_note": "Fictional clinic-supplied scheduling constraints for testing; not medical advice.",
    })


def load_context(path=None):
    path = Path(path) if path else LOCAL / "patient.json"
    if not path.exists():
        if path != LOCAL / "patient.json":
            raise ValueError("The supplied patient file does not exist.")
        write_private(path, sample_context())
    value = json.loads(path.read_text())
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ZoneInfo(value["timezone"])
    deadline = datetime.fromisoformat(value["arrival_deadline"])
    if deadline.tzinfo is None:
        raise ValueError("The clinic arrival deadline needs a timezone offset.")
    for key in ("procedure_date", "return_not_before", "outbound_date", "return_date"):
        date.fromisoformat(value[key])
    if not isinstance(value["destination"], str) or len(value["destination"]) != 3:
        raise ValueError("Use a three-letter destination airport code.")
    return apply_policy(value)
