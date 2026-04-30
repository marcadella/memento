from generics.agent import AgentLike
from processes.ReactToContextProcess import ReactToContextProcess
from utilities.BoundedContext import BoundedContext


class BaseAgent(AgentLike):
    """
    A simple agent with a flash memory (bounded rolling context).
    """
    def __init__(self, name: str, client, model="gpt-4.1-mini", verbose=False, flash_memory_size=10000):
        super().__init__(name, verbose)
        self.processes = {
            "react": ReactToContextProcess("react", client, model, name),
        }
        self.flash_memory = BoundedContext(flash_memory_size)

    def speak(self):
        """
        In this implementation, we react to the context.
        """
        context = self.flash_memory.get() # Only for testing purpose
        return self.processes["react"].apply(context)

    def hear(self, speaker_name: str, message: str):
        """In this implementation, each new message is ...
        """
        role = "assistant" if speaker_name == self.name else "user"
        self.flash_memory.append({"role": role, "content": message, "name": speaker_name})
        if self.verbose:
            print(self.flash_memory._current_size())
            print(self.flash_memory.get())