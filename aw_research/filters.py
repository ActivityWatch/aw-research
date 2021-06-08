import logging
from typing import List

from aw_core.models import Event
from aw_client import ActivityWatchClient


logger = logging.getLogger(__name__)


def filter_short(events, threshold: float = 1):
    # TODO: Try to fill hole in timeline where events have been removed
    #       (if events before and after where are the same)
    #       Useful for filtering AFK data and to make data look "smoother".
    #       Might be something for another function
    return [e for e in events if e.duration.total_seconds() > threshold]


def filter_datafields(events: List[Event], fields: List[str]):
    """Filters away specific datafield from every event in a list"""
    for e in events:
        for field in fields:
            if field in e.data:
                e.data.pop(field)
    return events


# TODO: Generalize
BUCKET_AFK = "aw-watcher-afk_erb-main2-arch"
BUCKET_WINDOW = "aw-watcher-window_erb-main2-arch"
BUCKET_WEB = "aw-watcher-web-firefox"


def test_filter_data() -> None:
    awapi = ActivityWatchClient("cleaner", testing=True)
    events = awapi.get_events(BUCKET_WEB, limit=-1)
    events = filter_datafields(events, ["title"])
    assert "title" not in events[0].data


def test_filter_short():
    # TODO: This was used in dev and does not work.
    awapi = ActivityWatchClient("cleaner", testing=True)
    events = awapi.get_events(BUCKET_WEB, limit=-1)
    filter_short(events, threshold=1)

    events = awapi.get_events(BUCKET_WINDOW, limit=-1)
    filter_short(events, threshold=1)

    events = awapi.get_events(BUCKET_AFK, limit=-1)
    filter_short(events, threshold=30)


if __name__ == "__main__":
    test_filter_data()
    test_filter_short()
