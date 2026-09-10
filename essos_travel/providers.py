from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo


class ServiceError(Exception):
    pass


def request_json(url, headers, body, timeout=12):
    """Retry only flight searches, once, for transient failures; never orders/sends."""
    import ssl
    import sys
    import time
    from pathlib import Path
    from urllib.parse import urlparse
    context = ssl.create_default_context()
    if sys.platform == "darwin" and Path("/etc/ssl/cert.pem").exists():
        context.load_verify_locations(cafile="/etc/ssl/cert.pem")
    parsed = urlparse(url)
    attempts = 2 if parsed.hostname == "api.duffel.com" and parsed.path == "/air/offer_requests" else 1
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **headers}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            temporary = exc.code in (429, 500, 502, 503, 504)
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(retry_after) if retry_after and retry_after.isdigit() else (60 if retry_after else 1)
            exc.close()
            if temporary and attempt + 1 < attempts and delay <= 3:
                time.sleep(max(1, delay))
                continue
            explanations = {401: "Access key rejected; check the saved Duffel key.",
                403: "Account or token lacks access to this search.",
                422: "The provider rejected the search details.",
                429: "Too many searches. Wait before trying again."}
            raise ServiceError(f"Provider HTTP {exc.code}: " + explanations.get(exc.code,
                "The service is temporarily unavailable; try again later.")) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            cause = getattr(exc, "reason", exc)
            if isinstance(cause, ssl.SSLCertVerificationError):
                raise ServiceError("Secure connection failed certificate verification. Check the Python certificate setup.") from None
            if attempt + 1 < attempts:
                time.sleep(1)
                continue
            raise ServiceError("Flight service connection failed or timed out. Check internet access and try again.") from None
        except (ValueError, UnicodeError):
            raise ServiceError("Provider returned unreadable data. No results were used.") from None


class MockFlights:
    label = "DEMO — invented flights and prices"

    def search(self, preferences, context):
        outbound = date.fromisoformat(preferences["outbound_date"])
        back = date.fromisoformat(preferences["return_date"])
        # Fixed, deterministic fixtures: explicitly not a schedule simulator.
        offers = []
        for index, (name, price, stops, hours) in enumerate([
            ("Example Connect", 640, 1, 15), ("Example Direct", 890, 0, 11),
            ("Example Flex", 1080, 0, 12), ("Example Budget", 490, 2, 22),
        ]):
            offers.append({
                "id": f"demo-{index}", "airline": name, "amount": str(price * preferences["adults"]),
                "currency": "USD", "stops": stops, "duration_minutes": hours * 60,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                "slices": [
                    {"origin": preferences["origin"], "destination": context["destination"],
                     "departing_at": f"{outbound}T18:00:00", "arriving_at": f"{outbound + timedelta(days=1)}T12:00:00",
                     "arrival_timezone": context["timezone"], "stops": stops},
                    {"origin": context["destination"], "destination": preferences["origin"],
                     "departing_at": f"{back}T14:00:00", "arriving_at": f"{back}T18:00:00",
                     "arrival_timezone": "UTC", "stops": stops},
                ],
                "baggage": "Not specified in demo", "source": "mock",
            })
        return offers


