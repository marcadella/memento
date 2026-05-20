from generics.memory import MemoryLike


class LineOfThought(MemoryLike):
    """
    A key-value memory using a process to decide which information is important to store and what key to use to store data.
    """
    def __init__(self):
        super().__init__()
        self.thoughts = ""

    def get(self, query=None) -> list:
        return [self.thoughts]

    def put(self, data: str, metadata=None):
        self.thoughts = data
