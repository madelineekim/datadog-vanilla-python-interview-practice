from pulse import validation as v
from pulse.errors import APIError


def get_record(state, service_id):
    record = state.services.get(service_id)
    if record is None:
        raise APIError(404, 'Service not found')
    return record


def serialize(record):
    result = dict(record)
    result['tags'] = sorted(record['tags'])
    return result


def create_service(state, body):
    v.fields(body, allowed=('name', 'description', 'tags'), required=('name',))
    name = v.text(body['name'], 'name', maximum=80)
    key = name.casefold()
    if key in state.service_names:
        raise APIError(409, 'Service name already exists')
    description = body.get('description', '')
    if not isinstance(description, str) or len(description) > 500:
        raise APIError(400, 'description must be a string of at most 500 characters')
    service_tags = v.tags(body.get('tags', []))
    service_id = str(state.next_service_id)
    record = {
        'id': service_id,
        'name': name,
        'description': description,
        'tags': service_tags,
        'created_at': state.clock(),
    }
    state.services[service_id] = record
    state.service_names[key] = service_id
    state.next_service_id += 1
    state.refresh_tags()
    return serialize(record)


def get_service(state, service_id):
    record = get_record(state, service_id)
    return serialize(record)


def update_service(state, service_id, body):
    record = get_record(state, service_id)
    v.fields(body, ('name', 'description', 'tags'))
    if not body:
        raise APIError(400, 'Supply at least one field')
    replacement = dict(record)
    if 'name' in body:
        replacement['name'] = v.text(body['name'], 'name', maximum=80)
        owner = state.service_names.get(replacement['name'].casefold())
        if owner is not None and owner != service_id:
            raise APIError(409, 'Service name already exists')
    if 'description' in body:
        if not isinstance(body['description'], str) or len(body['description']) > 500:
            raise APIError(400, 'description must be a string of at most 500 characters')
        replacement['description'] = body['description']
    if 'tags' in body:
        replacement['tags'] = v.tags(body['tags'])
    del state.service_names[record['name'].casefold()]
    state.service_names[replacement['name'].casefold()] = service_id
    state.services[service_id] = replacement
    state.refresh_tags()
    return serialize(replacement)


def list_services(state, values):
    values = v.query(values, ('tag', 'offset', 'limit'))
    offset, limit = v.pagination(values)
    records = list(state.services.values())
    if 'tag' in values:
        tag = v.text(values['tag'], 'tag', maximum=32).lower()
        records = [record for record in records if tag in record['tags']]
    page = records[offset:offset + limit]
    return {
        'items': [serialize(record) for record in page],
        'total': len(records),
        'offset': offset,
        'limit': limit,
    }
