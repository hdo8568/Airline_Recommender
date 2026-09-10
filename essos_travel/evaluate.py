"""One search evaluation; no booking or messaging side effects."""
from collections import Counter
import getpass
import json
import time
from datetime import datetime, timezone
from decimal import Decimal

from .config import LOCAL, load_context, settings, write_private
from .providers import DuffelFlights, ServiceError, eligible, request_json, rejection_reason, distinct_itineraries


def evaluate(token, context, http=request_json, *, origin="ORD", adults=1):
    provider = DuffelFlights(token, http)
    preferences = {
        'origin': origin, 'outbound_date': context['outbound_date'],
        'return_date': context['return_date'], 'adults': adults,
        'max_stops': None, 'budget': None, 'sort': 'cheapest',
    }
    report = {
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'live' if provider.live else 'sandbox',
        'request': preferences | {'destination': context['destination']},
        'clinic_arrival_deadline': context['arrival_deadline'],
        'clinic_return_not_before': context['return_not_before'],
        'limitations': ['One search cannot establish complete airline coverage or typical latency.',
                        'Prices and availability may change; nothing booked.',
                        'Fare fields are retained as supplied; missing information remains unknown.'],
    }
    def observed_http(url, headers, body):
        response = http(url, headers, body)
        data = response.get('data', {}) if isinstance(response, dict) else {}
        raw = data.get('offers') if isinstance(data, dict) else None
        if isinstance(raw, list):
            report['offers_received'] = len(raw)
        return response
    provider.http = observed_http
    started = time.monotonic()
    try:
        offers = provider.search(preferences, context)
        rejected = [{'id': o['id'], 'reason': reason} for o in offers if (reason := rejection_reason(o, preferences, context))]
        valid = [o for o in offers if eligible(o, preferences, context)]
        valid.sort(key=lambda o: Decimal(o['amount']))
        report.update(status='success', offers_normalized=len(offers),
                      offers_eligible=len(valid), offers_rejected_by_checks=len(offers)-len(valid),
                      offers_rejected_during_normalization=report.get('offers_received', len(offers))-len(offers),
                      airlines_returned=sorted({o['airline'] for o in offers}),
                      offers=offers, shortlist=distinct_itineraries(valid)[:3],
                      distinct_eligible_itineraries=len(distinct_itineraries(valid)),
                      rejection_counts=dict(Counter(r['reason'] for r in rejected)), rejected_offers=rejected)
        report['filter_note'] = 'Each rejected offer is counted once under its first failed check. Fare variants are grouped only for display; all normalized offers are retained.'
    except ServiceError as exc:
        report.update(status='failed', error=str(exc))
    report['elapsed_seconds'] = round(time.monotonic()-started, 2)
    return report


def main():
    config = settings()
    token = config.get('DUFFEL_ACCESS_TOKEN')
    if not token:
        print('Paste your Duffel access token. Typing is hidden; press Enter when done.')
        token = getpass.getpass('Duffel token: ').strip()
        DuffelFlights(token)  # Validate before saving; makes no request.
        config['DUFFEL_ACCESS_TOKEN'] = token
        write_private(LOCAL / 'settings.json', config)
    context = load_context()
    print(f"One search: ORD → {context['destination']}, {context['outbound_date']} to {context['return_date']}, 1 adult, economy, no budget/stops cap.", flush=True)
    print('LIVE data' if token.startswith('duffel_live_') else 'SANDBOX data — not live availability', flush=True)
    report = evaluate(token, context)
    path = LOCAL / 'duffel-evaluation.json'
    write_private(path, report)
    summary = {k: v for k, v in report.items() if k not in ('offers', 'shortlist', 'rejected_offers')}
    print(json.dumps(summary, indent=2))
    for offer in report.get('shortlist', []):
        print(f"{offer['airline']}: {offer['amount']} {offer['currency']}; up to {offer['stops']} stops each way; expires {offer['expires_at']}")
    print(f'Report saved: {path}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, EOFError) as exc:
        print(f'Setup: {exc}')
        raise SystemExit(1)
