import json
from urllib.parse import parse_qs, unquote, urlsplit

from pulse.errors import APIError

MAX_BODY = 65536


def parse_target(target):
    parsed = urlsplit(target)
    parts = [unquote(part) for part in parsed.path.split('/')[1:]]
    return parts, parse_qs(parsed.query, keep_blank_values=True)


def reject_constant(value):
    raise ValueError('Invalid JSON number')


def read_json(handler):
    if handler.headers.get('Transfer-Encoding'):
        raise APIError(400, 'Transfer-Encoding is not supported')
    content_type = handler.headers.get('Content-Type', '').split(';')[0].strip().lower()
    if content_type != 'application/json':
        raise APIError(415, 'Content-Type must be application/json')
    lengths = handler.headers.get_all('Content-Length', [])
    if len(lengths) != 1:
        raise APIError(400, 'Supply one Content-Length header')
    try:
        length = int(lengths[0])
    except ValueError:
        raise APIError(400, 'Invalid Content-Length')
    if length < 1:
        raise APIError(400, 'A JSON body is required')
    if length > MAX_BODY:
        raise APIError(413, 'Request body is too large')
    try:
        raw = handler.rfile.read(length)
        if len(raw) != length:
            raise APIError(400, 'Incomplete request body')
        return json.loads(raw.decode('utf-8'), parse_constant=reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise APIError(400, 'Malformed JSON')


def send_bytes(handler, status, body, content_type, headers=None):
    handler.send_response(status)
    handler.send_header('Content-Type', content_type)
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    for key, value in (headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()
    handler.wfile.write(body)


def send_json(handler, status, body, headers=None):
    encoded = json.dumps(body, allow_nan=False).encode('utf-8')
    send_bytes(handler, status, encoded, 'application/json; charset=utf-8', headers)
