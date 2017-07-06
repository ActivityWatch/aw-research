import re
from typing import List, Callable, Tuple
from pprint import pprint

from aw_core.models import Event


def _redact_full(event):
    for key in event.data:
        event.data[key] = "redacted"
    return event


def _redact(events: List[Event], f: Callable[[str], bool]) -> Tuple[List[Event], int]:
    n = 0
    for i, event in enumerate(events):
        for key in event.data:
            if f(event.data[key]):
                n += 1
                print("Redacting: \"{}\"".format(event.data[key]))
                events[i] = _redact_full(event)
                break
    return events, n


def redact_words(events, words):
    words_pattern = "(" + "|".join((re.escape(bw) for bw in words)) + ")"
    r = re.compile(words_pattern)
    events, n_redacted = _redact(events, lambda s: r.search(s.lower()))
    print("Total: {}\nRedacted: {}\nPercent: {}%".format(len(events), n_redacted, 100 * n_redacted / len(events)))
    return events
