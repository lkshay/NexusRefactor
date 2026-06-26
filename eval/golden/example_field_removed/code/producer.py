from models import Event


def make_event(name: str) -> Event:
    return Event(id=1, name=name, deprecated_tag="legacy")
