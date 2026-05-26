from generics.memory import MemoryLike
from utilities.BoundedContext import BoundedContext
from utilities.Message import Message


class FlashMemory(MemoryLike):
    def __init__(self, flash_memory_size):
        super().__init__()
        self.bounded_context = BoundedContext(flash_memory_size)

    def get(self, n=None) -> list[Message]:
        """
        Get the content of the flash memory.

        :param n: number of messages to return (n last messages). If None, returns all messages
        :return: List of messages
        """
        return self.bounded_context.get()

    def put(self, data: Message, metadata=None):
        """
        Add a messages to the flash memory.

        :param data: Message to add
        :param metadata: Not used.
        """
        self.bounded_context.append(data)

