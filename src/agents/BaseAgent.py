from generics.agent import AgentLike
from memories.FlashMemory import FlashMemory
from processes.ReactToContextProcess import ReactToContextProcess
from utilities.Message import Message


class BaseAgent(AgentLike):
    """
    A simple agent with a flash memory (bounded rolling context).
    """
    def __init__(self, name: str, client, model="gpt-4.1-mini", verbose=False, flash_memory_size=10000):
        super().__init__(name, verbose)
        self.react_processes = ReactToContextProcess("react", client, model, name)
        self.flash_memory = FlashMemory(flash_memory_size)

    def speak(self) -> str:
        """
        In this implementation, we react to the context.
        """
        context = self.flash_memory.get() # Only for testing purpose
        return self.react_processes.apply(context)

    def hear(self, speaker_name: str, content: str):
        """In this implementation, each new message is ...
        """
        role = "assistant" if speaker_name == self.name else "user"
        self.flash_memory.put(Message(role=role, content=content, name=speaker_name))
        if self.verbose:
            print(self.flash_memory.get())

    def flash(self):
        """
        Get the content of the flash memory
        :return:
        """
        return "\n".join([m.to_string() for m in self.flash_memory.get()])