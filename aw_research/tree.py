
class Node:
    """
    Used to represent a tree with a value (usually time)

    Useful to visualize time spent in each category.
    """
    def __init__(self, label: str, value: int):
        self.label = label
        self.value = value
        self.children = []

    def total(self):
        return self.value + sum([c.total() for c in self.children])

    def print(self, depth=1) -> str:
        parent = f"{self.label}: {self.total()} ({self.value})\n"
        children = "".join([("    " * depth) + node.print(depth=depth + 1) for node in self.children])
        return parent + children


def test_node():
    root = Node('root', 1)

    work = Node('Work', 2)
    root.children.append(work)

    media = Node('Media', 3)
    root.children.append(media)

    prog = Node('Programming', 2)
    work.children.append(prog)

    print(work.print())
    print(root.print())
    assert root.total() == 8


if __name__ == "__main__":
    test_node()
