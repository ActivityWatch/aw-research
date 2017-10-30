from aw_core.models import Event
from aw_analysis.simplify import simplify


def test_simplify():
    assert simplify([Event(data={"title": "(2) asd"})])[0].data["title"] == "asd"
    assert simplify([Event(data={"title": "Cemu - FPS: 12.2 - ..."})])[0].data["title"] == "Cemu -  - ..."
