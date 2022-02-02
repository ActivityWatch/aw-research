from datetime import timedelta
from typing import Union, List


class Node:
    """
    Used to represent a tree with a value (usually time)

    Useful to visualize time spent in each category.
    """
    def __init__(self, label: str, value: int):
        self.label = label
        self.value = value
        self.children = []

    def __repr__(self) -> str:
        return f"<Node '{self.label}' with '{self.value}' and {len(self.children)} children>"

    def __contains__(self, label: Union[str, List[str]]) -> bool:
        if isinstance(label, list):
            node = self
            for sublabel in label:
                node = node[sublabel]
            return node
        else:
            return any(label == child.label for child in self.children)

    def __getitem__(self, label: str) -> 'Node':
        return next(child for child in self.children if child.label == label)

    def __iadd__(self, other: 'Node') -> 'Node':
        assert isinstance(other, Node)
        self.children.append(other)
        return self

    def total(self) -> Union[int, timedelta]:
        acc = self.value
        if isinstance(self.value, timedelta):
            zero = timedelta()
        else:
            zero = 0
        acc += sum([c.total() for c in self.children], zero)
        return acc

    def print(self, depth=1, width=24, indent=4, sort=True) -> str:
        total = self.total()
        children = self.children
        if sort:
            children = sorted(children, key=lambda c: c.total(), reverse=True)
        label = f"{self.label}:".ljust(width - indent * depth)
        parent = f"  {total}  {'(' + str(self.value) + ')' if self.value != total else ''}\n"
        children = "".join([(" " * indent * depth) + node.print(depth=depth + 1) for node in children])
        return label + parent + children


def test_node():
    root = Node('root', 1)

    work = Node('Work', 2)
    root += work
    assert 'Work' in root

    prog = Node('Programming', 2)
    work += prog
    assert 'Programming' in work
    assert work['Programming']

    media = Node('Media', 3)
    root += media
    media += Node('YouTube', 5)

    print(work.print())
    print(root.print())
    assert root.total() == 13


def test_node_timedelta():
    root = Node('root', timedelta(seconds=5))
    root += Node('work', timedelta(seconds=30))
    print(root.total())
    print(root.print(sort=False))


if __name__ == "__main__":
    test_node()
    test_node_timedelta()
