import unittest

from pulse.errors import APIError
from pulse.events import health_overview, list_events, submit_events, summary
from pulse.services import create_service
from pulse.state import State


class EventTests(unittest.TestCase):
    def setUp(self):
        self.state = State(clock=lambda: '2026-01-01T12:00:00Z')
        create_service(self.state, {'name': 'A'})
        create_service(self.state, {'name': 'B'})

    def submit(self, status='ok', latency=20, service='1'):
        return submit_events(self.state, service, {'events': [{'status': status, 'latency_ms': latency}]})

    def test_batch_is_atomic(self):
        with self.assertRaises(APIError):
            submit_events(self.state, '1', {'events': [
                {'status': 'ok', 'latency_ms': 1}, {'status': 'bad', 'latency_ms': 2}]})
        self.assertEqual(self.state.events, [])
        self.assertEqual(self.state.next_event_id, 1)

    def test_batch_ids_and_copies(self):
        body = {'events': [{'status': 'ok', 'latency_ms': 0, 'metadata': {'region': 'eu'}}]}
        result = submit_events(self.state, '1', body)
        body['events'][0]['metadata']['region'] = 'us'
        result['items'][0]['metadata']['region'] = 'ap'
        self.assertEqual(self.state.events[0]['metadata'], {'region': 'eu'})
        self.assertEqual(self.submit()['items'][0]['id'], '2')
        fetched = list_events(self.state, '1', {})
        fetched['items'][0]['metadata']['region'] = 'changed'
        self.assertEqual(self.state.events[0]['metadata'], {'region': 'eu'})

    def test_filter_offset_and_service_isolation(self):
        self.submit('critical')
        self.submit('ok')
        self.submit('critical', service='2')
        self.submit('critical')
        result = list_events(self.state, '1', {'status': ['critical'], 'offset': ['1'], 'limit': ['1']})
        self.assertEqual([e['id'] for e in result['items']], ['4'])
        self.assertEqual(result['total'], 2)
        self.assertEqual(list_events(self.state, '1', {'offset': ['99']})['items'], [])

    def test_since_inclusive_and_timezone(self):
        self.submit()
        self.state.clock = lambda: '2026-01-01T13:00:00Z'
        self.submit('warning')
        result = list_events(self.state, '1', {'since': ['2026-01-01T14:00:00+01:00']})
        self.assertEqual([e['id'] for e in result['items']], ['2'])

    def test_summary_uses_all_matching_events(self):
        self.submit('ok', 10)
        self.submit('critical', 30)
        self.submit('warning', 100, service='2')
        result = summary(self.state, '1', {})
        self.assertEqual(result, {'service_id': '1', 'event_count': 2,
                                 'counts': {'ok': 1, 'warning': 0, 'critical': 1},
                                 'average_latency_ms': 20.0, 'latest_status': 'critical'})

    def test_empty_summary(self):
        result = summary(self.state, '1', {})
        self.assertEqual(result['latest_status'], 'unknown')
        self.assertIsNone(result['average_latency_ms'])
        self.assertEqual(result['event_count'], 0)

    def test_batch_boundaries(self):
        item = {'status': 'ok', 'latency_ms': 600000}
        self.assertEqual(submit_events(self.state, '1', {'events': [item] * 50})['accepted'], 50)
        for batch in [[], [item] * 51, 'bad']:
            with self.subTest(batch_size=len(batch)), self.assertRaises(APIError):
                submit_events(self.state, '1', {'events': batch})
        self.assertEqual(len(self.state.events), 50)

    def test_invalid_event_fields(self):
        for overrides in [{'latency_ms': True}, {'latency_ms': -1}, {'latency_ms': float('nan')},
                          {'latency_ms': float('inf')}, {'metadata': []},
                          {'metadata': {'x': 4}}, {'status': []}, {'message': 4}]:
            with self.subTest(overrides=overrides), self.assertRaises(APIError):
                submit_events(self.state, '1', {'events': [dict(status='ok', latency_ms=1) | overrides]})
        self.assertEqual(self.state.events, [])

    def test_missing_service(self):
        for operation in [lambda: self.submit(service='99'),
                          lambda: list_events(self.state, '99', {}),
                          lambda: summary(self.state, '99', {})]:
            with self.assertRaises(APIError) as error:
                operation()
            self.assertEqual(error.exception.status, 404)

    def test_invalid_filters(self):
        for query in [{'since': ['2026-01-01']}, {'since': ['bad']},
                      {'status': ['bad']}, {'status': ['ok', 'critical']}]:
            with self.subTest(query=query), self.assertRaises(APIError):
                list_events(self.state, '1', query)

    def test_overview_latest_status_and_unknown(self):
        self.submit('critical')
        self.submit('ok')
        result = health_overview(self.state, {})
        self.assertEqual(result['counts'], {'ok': 1, 'warning': 0, 'critical': 0, 'unknown': 1})
        self.assertEqual(result['items'][0]['event_count'], 2)
        self.assertEqual(result['items'][1]['status'], 'unknown')
        self.assertIsNone(result['items'][1]['last_received_at'])
        self.assertEqual(health_overview(self.state, {'tag': ['missing']})['service_count'], 0)
