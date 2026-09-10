from __future__ import annotations

import re
from decimal import Decimal

from .conversation import Agent
from .providers import eligible
from .ranking import recommend_offer, recommendation_reason


class AdvancedAgent(Agent):
    def reply(self, session, text):
        state = self.store.load(session) or self.initial()
        if state.get("context") != self.context:
            state = self.initial()
        if state.get("provider") != self.provider.label:
            state["offers"], state["history"] = [], []
            state["provider"] = self.provider.label

        low = text.lower().strip()

        if re.search(r"\b(what do you know about my trip|summarize my trip|what are my preferences|what filters|current filters|my trip details)\b", low):
            response = self.trip_summary(state)
            return self._save_direct_reply(session, state, text, response)

        if re.search(r"\b(when do i need to arrive|when should i arrive|when can i fly back|when can i return|what are my dates|what dates do i need)\b", low):
            response = self.trip_dates()
            return self._save_direct_reply(session, state, text, response)

        if re.search(r"\b(where am i going|what airport am i flying to|what is my destination|which clinic)\b", low):
            response = self.trip_destination()
            return self._save_direct_reply(session, state, text, response)

        if re.search(r"\b(recommend|best option|best one|which would you|which should i|what would you pick|what should i pick|what's best|whats best)\b", low):
            response = self.recommend(state)
            return self._save_direct_reply(session, state, text, response)

        if re.search(r"\b(compare|difference between|versus|vs\.?)(?:\s+options?)?\b", low):
            response = self.compare(state, text)
            return self._save_direct_reply(session, state, text, response)

        return super().reply(session, text)

    def _save_direct_reply(self, session, state, text, response):
        state["history"] = (state.get("history", []) + [
            {"role": "user", "text": text},
            {"role": "assistant", "text": response},
        ])[-12:]
        self.store.save(session, state)
        return response

    def trip_summary(self, state):
        preferences = state["preferences"]
        origin = preferences["origin"] or "not set yet"
        budget = "no budget cap" if preferences["budget"] is None else f"${preferences['budget']:,.0f} total budget"
        stops = "any number of stops" if preferences["max_stops"] is None else f"up to {preferences['max_stops']} stop(s) each way"
        return (
            f"Clinic: {self.context['clinic']} via {self.context['destination']}. "
            f"Current search: {origin} → {self.context['destination']}, depart {preferences['outbound_date']}, "
            f"return {preferences['return_date']}, {preferences['adults']} adult(s), {budget}, {stops}, "
            f"ranked by {preferences['sort']}."
        )

    def trip_dates(self):
        return (
            f"Your clinic context says to arrive by {self.context['arrival_deadline']} and not fly back before "
            f"{self.context['return_not_before']}. I’m using those as fixed scheduling constraints for flight search."
        )

    def trip_destination(self):
        return (
            f"You’re traveling to {self.context['clinic']} via {self.context['destination']}. "
            "That clinic and destination are fixed in this prototype."
        )

    def current_offers(self, state):
        offers = []
        for offer in state.get("offers", []):
            if eligible(offer, state["preferences"], self.context):
                offers.append(offer)
        if len(offers) != len(state.get("offers", [])):
            state["offers"] = offers
        return offers

    def recommend(self, state):
        offers = self.current_offers(state)
        if not offers:
            return "I need a current shortlist first. Ask me to find flights, then I can recommend one."

        choice = recommend_offer(offers)
        index = offers.index(choice) + 1
        reason = recommendation_reason(choice, offers)
        return (
            f"I’d pick option {index}: {choice['airline']} at ${Decimal(choice['amount']):,.2f} total. "
            f"Among the current options, {reason}. Nothing is booked."
        )

    def compare(self, state, text):
        offers = self.current_offers(state)
        if len(offers) < 2:
            return "I need at least two current flight options before I can compare them."

        numbers = [int(x) for x in re.findall(r"\b([1-3])\b", text)]
        if len(numbers) >= 2:
            indexes = []
            for number in numbers:
                if 1 <= number <= len(offers) and number not in indexes:
                    indexes.append(number)
            if len(indexes) < 2:
                return "Tell me two displayed option numbers to compare, like ‘compare 1 and 2’."
        else:
            indexes = list(range(1, min(len(offers), 3) + 1))

        lines = ["Here’s the quick comparison:"]
        for index in indexes:
            offer = offers[index - 1]
            duration = offer.get("duration_minutes")
            hours = f"{duration // 60}h {duration % 60}m" if duration else "duration unavailable"
            lines.append(
                f"{index}. {offer['airline']}: ${Decimal(offer['amount']):,.2f} total, "
                f"{offer.get('stops', 0)} stop(s) max each way, {hours} outbound."
            )
        lines.append("I can also tell you which one I’d recommend.")
        return "\n".join(lines)
