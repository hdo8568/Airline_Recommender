from __future__ import annotations

import re
from decimal import Decimal

from .conversation import Agent
from .providers import eligible
from .ranking import recommend_offer, recommendation_reason


class AdvancedAgent(Agent):
    def reply(self, session, text):
        state = self.store.load(session) or self.initial()
        low = text.lower().strip()

        if re.search(r"\b(recommend|best option|best one|which one|which would you|which should i|what would you pick)\b", low):
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
