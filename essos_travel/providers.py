from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo


class ServiceError(Exception):
    pass


def request_json(url, headers, body, timeout=30):
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Never echo a provider body, request, or credential into the chat/log.
        raise ServiceError(f"Provider returned HTTP {exc.code}. Check credentials/access or try later.") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise ServiceError("The provider could not be reached or returned an invalid response.") from None


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
                    "arrival_timezone": last["destination"]["time_zone"], "stops": len(segments) - 1})
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
                "source": "duffel"}
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return None


def eligible(offer, preferences, context):
    """Validate returned facts independently of the language model and supplier filters."""
    try:
        outward, inward = offer["slices"]
        if (outward["origin"], outward["destination"], inward["origin"], inward["destination"]) != (
            preferences["origin"], context["destination"], context["destination"], preferences["origin"]):
            return False
        if outward["departing_at"][:10] != preferences["outbound_date"] or inward["departing_at"][:10] != preferences["return_date"]:
            return False
        arrival = datetime.fromisoformat(outward["arriving_at"])
        if arrival.tzinfo is None:
            arrival = arrival.replace(tzinfo=ZoneInfo(outward["arrival_timezone"]))
        if arrival > datetime.fromisoformat(context["arrival_deadline"]):
            return False
        if inward["departing_at"][:10] < context["return_not_before"]:
            return False
        expiry = datetime.fromisoformat(offer["expires_at"].replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            return False
        if preferences["max_stops"] is not None and max(outward["stops"], inward["stops"]) > preferences["max_stops"]:
            return False
        # v1 supports USD comparisons only; never compare different currencies numerically.
        price = Decimal(offer["amount"])
        if offer["currency"] != "USD" or not price.is_finite() or price <= 0:
            return False
        return preferences["budget"] is None or price <= Decimal(str(preferences["budget"]))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return False
