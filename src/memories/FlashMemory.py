from generics.memory import MemoryLike
from utilities.BoundedContext import BoundedContext
from utilities.Message import Message


class FlashMemory(MemoryLike):
    def __init__(self, flash_memory_size):
        super().__init__()
        self.bounded_context = BoundedContext(flash_memory_size)

    def get(self, key=None) -> list[Message]:
        return self.bounded_context.get()

    def put(self, data: Message, metadata=None):
        self.bounded_context.append(data)

