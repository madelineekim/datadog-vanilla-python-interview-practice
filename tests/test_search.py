import unittest

from pulse.errors import APIError
from pulse.events import search_events, submit_events
from pulse.services import create_service
from pulse.state import State


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.state = State(clock=lambda: '2026-01-01T12:00:00Z')
        create_service(self.state, {'name': 'Checkout', 'tags': ['web']})
        create_service(self.state, {'name': 'Worker', 'tags': ['jobs']})
        for service, status, message in [('1', 'critical', 'Upstream timeout'),
                                         ('2', 'warning', 'Queue TIMEOUT'),
                                         ('1', 'ok', 'Recovered')]:
            submit_events(self.state, service, {'events': [
                {'status': status, 'latency_ms': 10, 'message': message}]})

    def test_case_insensitive_search_across_services(self):
        result = search_events(self.state, {'q': [' TIMEOUT ']})
        self.assertEqual([item['id'] for item in result['items']], ['2', '1'])
        self.assertEqual(result['items'][0]['service_name'], 'Worker')
        self.assertEqual(result['total'], 2)

    def test_status_and_tag_filters(self):
        result = search_events(self.state, {'q': ['timeout'], 'status': ['critical'], 'tag': ['WEB']})
        self.assertEqual([item['id'] for item in result['items']], ['1'])

    def test_pagination(self):
        result = search_events(self.state, {'q': ['timeout'], 'offset': ['1'], 'limit': ['1']})
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['total'], 2)
        self.assertEqual((result['offset'], result['limit']), (1, 1))

    def test_no_matches(self):
        result = search_events(self.state, {'q': ['unrecognized']})
        self.assertEqual(result['items'], [])
        self.assertEqual(result['total'], 0)

    def test_invalid_query_and_pagination(self):
        for values in [{}, {'q': [' ']}, {'q': ['a' * 101]}, {'q': ['a'], 'limit': ['0']},
                       {'q': ['a', 'b']}, {'q': ['a'], 'other': ['b']}]:
            with self.subTest(values=values), self.assertRaises(APIError):
                search_events(self.state, values)
