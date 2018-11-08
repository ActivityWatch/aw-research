# TODO
# Replace current redact method with:
#  1. tag (classify.py)
#  2. redact by tag

import re
import logging
from typing import List, Callable, Tuple
from pprint import pprint

from aw_core.models import Event

logger = logging.getLogger(__name__)


def _redact_full(event):
    for key in event.data:
        event.data[key] = "REDACTED"
    return event


def _redact(events: List[Event], f: Callable[[str], bool]) -> Tuple[List[Event], int]:
    n = 0
    for i, event in enumerate(events):
        for key in event.data:
            if f(event.data[key]):
                n += 1
                logger.debug("Redacting: \"{}\"".format(event.data[key]))
                events[i] = _redact_full(event)
                break
    return events, n


def redact_words(events, words):
    words_pattern = r"\b({})\b".format(("|".join(re.escape(bw.lower()) for bw in words)))
    r = re.compile(words_pattern)
    events, n_redacted = _redact(events, lambda s: r.search(s.lower()))

    percent = round(100 * n_redacted / len(events), 2)
    logger.info("# Redacted\n\tTotal: {}\n\tRedacted: {}\n\tPercent: {}%".format(len(events), n_redacted, percent))

    return events
