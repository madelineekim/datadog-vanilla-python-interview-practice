# Pulse

Pulse is a small service-health notebook. Register services, attach tags, and submit
health observations from manual checks or monitoring clients. Summaries help a
team see recent results without needing a monitoring account.

This is an independent interview practice project, not a Datadog product or an
actual Datadog interview question.

## Run

Python 3.9 or newer is required. No dependencies to install.

```sh
python3 server.py
```

Open http://127.0.0.1:8000. Optional flags: `--host 127.0.0.1 --port 8080`.
Stop with Ctrl-C. All data lives in memory and disappears on restart. The server
handles one request at a time. It is intended for local practice.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary local ports and do not need a separately running server.
They include direct business-operation tests and real HTTP requests.

## API

All API responses are JSON. POST and PATCH require `Content-Type: application/json`
and a JSON object body. The request-body limit is 65,536 bytes. Unknown body fields,
unknown query parameters, and repeated query parameters are rejected.
IDs are opaque strings returned by the API. Paths have no trailing slash.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/services` | List services; optional `tag`, `offset`, `limit` |
| POST | `/api/services` | Register a service |
| GET | `/api/services/{id}` | Get a service |
| PATCH | `/api/services/{id}` | Update supplied fields |
| GET | `/api/overview` | Latest health per service; optional `tag` |
| GET | `/api/tags` | Sorted unique tags currently attached to services |
| POST | `/api/services/{id}/events` | Submit an atomic batch of observations |
| GET | `/api/services/{id}/events` | List observations; optional `status`, `since`, `offset`, `limit` |
| GET | `/api/services/{id}/summary` | Aggregate observations; optional `since` |

### Services

Required `name`: nonempty string, trimmed, at most 80 characters. Names are unique
case-insensitively. Optional `description`: string up to 500 characters, default
empty. Optional `tags`: at most 20 strings, each nonempty and at most 32 characters;
tags are trimmed, lowercased, deduplicated and returned in sorted order.

POST returns 201 and a `Location` header. GET and PATCH return 200. PATCH accepts
one or more of the same fields, replaces the entire tags collection when supplied,
and leaves omitted fields unchanged. Failed writes leave state unchanged.

```sh
curl -i http://127.0.0.1:8000/api/services \
  -H 'Content-Type: application/json' \
  -d '{"name":"Checkout","tags":["web","payments"]}'

curl -X PATCH http://127.0.0.1:8000/api/services/1 \
  -H 'Content-Type: application/json' \
  -d '{"description":"Customer checkout API"}'
```

A service response has `id`, `name`, `description`, `tags`, and `created_at`.
Service lists are in registration order; `tag` is an exact normalized match.

### Observations

Body: `{"events": [...]}` with 1–50 items. Every item requires `status` (`ok`,
`warning`, or `critical`) and `latency_ms` (finite number from 0 through 600000,
excluding booleans). Optional `message` is a string up to 500 characters, default
empty. Optional `metadata` is an object with at most 10 entries; keys are nonempty
strings up to 40 characters and values are strings up to 200 characters.

A batch is validated completely before any item is stored. Received timestamps
are assigned by the server, and every item in a batch shares the same timestamp.
The response is 201 with `accepted` and `items`; each item includes the supplied
fields, defaults, `id`, `service_id`, and `received_at`.

```sh
curl http://127.0.0.1:8000/api/services/1/events \
  -H 'Content-Type: application/json' \
  -d '{"events":[{"status":"ok","latency_ms":42,"metadata":{"region":"eu"}}]}'

curl 'http://127.0.0.1:8000/api/services/1/events?status=ok&offset=0&limit=5'
curl http://127.0.0.1:8000/api/services/1/summary
```

Events are returned oldest first, with submission order breaking timestamp ties.
`since` is an inclusive ISO 8601 timestamp requiring a timezone, e.g.
`2026-01-01T00:00:00Z`. URL-encode `+` as `%2B` for numeric timezone offsets.
Filtering occurs before pagination. List responses have `items`, `total` (the
matching count before pagination), `offset`, and `limit`. Offset defaults to 0
and must be 0–1000000; limit defaults to 20 and must be 1–100. An offset beyond
the matching collection returns an empty page.

Summary returns `service_id`, `event_count`, `counts` by status,
`average_latency_ms` rounded to two decimal places, and `latest_status`.
It includes all matching observations, without pagination. With no observations,
the average is null and latest status is `unknown`.

### Errors

Errors have shape `{"error":"message"}`. Typical statuses:

- 400: invalid JSON, fields, or query parameters
- 404: unknown route or service
- 405: unsupported method on a known route, with an `Allow` header
- 409: duplicate service name
- 413: body exceeds the size limit
- 415: unsupported request content type
- 500: unexpected internal failure, with a generic response

Unsupported HTTP methods outside GET, POST, PATCH and DELETE use the standard
library server's default 501 response.

### Fleet overview

`GET /api/overview` returns all services in registration order with their latest
status, observation count, and last received timestamp. Optional `tag` selects
services by exact normalized tag. The response includes `items`, `service_count`,
and `counts` of services in each status, including `unknown` for services without
observations. It is not paginated.

## Python syntax / data structure calibration

This interview practice tests recognition and reasoning about basic Python data
structures. Keep the challenge in tracing request → routing → validation →
business logic → in-memory state → response.

Aim for roughly 70–80% straightforward Python and 20–30% moderately compact,
idiomatic Python. This is a readability guideline, not a line-count quota.
Use dictionaries, lists, sets, tuples, and nested JSON naturally. Preserve simple
list and set comprehensions, dictionary lookups and updates, iteration over
`dict.items()`, `dict.values()`, and lists, sorting with `key=`, pagination slices,
and `parse_qs` dictionaries whose values are lists.

Prefer a few readable lines for important operations. Avoid deeply nested
comprehensions, comprehensions inside dictionary comprehensions, complicated
generators inside `sum` or `max`, long chains of operations, excessive lambdas,
clever one-liners, cryptic helpers with unexplained positional arguments, and
condensed validation. Use named arguments when they clarify validation limits.
Do not remove normal idiomatic Python just to make every line elementary.

Examples to trace in this application:

- `state.services[service_id]` stores a service; `.get(service_id)` looks it up.
- Event batches validate before updating `state.events`; local lists use `.append()`.
- `state.tags.update(service['tags'])` maintains the unique tag catalog.
- Simple comprehensions filter services and collect unique service IDs.
- `query()` iterates over `.items()` and unwraps single-item parameter lists.
- Pagination slices a filtered list before serializing its records.
- Event metadata and summary counts are nested dictionaries in JSON responses.

For sorting practice, try this in a scratch session using populated state:

```python
services_by_name = sorted(
    state.services.values(),
    key=lambda service: service['name'].casefold(),
)
```

The API itself keeps services in registration order. Future changes should keep
this calibration while preserving the documented API behavior.
