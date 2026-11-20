class EventManager:

    def __init__(self):
        self.processed_events = set()

    def register_event(self, camera_id, event_id):
        if event_id in self.processed_events:
            print(f"[EVENT] Duplicate event: {event_id}")
            return False

        self.processed_events.add(event_id)

        print(
            f"[EVENT] Camera {camera_id} "
            f"detected fall: {event_id}"
        )

        return True