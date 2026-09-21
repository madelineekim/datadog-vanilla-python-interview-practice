import unittest

from pulse.errors import APIError
from pulse.services import create_service, get_service, list_services, update_service
from pulse.state import State


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.state = State(clock=lambda: '2026-01-01T00:00:00Z')

    def test_create_normalizes_tags_and_returns_copy(self):
        result = create_service(self.state, {'name': ' Checkout ', 'tags': ['WEB', 'web']})
        self.assertEqual(result['name'], 'Checkout')
        self.assertEqual(result['tags'], ['web'])
        self.assertEqual(self.state.tags, {'web'})
        result['tags'].append('other')
        self.assertEqual(self.state.services['1']['tags'], {'web'})

    def test_duplicate_name_and_rename(self):
        create_service(self.state, {'name': 'Checkout'})
        with self.assertRaises(APIError) as error:
            create_service(self.state, {'name': 'checkout'})
        self.assertEqual(error.exception.status, 409)
        update_service(self.state, '1', {'name': 'Orders'})
        create_service(self.state, {'name': 'Checkout'})
        self.assertEqual(self.state.service_names, {'orders': '1', 'checkout': '2'})

    def test_failed_patch_does_not_partially_mutate(self):
        create_service(self.state, {'name': 'Checkout', 'tags': ['web']})
        with self.assertRaises(APIError):
            update_service(self.state, '1', {'name': 'Orders', 'tags': [False]})
        self.assertEqual(get_service(self.state, '1')['name'], 'Checkout')
        self.assertEqual(self.state.service_names, {'checkout': '1'})
        self.assertEqual(self.state.tags, {'web'})

    def test_tag_catalog_preserves_shared_tags(self):
        create_service(self.state, {'name': 'A', 'tags': ['web', 'old']})
        create_service(self.state, {'name': 'B', 'tags': ['web']})
        update_service(self.state, '1', {'tags': ['new']})
        self.assertEqual(self.state.tags, {'new', 'web'})

    def test_filter_before_pagination_and_exact_membership(self):
        for name, tags in [('A', ['web']), ('B', []), ('C', ['web']), ('D', ['web'])]:
            create_service(self.state, {'name': name, 'tags': tags})
        result = list_services(self.state, {'tag': ['WEB'], 'offset': ['1'], 'limit': ['1']})
        self.assertEqual([s['name'] for s in result['items']], ['C'])
        self.assertEqual(result['total'], 3)

    def test_invalid_create_leaves_ids_untouched(self):
        for body in [{}, [], {'name': ''}, {'name': 'A', 'extra': 1},
                     {'name': 'A', 'tags': 'web'}, {'name': 'A', 'description': 2}]:
            with self.subTest(body=body), self.assertRaises(APIError):
                create_service(self.state, body)
        self.assertEqual(self.state.services, {})
        self.assertEqual(self.state.next_service_id, 1)

    def test_empty_patch_and_conflicting_rename(self):
        create_service(self.state, {'name': 'A'})
        create_service(self.state, {'name': 'B'})
        for body in [{}, {'name': 'B'}]:
            with self.subTest(body=body), self.assertRaises(APIError):
                update_service(self.state, '1', body)
        self.assertEqual(get_service(self.state, '1')['name'], 'A')

    def test_fresh_state_is_empty(self):
        create_service(self.state, {'name': 'A'})
        self.assertEqual(list_services(State(), {})['total'], 0)

    def test_query_validation(self):
        for query in [{'offset': ['-1']}, {'limit': ['0']}, {'limit': ['101']},
                      {'limit': ['a']}, {'tag': ['']}, {'x': ['1']},
                      {'limit': ['1', '2']}, {'offset': ['9' * 100]}]:
            with self.subTest(query=query), self.assertRaises(APIError):
                list_services(self.state, query)
