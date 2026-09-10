import copy
import unittest
from essos_travel.config import sample_context
from essos_travel.providers import MockFlights, DuffelFlights, rejection_reason, distinct_itineraries, flight_details


class OfferDetailsTests(unittest.TestCase):
    def setUp(self):
        self.context = sample_context()
        self.prefs = {'origin': 'ORD', 'outbound_date': self.context['outbound_date'],
                      'return_date': self.context['return_date'], 'adults': 1,
                      'max_stops': None, 'budget': None}
        self.offer = MockFlights().search(self.prefs, self.context)[0]

    def test_reasons_match_constraints(self):
        self.assertIsNone(rejection_reason(self.offer, self.prefs, self.context))
        self.assertEqual(rejection_reason(self.offer, self.prefs | {'budget': 1}, self.context), 'over_budget')
        self.assertEqual(rejection_reason(self.offer, self.prefs | {'max_stops': 0}, self.context), 'too_many_stops')
        bad = copy.deepcopy(self.offer)
        bad['slices'][0]['arriving_at'] = self.context['arrival_deadline'][:10] + 'T23:00:00'
        self.assertEqual(rejection_reason(bad, self.prefs, self.context), 'arrives_after_clinic_deadline')
        bad['slices'][0]['origin'] = 'JFK'
        self.assertEqual(rejection_reason(bad, self.prefs, self.context), 'route_mismatch')

    def test_preserves_segments_and_fare_details(self):
        raw = {'id': 'offer', 'total_amount': '900', 'total_currency': 'USD',
               'expires_at': self.offer['expires_at'], 'conditions': {'refund_before_departure': None}, 'slices': []}
        for part in self.offer['slices']:
            raw['slices'].append({'duration': 'PT15H', 'segments': [{
                'origin': {'iata_code': part['origin'], 'time_zone': 'America/Chicago'},
                'destination': {'iata_code': part['destination'], 'time_zone': part['arrival_timezone']},
                'departing_at': part['departing_at'], 'arriving_at': part['arriving_at'],
                'operating_carrier': {'name': 'Example', 'iata_code': 'XX'},
                'marketing_carrier': {'name': 'Example', 'iata_code': 'XX'},
                'operating_carrier_flight_number': '123',
                'passengers': [{'id': 'excluded-passenger-id', 'cabin_class': 'economy', 'baggages': [{'type': 'checked', 'quantity': 1}]}]}]})
        normalized = DuffelFlights.normalize(raw)
        segment = normalized['slices'][0]['segments'][0]
        self.assertEqual(segment['operating_flight_number'], '123')
        self.assertEqual(segment['passenger_fares'][0]['baggages'][0]['quantity'], 1)
        self.assertNotIn('id', segment['passenger_fares'][0])
        self.assertIn('123', flight_details(normalized))
        variant = copy.deepcopy(normalized)
        variant.update(id='another-fare', amount='1000')
        self.assertEqual(len(distinct_itineraries([normalized, variant])), 1)
        variant['slices'][0]['segments'][0]['operating_flight_number'] = '456'
        self.assertEqual(len(distinct_itineraries([normalized, variant])), 2)

    def test_missing_segment_details_are_not_merged(self):
        variant = copy.deepcopy(self.offer)
        variant['id'] = 'different-offer'
        self.assertEqual(len(distinct_itineraries([self.offer, variant])), 2)
