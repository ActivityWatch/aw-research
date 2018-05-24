import logging
from typing import List

from aw_core.models import Event
from aw_client import ActivityWatchClient

# Function was moved into aw_transform
from aw_transform import filter_keyvals, filter_period_intersect


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


def test_filter_data():
    awapi = ActivityWatchClient("cleaner", testing=True)
    events = awapi.get_events("aw-watcher-web-test", limit=-1)
    events = filter_datafields(events, "title")
    assert "title" not in events[0].data


def test_filter_short():
    # TODO: This was used in dev and does not work.
    awapi = ActivityWatchClient("cleaner", testing=True)
    events = awapi.get_events("aw-watcher-web-test", limit=-1)
    filter_short(events, threshold=1)

    events = awapi.get_events("aw-watcher-window-testing_erb-main2-arch", limit=-1)
    filter_short(events, threshold=1)

    events = awapi.get_events("aw-watcher-afk-testing_erb-main2-arch", limit=-1)
    filter_short(events, threshold=30)


if __name__ == "__main__":
    test_filter_data()
    test_filter_short()
