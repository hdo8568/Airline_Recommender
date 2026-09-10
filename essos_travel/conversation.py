from __future__ import annotations

import json
import copy
import re
import time
from collections import Counter
from datetime import date, datetime
from decimal import Decimal

from .prompts import intent_system_prompt
from .providers import ServiceError, eligible, request_json, distinct_itineraries, flight_details, rejection_reason

AIRPORTS = {"chicago": "ORD", "o'hare": "ORD", "jfk": "JFK", "newark": "EWR", "boston": "BOS",
    "los angeles": "LAX", "san francisco": "SFO", "seattle": "SEA", "miami": "MIA",
    "toronto": "YYZ", "heathrow": "LHR", "atlanta": "ATL", "dallas": "DFW"}
HELP = "Tell me your departure airport, total round-trip budget in USD, and whether you need nonstop flights. You can also say ‘cheapest’, ‘fastest’, ‘2 adults’, ‘depart YYYY-MM-DD’, ‘return YYYY-MM-DD’, or ‘why option 2?’. Clinic dates stay fixed. Say ‘show preferences’ or ‘reset’."


def basic_intent(text, state):
    low = text.lower().strip()
    patches = {}
    if any(word in low for word in ("hotel", "clinic search", "find a clinic", "book a clinic")):
        return {"action": "scope", "changes": {}}
    if any(word in low for word in ("baggage", "checked bag", "carry-on", "refund", "wheelchair", "business class", "premium economy", "first class", "delta only", "points", "miles")):
        return {"action": "unsupported", "changes": {}}
    if re.search(r"€|£|\beur\b|\bgbp\b", low):
        return {"action": "currency", "changes": {}}
    if re.search(r"\b(book|buy|purchase|pay|ticket it)\b", low):
        return {"action": "purchase", "changes": {}}
    if re.search(r"\b(why|explain|details|detail|second|third|first option)\b", low):
        match = re.search(r"\b([123])\b", low)
        return {"action": "explain", "option": int(match[1]) if match else 2 if "second" in low else 3 if "third" in low else 1, "changes": {}}
    if low in ("help", "/help", "?", "hello", "hi"):
        return {"action": "help", "changes": {}}
    if "new york" in low:
        return {"action": "airport", "changes": {}}
    for name, airport in AIRPORTS.items():
        if re.search(r"\b" + re.escape(name) + r"\b", low):
            patches["origin"] = airport
    match = re.search(r"(?:\bfrom\s+|/from\s+)([a-z]{3})\b", low)
    if match:
        patches["origin"] = match[1].upper()
    elif re.fullmatch(r"[A-Z]{3}", text.strip()):
        patches["origin"] = text.strip()
    amount = re.search(r"(?:under\s*|budget(?:\s+is|\s+of)?\s*|up to\s*|\$)(\d[\d,]*(?:\.\d{1,2})?)", low)
    if amount:
        patches["budget"] = float(amount[1].replace(",", ""))
    if low in ("no budget", "no budget limit", "remove budget", "any price", "whatever it costs"):
        patches["budget"] = None
    if re.search(r"\b(non[- ]?stop|direct)\b", low):
        patches["max_stops"] = 0
    if re.search(r"(one|1) (stop|layover)", low):
        patches["max_stops"] = 1
    if low in ("any stops", "layovers are fine", "remove nonstop", "connections are fine", "stops are fine"):
        patches["max_stops"] = None
    if "fastest" in low or "shortest" in low or "faster" in low or "quicker" in low:
        patches["sort"] = "fastest"
    if "cheapest" in low or "cheaper" in low or "less expensive" in low:
        patches["sort"] = "cheapest"
    adults = re.search(r"\b([1-6]) (?:adults?|people|passengers?)\b", low)
    if adults:
        patches["adults"] = int(adults[1])
    for pattern, key in ((r"\b(?:depart|leave|outbound)(?: on)? (\d{4}-\d{2}-\d{2})\b", "outbound_date"),
                         (r"\breturn(?: on)? (\d{4}-\d{2}-\d{2})\b", "return_date")):
        match = re.search(pattern, low)
        if match:
            patches[key] = match[1]
    if patches or re.search(r"\b(search|find|flights?|again|options|appointment|trip|travel)\b", low):
        return {"action": "search", "changes": patches}
    return {"action": "unsupported", "changes": {}}


SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": ["search", "explain", "help", "scope", "purchase", "unsupported", "airport", "currency"]},
        "option": {"type": "integer", "minimum": 1, "maximum": 3},
        "changes": {"type": "object", "additionalProperties": False, "properties": {
            "origin": {"type": "string", "pattern": "^[A-Z]{3}$"},
            "budget": {"type": ["number", "null"], "exclusiveMinimum": 0, "maximum": 100000},
            "max_stops": {"type": ["integer", "null"], "minimum": 0, "maximum": 2},
            "adults": {"type": "integer", "minimum": 1, "maximum": 6},
            "sort": {"type": "string", "enum": ["cheapest", "fastest"]},
            "outbound_date": {"type": "string"}, "return_date": {"type": "string"},
        }},
    }, "required": ["action", "changes"],
}


class ClaudeIntent:
    def __init__(self, key, model, http=request_json):
        if not key or not model:
            raise ValueError("Configure ANTHROPIC_API_KEY and ANTHROPIC_MODEL before enabling Claude.")
        self.key, self.model, self.http = key, model, http

    def __call__(self, text, state):
        response = self.http("https://api.anthropic.com/v1/messages",
            {"x-api-key": self.key, "anthropic-version": "2023-06-01"}, {
                "model": self.model, "max_tokens": 600, "system": intent_system_prompt(),
                "messages": [{"role": "user", "content": json.dumps({"today": date.today().isoformat(),
                    "clinic_context": state.get("context", {}), "preferences": state["preferences"],
                    "recent_history": state.get("history", [])[-6:], "message": text})}],
                "tools": [{"name": "interpret_trip", "description": "Extract supported flight preferences or classify the question.", "input_schema": SCHEMA}],
                "tool_choice": {"type": "tool", "name": "interpret_trip"},
            })
        if not isinstance(response, dict) or not isinstance(response.get("content"), list):
            raise ServiceError("The AI returned an unexpected response.")
        blocks = [b for b in response["content"] if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "interpret_trip"]
        if len(blocks) != 1 or not isinstance(blocks[0].get("input"), dict):
            raise ServiceError("The AI returned an invalid preference update. Please try a simpler message.")
        return blocks[0]["input"]


def validate_changes(changes):
    if not isinstance(changes, dict) or set(changes) - set(SCHEMA["properties"]["changes"]["properties"]):
        raise ValueError("That preference update is not supported.")
    for key, value in changes.items():
        if key == "origin" and (not isinstance(value, str) or not re.fullmatch("[A-Z]{3}", value)):
            raise ValueError("Use a three-letter departure airport code, such as ORD.")
        if key == "budget" and value is not None and (type(value) not in (float, int) or not 0 < value <= 100000):
            raise ValueError("Use a total USD budget between 0 and 100,000.")
        if key == "max_stops" and value is not None and (type(value) is not int or value not in (0, 1, 2)):
            raise ValueError("Maximum stops must be 0, 1, 2, or unrestricted.")
        if key == "adults" and (type(value) is not int or not 1 <= value <= 6):
            raise ValueError("This draft supports 1–6 adults.")
        if key == "sort" and value not in ("cheapest", "fastest"):
            raise ValueError("Choose cheapest or fastest.")
        if key.endswith("_date"):
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Use dates formatted YYYY-MM-DD.")
            date.fromisoformat(value)


