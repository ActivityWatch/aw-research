from datetime import timedelta
from copy import deepcopy


def flood(events, pulsetime=5, trixy=True):
    """
    See details on flooding here:
     - https://github.com/ActivityWatch/activitywatch/issues/124
    """
    events = deepcopy(events)
    events = sorted(events, key=lambda e: e.timestamp)

    for e1, e2 in zip(events[:-1], events[1:]):
        if e1.data["app"] == e2.data["app"]:
            gap = e2.timestamp - (e1.timestamp + e1.duration)
            assert gap >= timedelta(0)

            if gap <= timedelta(seconds=pulsetime):
                if trixy:
                    if e1.duration >= e2.duration:
                        # Extend e1 forwards until e2
                        e1.duration = e2.timestamp - e1.timestamp
                    else:
                        # Extend e2 backwards until e1
                        e2_end = e2.timestamp + e2.duration
                        e2.timestamp = e1.timestamp
                        e2.duration = e2_end - e2.timestamp
                else:
                    e1.duration = e2.timestamp - e1.timestamp

    return events
