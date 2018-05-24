from datetime import timedelta
from copy import deepcopy
from difflib import SequenceMatcher


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


def merge_close_and_similar(events, pulsetime=10):
    """
    Merges close window events with similar window title.

    Useful when a window is constantly making small changes
    to its window title that you don't care about.
    """
    events = deepcopy(events)
    events = sorted(events, key=lambda e: e.timestamp)

    merged_events = [events[0]]

    for i in range(1, len(events)):
        e1 = merged_events[-1]
        e2 = events[i]

        merged = False

        if e1.data["app"] == e2.data["app"]:
            gap = e2.timestamp - (e1.timestamp + e1.duration)
            assert gap >= timedelta(0)

            # Only merge if events are close
            if gap <= timedelta(seconds=pulsetime):
                simscore = similar(e1.data["title"], e2.data["title"])
                if simscore > 0.9:
                    e1.duration = (e2.timestamp + e2.duration) - e1.timestamp
                    merged = True

        if not merged:
            merged_events.append(e2)

    return merged_events
