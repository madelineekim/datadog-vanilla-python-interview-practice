from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class State:
    def __init__(self, clock=utc_now):
        self.services = {}
        self.service_names = {}
        self.events = []
        self.tags = set()
        self.next_service_id = 1
        self.next_event_id = 1
        self.clock = clock

    def refresh_tags(self):
        self.tags = set()
        for service in self.services.values():
            self.tags.update(service['tags'])
