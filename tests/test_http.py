import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import create_server


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01})
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()

    def request(self, path, method='GET', body=None, raw=None, content_type='application/json'):
        data = json.dumps(body).encode() if body is not None else raw
        request = Request(self.base + path, data=data, method=method,
                          headers={'Content-Type': content_type} if data is not None else {})
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            payload = response.read()
            result = json.loads(payload) if 'application/json' in response.headers['Content-Type'] else payload
            return response.status, result, response.headers

    def create(self, name='Checkout'):
        status, body, headers = self.request('/api/services', 'POST', {'name': name})
        self.assertEqual(status, 201)
        self.assertEqual(headers['Location'], '/api/services/' + body['id'])
        return body['id']

    def test_full_lifecycle_across_requests(self):
        service = self.create()
        path = '/api/services/' + service
        self.assertEqual(self.request(path)[1]['name'], 'Checkout')
        self.assertEqual(self.request(path, 'PATCH', {'tags': ['web', 'WEB']})[0], 200)
        self.assertEqual(self.request('/api/tags')[1], {'items': ['web']})
        status, result, _ = self.request(path + '/events', 'POST', {'events': [
            {'status': 'critical', 'latency_ms': 12, 'metadata': {'region': 'eu'}}]})
        self.assertEqual((status, result['accepted']), (201, 1))
        self.assertEqual(self.request(path + '/events?status=critical')[1]['total'], 1)
        self.assertEqual(self.request(path + '/summary')[1]['latest_status'], 'critical')
        self.assertEqual(len(self.server.state.events), 1)

    def test_malformed_and_non_object_json(self):
        for raw in [b'{', b'null', b'[]', b'{"name": NaN}', b'\xff']:
            with self.subTest(raw=raw):
                status, body, _ = self.request('/api/services', 'POST', raw=raw)
                self.assertEqual(status, 400)
                self.assertIn('error', body)
        self.assertEqual(self.server.state.services, {})

    def test_headers_and_size(self):
        self.assertEqual(self.request('/api/services', 'POST', raw=b'{}', content_type='text/plain')[0], 415)
        self.assertEqual(self.request('/api/services', 'POST', raw=b' ' * 65537)[0], 413)
        self.assertEqual(self.request('/api/services', 'POST', raw=b'')[0], 400)

    def test_routes_methods_and_conflicts(self):
        self.create()
        self.assertEqual(self.request('/api/services', 'POST', {'name': 'CHECKOUT'})[0], 409)
        for path in ['/api/services/999', '/api/services/1/unknown', '/api/services/1/events/extra', '/missing']:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)
        status, _, headers = self.request('/api/services/1', 'DELETE')
        self.assertEqual(status, 405)
        self.assertEqual(headers['Allow'], 'GET, PATCH')

    def test_query_errors_and_empty_collection(self):
        self.assertEqual(self.request('/api/services')[1]['items'], [])
        for suffix in ['limit=0', 'offset=-1', 'limit=1&limit=2', 'unknown=x']:
            with self.subTest(suffix=suffix):
                self.assertEqual(self.request('/api/services?' + suffix)[0], 400)

    def test_static_assets_and_allowlist(self):
        for path, content_type in [('/', 'text/html'), ('/app.js', 'text/javascript'), ('/style.css', 'text/css')]:
            status, body, headers = self.request(path)
            self.assertEqual(status, 200)
            self.assertIn(content_type, headers['Content-Type'])
            self.assertGreater(len(body), 0)
        self.assertEqual(self.request('/server.py')[0], 404)
        self.assertEqual(self.request('/../server.py')[0], 404)

    def test_unexpected_error_has_generic_response(self):
        with patch('pulse.handler.services.list_services', side_effect=RuntimeError('private detail')):
            with self.assertLogs(level='ERROR'):
                status, body, _ = self.request('/api/services')
        self.assertEqual(status, 500)
        self.assertEqual(body, {'error': 'Internal server error'})

    def test_new_server_has_fresh_state(self):
        self.create()
        other = create_server(port=0)
        try:
            self.assertEqual(other.state.services, {})
            self.assertIsNot(other.state, self.server.state)
        finally:
            other.server_close()
