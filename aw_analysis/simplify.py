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


# TODO: Turn into proper tests
assert simplify([Event(data={"title": "(2) asd"})])[0].data["title"] == "asd"
assert simplify([Event(data={"title": "(392) asd"})])[0].data["title"] == "asd"
assert simplify([Event(data={"title": "Cemu - FPS: 12.2"})])[0].data["title"] == "Cemu - "
