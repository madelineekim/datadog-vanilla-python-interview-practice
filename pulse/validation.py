import math
from datetime import datetime, timezone

from pulse.errors import APIError

STATUSES = ('ok', 'warning', 'critical')


def fields(value, allowed, required=()):
    if not isinstance(value, dict):
        raise APIError(400, 'Expected a JSON object')
    unknown = set(value) - set(allowed)
    missing = set(required) - set(value)
    if unknown:
        raise APIError(400, 'Unknown fields: ' + ', '.join(sorted(unknown)))
    if missing:
        raise APIError(400, 'Missing fields: ' + ', '.join(sorted(missing)))
    return value


def text(value, name, maximum=120):
    if not isinstance(value, str) or not value.strip():
        raise APIError(400, name + ' must be a nonempty string')
    value = value.strip()
    if len(value) > maximum:
        raise APIError(400, name + ' is too long')
    return value


def tags(value):
    if not isinstance(value, list) or len(value) > 20:
        raise APIError(400, 'tags must be a list of at most 20 strings')
    return {text(item, 'tag', 32).lower() for item in value}


def status(value):
    if not isinstance(value, str) or value not in STATUSES:
        raise APIError(400, 'status must be ok, warning, or critical')
    return value


def timestamp(value, name='since'):
    if not isinstance(value, str):
        raise APIError(400, name + ' must be an ISO 8601 timestamp')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise APIError(400, name + ' must include a valid date, time and timezone')


def integer(value, name, minimum, maximum):
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise APIError(400, name + ' must be an integer')
    if len(value) > 10:
        raise APIError(400, name + ' is out of range')
    number = int(value)
    if not minimum <= number <= maximum:
        raise APIError(400, name + ' is out of range')
    return number


def query(values, allowed):
    if set(values) - set(allowed):
        raise APIError(400, 'Unknown query parameter')
    if any(len(items) != 1 for items in values.values()):
        raise APIError(400, 'Query parameters must not be repeated')
    return {key: items[0] for key, items in values.items()}


def pagination(values):
    return (integer(values.get('offset', '0'), 'offset', 0, 1000000),
            integer(values.get('limit', '20'), 'limit', 1, 100))


def event(value):
    fields(value, ('status', 'latency_ms', 'message', 'metadata'), ('status', 'latency_ms'))
    latency = value['latency_ms']
    if (isinstance(latency, bool) or not isinstance(latency, (int, float))
            or not 0 <= latency <= 600000 or not math.isfinite(latency)):
        raise APIError(400, 'latency_ms must be a number between 0 and 600000')
    message = value.get('message', '')
    if not isinstance(message, str) or len(message) > 500:
        raise APIError(400, 'message must be a string of at most 500 characters')
    metadata = value.get('metadata', {})
    if not isinstance(metadata, dict) or len(metadata) > 10:
        raise APIError(400, 'metadata must be an object with at most 10 entries')
    for key, item in metadata.items():
        text(key, 'metadata key', 40)
        if not isinstance(item, str) or len(item) > 200:
            raise APIError(400, 'metadata values must be strings of at most 200 characters')
    return {'status': status(value['status']), 'latency_ms': latency,
            'message': message, 'metadata': dict(metadata)}
