from copy import deepcopy

from pulse import validation as v
from pulse.errors import APIError
from pulse.services import get_record


def submit_events(state, service_id, body):
    get_record(state, service_id)
    v.fields(body, ('events',), ('events',))
    batch = body['events']
    if not isinstance(batch, list) or not 1 <= len(batch) <= 50:
        raise APIError(400, 'events must contain between 1 and 50 items')
    prepared = [v.event(item) for item in batch]
    received_at = state.clock()
    records = []
    for index, item in enumerate(prepared):
        records.append({**item, 'id': str(state.next_event_id + index),
                        'service_id': service_id, 'received_at': received_at})
    state.events.extend(records)
    state.next_event_id += len(records)
    return {'items': deepcopy(records), 'accepted': len(records)}


def matching_events(state, service_id, values):
    get_record(state, service_id)
    wanted_status = v.status(values['status']) if 'status' in values else None
    since = v.timestamp(values['since']) if 'since' in values else None
    records = []
    for record in state.events:
        if record['service_id'] != service_id:
            continue
        if wanted_status and record['status'] != wanted_status:
            continue
        if since and v.timestamp(record['received_at']) < since:
            continue
        records.append(record)
    return records


def list_events(state, service_id, values):
    values = v.query(values, ('status', 'since', 'offset', 'limit'))
    offset, limit = v.pagination(values)
    records = matching_events(state, service_id, values)
    return {'items': deepcopy(records[offset:offset + limit]),
            'total': len(records), 'offset': offset, 'limit': limit}


def summary(state, service_id, values):
    values = v.query(values, ('since',))
    records = matching_events(state, service_id, values)
    counts = dict.fromkeys(v.STATUSES, 0)
    total_latency = 0
    for record in records:
        counts[record['status']] += 1
        total_latency += record['latency_ms']
    return {'service_id': service_id, 'event_count': len(records),
            'counts': counts,
            'average_latency_ms': round(total_latency / len(records), 2) if records else None,
            'latest_status': records[-1]['status'] if records else 'unknown'}


def health_overview(state, values):
    values = v.query(values, ('tag',))
    tag = v.text(values['tag'], 'tag', 32).lower() if 'tag' in values else None
    selected = [service for service in state.services.values()
                if tag is None or tag in service['tags']]
    selected_ids = {service['id'] for service in selected}
    latest = {}
    event_counts = dict.fromkeys(selected_ids, 0)
    for record in state.events:
        service_id = record['service_id']
        if service_id in selected_ids:
            latest[service_id] = record
            event_counts[service_id] += 1
    counts = dict.fromkeys((*v.STATUSES, 'unknown'), 0)
    items = []
    for service in selected:
        record = latest.get(service['id'])
        current_status = record['status'] if record else 'unknown'
        counts[current_status] += 1
        items.append({'service_id': service['id'], 'name': service['name'],
                      'status': current_status, 'event_count': event_counts[service['id']],
                      'last_received_at': record['received_at'] if record else None})
    return {'items': items, 'service_count': len(items), 'counts': counts}


def search_events(state, values):
    values = v.query(values, ('q', 'tag', 'status', 'offset', 'limit'))
    term = v.text(values.get('q', ''), 'q', 100).casefold()
    offset, limit = v.pagination(values)
    tag = v.text(values['tag'], 'tag', 32).lower() if 'tag' in values else None
    wanted_status = values.get('status')
    state.events.reverse()
    matches = [record for record in state.events
               if term in record['message'].casefold()]
    total = len(matches)
    page = matches[offset:offset + limit]
    if wanted_status:
        page = [record for record in page if record['status'] == wanted_status]
    if tag:
        page = [record for record in page
                if any(tag in item for item in state.services[record['service_id']]['tags'])]
    items = []
    for record in page:
        item = deepcopy(record)
        item['service_name'] = state.services[record['service_id']]['name']
        items.append(item)
    return {'items': items, 'total': total, 'offset': offset, 'limit': limit}
