from __future__ import annotations

from decimal import Decimal


def recommend_offer(offers):
    if not offers:
        return None

    prices = [Decimal(o["amount"]) for o in offers]
    durations = [o.get("duration_minutes") or 10**9 for o in offers]
    stops = [o.get("stops", 0) for o in offers]

    min_price, max_price = min(prices), max(prices)
    min_duration, max_duration = min(durations), max(durations)
    min_stops, max_stops = min(stops), max(stops)

    def normalize(value, low, high):
        if high == low:
            return 0.0
        return float((value - low) / (high - low))

    scored = []
    for offer in offers:
        price_score = normalize(Decimal(offer["amount"]), min_price, max_price)
        duration_score = normalize(offer.get("duration_minutes") or 10**9, min_duration, max_duration)
        stop_score = normalize(offer.get("stops", 0), min_stops, max_stops)
        score = 0.5 * price_score + 0.3 * duration_score + 0.2 * stop_score
        scored.append((score, offer))

    scored.sort(key=lambda item: item[0])
    return scored[0][1]


def recommendation_reason(offer, offers):
    if not offer:
        return "I need a current flight shortlist before I can recommend one."

    cheapest = min(Decimal(o["amount"]) for o in offers)
    fastest = min((o.get("duration_minutes") or 10**9) for o in offers)
    fewest_stops = min(o.get("stops", 0) for o in offers)

    reasons = []
    if Decimal(offer["amount"]) == cheapest:
        reasons.append("it is the cheapest option")
    if (offer.get("duration_minutes") or 10**9) == fastest:
        reasons.append("it has the shortest outbound travel time")
    if offer.get("stops", 0) == fewest_stops:
        reasons.append("it has the fewest stops")

    if not reasons:
        reasons.append("it gives the best balance of price, travel time, and stops")
    elif len(reasons) == 1:
        reasons.append("it still compares well on travel time and stops")

    return reasons[0] + " and " + reasons[1] if len(reasons) > 1 else reasons[0]
