"""User-specified demo scheduling rules; these are not medical advice."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def boundaries(context):
    zone = ZoneInfo(context['timezone'])
    if context.get('procedure_at'):
        procedure = datetime.fromisoformat(context['procedure_at'])
        if procedure.tzinfo is None:
            raise ValueError('Procedure time must include a timezone offset.')
        if procedure.astimezone(zone).date().isoformat() != context['procedure_date']:
            raise ValueError('Procedure timestamp and date disagree.')
        instant = procedure.astimezone(timezone.utc)
        return ((instant-timedelta(days=7)).astimezone(zone),
                (instant+timedelta(hours=24)).astimezone(zone))
    start = datetime.combine(date.fromisoformat(context['procedure_date']), time.min, zone)
    # Unknown time: use start of day for arrival and end of day for return.
    return ((start.astimezone(timezone.utc)-timedelta(days=7)).astimezone(zone),
            ((start+timedelta(days=1)).astimezone(timezone.utc)+timedelta(hours=24)).astimezone(zone))


def apply_policy(context):
    result = dict(context)
    arrival, returning = boundaries(result)
    result.update(arrival_deadline=arrival.isoformat(), return_not_before=returning.date().isoformat(),
                  return_not_before_at=returning.isoformat(), travel_policy_version=2)
    if result['outbound_date'] >= arrival.date().isoformat():
        result['outbound_date'] = (arrival.date()-timedelta(days=2)).isoformat()
    if result['return_date'] < returning.date().isoformat():
        result['return_date'] = returning.date().isoformat()
    result['policy_note'] = ('Demo rule: arrive at least 7 days before the procedure; depart home at least 24 hours after. '
        'If procedure time is unknown, use the start of its day for arrival and end of its day for return. Not medical advice.')
    return result
