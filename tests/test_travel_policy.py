import unittest
from datetime import datetime, timedelta
from essos_travel.config import sample_context
from essos_travel.travel_policy import apply_policy, boundaries
from essos_travel.providers import MockFlights, rejection_reason

class TravelPolicyTests(unittest.TestCase):
    def test_unknown_time_is_conservative(self):
        context=sample_context()
        context['procedure_date']='2026-10-15'
        arrival, returning=boundaries(context)
        self.assertEqual(arrival.isoformat(),'2026-10-08T00:00:00+03:00')
        self.assertEqual(returning.isoformat(),'2026-10-17T00:00:00+03:00')
    def test_exact_time_boundaries(self):
        context=sample_context()
        context.update(procedure_date='2026-10-15',procedure_at='2026-10-15T15:00:00+03:00')
        context=apply_policy(context)
        prefs={'origin':'ORD','outbound_date':'2026-10-07','return_date':'2026-10-16','adults':1,'max_stops':None,'budget':None}
        offer=MockFlights().search(prefs,context)[0]
        out,back=offer['slices']
        out['arriving_at']='2026-10-08T12:00:00+00:00'
        back['departing_at']='2026-10-16T12:00:00+00:00'
        self.assertIsNone(rejection_reason(offer,prefs,context))
        out['arriving_at']='2026-10-08T12:00:01+00:00'
        self.assertEqual(rejection_reason(offer,prefs,context),'arrives_after_clinic_deadline')
        out['arriving_at']='2026-10-08T12:00:00+00:00'
        back['departing_at']='2026-10-16T11:59:59+00:00'
        self.assertEqual(rejection_reason(offer,prefs,context),'return_before_permitted_date')
    def test_old_defaults_migrate_without_mutating_input(self):
        old=sample_context()
        old['outbound_date']=old['procedure_date']
        old['return_date']=old['procedure_date']
        new=apply_policy(old)
        self.assertLess(new['outbound_date'],new['arrival_deadline'][:10])
        self.assertGreater(new['return_date'],old['procedure_date'])
        self.assertEqual(old['outbound_date'],old['procedure_date'])
