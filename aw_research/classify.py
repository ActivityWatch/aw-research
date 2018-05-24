from typing import List, Dict, Any
import socket
from urllib.parse import urlparse

from aw_core.models import Event
from aw_client import ActivityWatchClient

import pydash


def bucket_query(awapi, bucket_type: str = None, host: str=None):
    # Might want to move this into AWClient
    buckets_dict = awapi.get_buckets()
    buckets = pydash.concat(*buckets_dict.values())  # type: List[Any]

    if host == "current":
        host = socket.gethostname()
    if host:
        buckets = [b for b in buckets if b["hostname"] == host]

    if bucket_type:
        buckets = [b for b in buckets if b["type"] == bucket_type]

    return buckets[0]["id"] if buckets else None


def _hostname(url):
    return urlparse(url).netloc


def group_by_url_hostname(events):
    return pydash.group_by(events, lambda e: _hostname(e.data["url"]))


def duration_of_groups(groups: Dict[Any, List[Event]]):
    groups_eventdurations = pydash.map_values(
        groups, lambda g: pydash.map_(g, lambda e: e.duration.total_seconds()))  # type: Dict[Any, float]

    duration_of_groups = pydash.map_values(
        groups_eventdurations, lambda g: pydash.reduce_(g, lambda total, d: total + d))

    return duration_of_groups


def get_web_events():
    awapi = ActivityWatchClient("test", testing=True)
    bid = bucket_query(awapi, bucket_type="current_webpage")
    return awapi.get_events(bid, limit=-1)


if __name__ == "__main__":
    from pprint import pprint

    assert "activitywatch.net" == _hostname("http://activitywatch.net/")
    assert "github.com" == _hostname("https://github.com/")

    events = get_web_events()
    groups = group_by_url_hostname(events)
    duration_pairs = pydash.to_pairs(duration_of_groups(groups))
    pprint(sorted(duration_pairs, key=lambda p: p[1]))