class DuffelFlights:
    def __init__(self, token, http=request_json):
        if not token:
            raise ValueError("Configure DUFFEL_ACCESS_TOKEN before choosing Duffel.")
        if not token.startswith(("duffel_test_", "duffel_live_")):
            raise ValueError("Expected a Duffel test or live access token.")
        self.token, self.http = token, http
        self.live = token.startswith("duffel_live_")
        self.label = "LIVE — Duffel" if self.live else "SANDBOX — Duffel test results"

    def search(self, preferences, context):
        body = {"data": {
            "slices": [
                {"origin": preferences["origin"], "destination": context["destination"], "departure_date": preferences["outbound_date"]},
                {"origin": context["destination"], "destination": preferences["origin"], "departure_date": preferences["return_date"]},
            ], "passengers": [{"type": "adult"} for _ in range(preferences["adults"])],
            "cabin_class": "economy",
        }}
        if preferences["max_stops"] is not None:
            body["data"]["max_connections"] = preferences["max_stops"]
        response = self.http("https://api.duffel.com/air/offer_requests?return_offers=true&supplier_timeout=10000",
            {"Authorization": f"Bearer {self.token}", "Duffel-Version": "v2", "Accept": "application/json"}, body)
        try:
            data = response["data"]
            if data["live_mode"] is not self.live:
                raise ServiceError("Provider mode differs from the configured mode; results withheld.")
            return [parsed for raw in data["offers"] if (parsed := self.normalize(raw))]
        except (KeyError, TypeError):
            raise ServiceError("The flight provider returned an unexpected response.") from None

    @staticmethod
    def normalize(raw):
        try:
            import re
            slices, minutes = [], 0
            carriers = []
            for part_index, part in enumerate(raw["slices"]):
                segments = part["segments"]
                if not segments:
                    return None
                first, last = segments[0], segments[-1]
                slices.append({"origin": first["origin"]["iata_code"], "destination": last["destination"]["iata_code"],
                    "departing_at": first["departing_at"], "arriving_at": last["arriving_at"],
                    "arrival_timezone": last["destination"]["time_zone"], "stops": len(segments) - 1,
                    "duration": part.get("duration"),
                    "segments": [{
                        "id": segment.get("id"),
                        "origin": segment["origin"]["iata_code"],
                        "destination": segment["destination"]["iata_code"],
                        "departure_timezone": segment["origin"].get("time_zone"),
                        "arrival_timezone": segment["destination"].get("time_zone"),
                        "departing_at": segment["departing_at"],
                        "arriving_at": segment["arriving_at"],
                        "operating_carrier": segment.get("operating_carrier"),
                        "marketing_carrier": segment.get("marketing_carrier"),
                        "operating_flight_number": segment.get("operating_carrier_flight_number"),
                        "marketing_flight_number": segment.get("marketing_carrier_flight_number"),
                        "duration": segment.get("duration"),
                        "passenger_fares": [{k: passenger.get(k) for k in
                            ("cabin_class", "cabin_class_marketing_name", "fare_basis_code", "baggages")}
                            for passenger in segment.get("passengers", [])],
                    } for segment in segments]})
                if part_index == 0:
                    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", part.get("duration", ""))
                    minutes = int(match[1] or 0) * 60 + int(match[2] or 0) if match else 0
                for segment in segments:
                    name = segment["operating_carrier"]["name"]
                    if name not in carriers:
                        carriers.append(name)
            amount = Decimal(raw["total_amount"])
            if not amount.is_finite() or amount <= 0 or len(slices) != 2:
                return None
            return {"id": raw["id"], "airline": " / ".join(carriers), "amount": str(amount),
                "currency": raw["total_currency"], "slices": slices,
                "stops": max(s["stops"] for s in slices), "duration_minutes": minutes,
                "expires_at": raw["expires_at"], "baggage": "Check fare details with the provider",
                "source": "duffel", "conditions": raw.get("conditions"), "owner": raw.get("owner")}
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return None


def rejection_reason(offer, preferences, context):
    """Validate returned facts independently of the language model and supplier filters."""
    try:
        outward, inward = offer["slices"]
        if (outward["origin"], outward["destination"], inward["origin"], inward["destination"]) != (
            preferences["origin"], context["destination"], context["destination"], preferences["origin"]):
            return "route_mismatch"
        if outward["departing_at"][:10] != preferences["outbound_date"] or inward["departing_at"][:10] != preferences["return_date"]:
            return "travel_date_mismatch"
        arrival = datetime.fromisoformat(outward["arriving_at"])
        if arrival.tzinfo is None:
            arrival = arrival.replace(tzinfo=ZoneInfo(outward["arrival_timezone"]))
        if arrival > datetime.fromisoformat(context["arrival_deadline"]):
            return "arrives_after_clinic_deadline"
        if inward["departing_at"][:10] < context["return_not_before"]:
            return "return_before_permitted_date"
        expiry = datetime.fromisoformat(offer["expires_at"].replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            return "expired_or_invalid_expiry"
        if preferences["max_stops"] is not None and max(outward["stops"], inward["stops"]) > preferences["max_stops"]:
            return "too_many_stops"
        # v1 supports USD comparisons only; never compare different currencies numerically.
        price = Decimal(offer["amount"])
        if not price.is_finite() or price <= 0:
            return "invalid_price"
        if offer["currency"] != "USD":
            return "unsupported_currency"
        if preferences["budget"] is not None and price > Decimal(str(preferences["budget"])):
            return "over_budget"
        return None
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return "invalid_or_missing_data"


def eligible(offer, preferences, context):
    return rejection_reason(offer, preferences, context) is None


def distinct_itineraries(offers):
    """Keep first ranked fare per itinerary for display; callers retain all offers."""
    unique = {}
    for offer in offers:
        legs = []
        for part in offer["slices"]:
            if part.get("segments"):
                legs.append(tuple((segment["origin"], segment["destination"],
                    segment["departing_at"], segment["arriving_at"],
                    (segment.get("operating_carrier") or {}).get("iata_code") or
                    (segment.get("operating_carrier") or {}).get("name"),
                    segment.get("operating_flight_number"),
                    (segment.get("marketing_carrier") or {}).get("iata_code"),
                    segment.get("marketing_flight_number")) for segment in part["segments"]))
            else:
                # Without segment details, never collapse potentially different routes.
                legs.append((offer["id"],))
        unique.setdefault(tuple(legs), offer)
    return list(unique.values())


def flight_details(offer):
    lines = []
    for label, part in zip(("Outbound", "Return"), offer["slices"]):
        if not part.get("segments"):
            continue
        lines.append(label + ":")
        for segment in part["segments"]:
            carrier = segment.get("operating_carrier") or {}
            number = segment.get("operating_flight_number") or segment.get("marketing_flight_number") or ""
            lines.append(f"{carrier.get('name', 'Airline')} {number}: {segment['origin']} {segment['departing_at'][:16].replace('T', ' ')} → {segment['destination']} {segment['arriving_at'][:16].replace('T', ' ')}")
    return "\n".join(lines)
