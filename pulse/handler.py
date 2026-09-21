import logging
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from pulse import events, services
from pulse.errors import APIError
from pulse.http_helpers import parse_target, read_json, send_bytes, send_json
from pulse.validation import query

STATIC = Path(__file__).resolve().parent.parent / 'static'
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def do_PATCH(self):
        self.dispatch()

    def do_DELETE(self):
        self.dispatch()

    def dispatch(self):
        try:
            path = self.path.split('?', 1)[0]
            if path in ASSETS:
                self.require_method(('GET',))
                filename, content_type = ASSETS[path]
                send_bytes(self, 200, (STATIC / filename).read_bytes(), content_type)
                return
            status, body, headers = self.route()
            send_json(self, status, body, headers)
        except APIError as error:
            headers = {'Allow': self.allowed_methods} if error.status == 405 else None
            send_json(self, error.status, {'error': error.message}, headers)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except Exception:
            logging.exception('Unexpected request failure')
            send_json(self, 500, {'error': 'Internal server error'})

    def require_method(self, allowed):
        if self.command not in allowed:
            self.allowed_methods = ', '.join(allowed)
            raise APIError(405, 'Method not allowed')

    def route(self):
        parts, values = parse_target(self.path)
        state = self.server.state
        if parts == ['api', 'services']:
            self.require_method(('GET', 'POST'))
            if self.command == 'GET':
                return 200, services.list_services(state, values), {}
            query(values, ())
            created = services.create_service(state, read_json(self))
            return 201, created, {'Location': '/api/services/' + created['id']}
        if parts == ['api', 'events', 'search']:
            self.require_method(('GET',))
            return 200, events.search_events(state, values), {}
        if parts == ['api', 'overview']:
            self.require_method(('GET',))
            return 200, events.health_overview(state, values), {}
        if parts == ['api', 'tags']:
            self.require_method(('GET',))
            query(values, ())
            return 200, {'items': sorted(state.tags)}, {}
        if len(parts) in (3, 4) and parts[:2] == ['api', 'services']:
            service_id = parts[2]
            if not service_id.isascii() or not service_id.isdecimal():
                raise APIError(404, 'Service not found')
            if len(parts) == 3:
                self.require_method(('GET', 'PATCH'))
                query(values, ())
                if self.command == 'GET':
                    return 200, services.get_service(state, service_id), {}
                return 200, services.update_service(state, service_id, read_json(self)), {}
            if parts[3] == 'events':
                self.require_method(('GET', 'POST'))
                if self.command == 'GET':
                    return 200, events.list_events(state, service_id, values), {}
                query(values, ())
                return 201, events.submit_events(state, service_id, read_json(self)), {}
            if parts[3] == 'summary':
                self.require_method(('GET',))
                return 200, events.summary(state, service_id, values), {}
        raise APIError(404, 'Route not found')
