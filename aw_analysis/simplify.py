import re
from copy import deepcopy

from aw_core.models import Event


def simplify(events):
    events = deepcopy(events)
    for e in events:
        # Remove prefixes that are numbers within parenthesis
        # Example: "(2) Facebook" -> "Facebook"
        e.data["title"] = re.sub(r"^\([0-9]+\)\s*", "", e.data["title"])

        # Remove FPS display in window title
        # Example: "Cemu - FPS: 59.2 - ..." -> "Cemu - - ..."
        e.data["title"] = re.sub(r"FPS:\s+[0-9\.]+", "", e.data["title"])
    return events