class Agent:
    def __init__(self, store, context, provider, interpreter=basic_intent):
        self.store, self.context, self.provider, self.interpreter = store, context, provider, interpreter

    def initial(self):
        return {"context": self.context, "provider": self.provider.label, "preferences": {"origin": None, "budget": None, "max_stops": None,
            "adults": 1, "sort": "cheapest", "outbound_date": self.context["outbound_date"],
            "return_date": self.context["return_date"]}, "offers": [], "history": []}

    def reply(self, session, text):
        if not text.strip() or len(text) > 4000:
            return "Please send a short text message (up to 4,000 characters)."
        state = self.store.load(session) or self.initial()
        if state.get("context") != self.context:
            state = self.initial()
        if state.get("provider") != self.provider.label:
            state["offers"], state["history"] = [], []
            state["provider"] = self.provider.label
        self.last_search = None
        try:
            command = text.strip().lower()
            if command in ("reset", "/reset", "start over"):
                state = self.initial()
                response = "Preferences reset; clinic destination and scheduling rules stay fixed.\n" + self.preference_summary(state["preferences"])
            elif command in ("show preferences", "preferences", "/preferences"):
                response = self.preference_summary(state["preferences"])
            else:
                intent = self.interpreter(text, state)
                response = self.respond(state, intent)
        except ServiceError as exc:
            state["offers"] = []
            response = f"I couldn’t complete that request. {exc} No flights were booked."
        except (ValueError, TypeError, KeyError) as exc:
            response = "I couldn’t apply that change. " + (str(exc) if isinstance(exc, ValueError) else "Please use a supported preference.")
        if self.last_search is not None:
            self.last_search.update(displayed_offer_snapshot=copy.deepcopy(state["offers"]),
                response_text=response, user_message=text,
                clinic_context=copy.deepcopy(self.context))
            self.store.record_search(session, self.last_search)
        state["history"] = (state.get("history", []) + [{"role": "user", "text": text}, {"role": "assistant", "text": response}])[-12:]
        self.store.save(session, state)
        return response

    def preference_summary(self, preferences):
        budget = "no limit" if preferences["budget"] is None else f"${preferences['budget']:,.2f} total round trip"
        stops = "any stops" if preferences["max_stops"] is None else "nonstop only" if preferences["max_stops"] == 0 else f"up to {preferences['max_stops']} stops each way"
        return (f"Active preferences: {preferences['origin'] or 'departure airport not set'} → {self.context['destination']}; "
            f"{preferences['adults']} adult(s), economy; budget {budget}; {stops}; {preferences['sort']} first.\n"
            f"Depart {preferences['outbound_date']}; return {preferences['return_date']}.\n"
            f"Clinic: arrive by {self.context['arrival_deadline']}; return no earlier than {self.context['return_not_before']}. "
            "Say ‘reset’ to clear travel preferences and restore default dates.")

    def respond(self, state, intent):
        action = intent.get("action")
        if action not in SCHEMA["properties"]["action"]["enum"]:
            raise ValueError("Please ask for flights or a supported preference change.")
        messages = {
            "help": HELP,
            "scope": "I can help with flights for your selected clinic. This version does not search hotels or clinics. Hotels are outside this demo.",
            "purchase": "I can compare flights, but I cannot book or pay for them. Nothing has been purchased.",
            "unsupported": "I can’t verify that preference yet, so I left your search unchanged. " + HELP,
            "airport": "Which departure airport should I use? Please send the three-letter code, such as JFK or EWR.",
            "currency": "I can only use a total round-trip budget in USD right now. Send the USD amount and I’ll keep the rest of your preferences.",
        }
        if action in messages:
            return messages[action]
        if action == "explain":
            index = intent.get("option", 1)
            if type(index) is not int or not 1 <= index <= len(state["offers"]):
                return "Search first, then ask something like ‘why option 1?’"
            offer = state["offers"][index - 1]
            if not eligible(offer, state["preferences"], self.context):
                state["offers"] = []
                return "That quote is no longer current. Say ‘search again’ and I’ll refresh it."
            return (f"{self.provider.label}\nOption {index} fits your saved dates and current filters. "
                f"It has at most {offer['stops']} stop(s) each way and costs ${Decimal(offer['amount']):,.2f} total for your party. "
                f"Results are ordered by {state['preferences']['sort']}. Baggage/refund terms are not verified. Nothing is booked.\n" + flight_details(offer))
        changes = intent.get("changes", {})
        validate_changes(changes)
        preferences = {**state["preferences"], **changes}
        if preferences["outbound_date"] < date.today().isoformat():
            return "That departure date is in the past. Send a future date; I left your current trip unchanged."
        if preferences["outbound_date"] > self.context["arrival_deadline"][:10]:
            return "That departure is too late for the clinic arrival deadline. Send an earlier date; I left your current trip unchanged."
        if preferences["return_date"] < self.context["return_not_before"]:
            return f"Your clinic context requires a return on or after {self.context['return_not_before']}. I left your current dates unchanged."
        if preferences["return_date"] <= preferences["outbound_date"]:
            return "Your return has to be after your departure. I left your current dates unchanged."
        if preferences["origin"] == self.context["destination"]:
            return "Your departure and clinic airports are the same. Send the airport you’re actually leaving from."
        state["preferences"], state["offers"] = preferences, []
        if not preferences["origin"]:
            return f"I already have your clinic destination ({self.context['destination']}) and dates. Which airport are you leaving from?"
        started = time.monotonic()
        self.last_search = {"provider": self.provider.label, "preferences": dict(preferences),
                            "destination": self.context["destination"], "status": "searching"}
        try:
            received = self.provider.search(preferences, self.context)
        except ServiceError as exc:
            self.last_search.update(status="failed", error=str(exc), elapsed_seconds=round(time.monotonic()-started, 2))
            raise
        reasons = Counter()
        offers = []
        for offer in received:
            reason = rejection_reason(offer, preferences, self.context)
            if reason:
                reasons[reason] += 1
            else:
                offers.append(offer)
        self.last_search.update(status="success", elapsed_seconds=round(time.monotonic()-started, 2),
            normalized_offers=len(received), eligible_offers=len(offers), rejection_counts=dict(reasons))
        if preferences["sort"] == "fastest":
            offers.sort(key=lambda o: (o["duration_minutes"] or float("inf"), Decimal(o["amount"])))
        else:
            offers.sort(key=lambda o: (Decimal(o["amount"]), o["stops"]))
        grouped = distinct_itineraries(offers)
        state["offers"] = grouped[:3]
        self.last_search.update(distinct_itineraries=len(grouped), displayed_offers=len(state["offers"]))
        summary = f"{preferences['origin']} ↔ {self.context['destination']} · depart {preferences['outbound_date']} · return {preferences['return_date']}"
        summary += "\n" + self.preference_summary(preferences)
        if not state["offers"]:
            return f"{self.provider.label}\n{summary}\nNo USD offers fit all of your current filters. I didn’t relax anything. You can raise the budget, allow more stops, or change the permitted dates."
        lines = [self.provider.label, summary, f"Economy · {preferences['adults']} adult(s) · TOTAL round-trip USD · {preferences['sort']} first"]
        for index, offer in enumerate(state["offers"], 1):
            out, back = offer["slices"]
            lines.append(f"{index}. {offer['airline']} — ${Decimal(offer['amount']):,.2f}; up to {offer['stops']} stop(s) each way. "
                f"Arrive {out['arriving_at'][:16].replace('T', ' ')}; return departs {back['departing_at'][:16].replace('T', ' ')}.")
            if out.get("segments") and back.get("segments"):
                def route(part):
                    return " → ".join([part["segments"][0]["origin"]] + [seg["destination"] for seg in part["segments"]])
                lines.append(f"Outbound {route(out)}: departs {out['departing_at'][:16].replace('T', ' ')}. "
                    f"Return {route(back)}: arrives home {back['arriving_at'][:16].replace('T', ' ')}.")
        if self.provider.label.startswith("LIVE") or self.provider.label.startswith("SANDBOX"):
            lines.append("One fare per distinct itinerary is shown; other fare conditions may differ. Ask for details of an option.")
        lines.append("Times local to each airport. Prices may change; nothing booked. Try ‘nonstop only’, ‘under $900’, or ‘why option 2?’.")
        return "\n".join(lines)
