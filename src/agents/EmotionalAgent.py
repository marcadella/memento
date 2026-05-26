from generics.agent import AgentLike
from memories.FlashMemory import FlashMemory
from memories.GraphicalEmotionalState import GraphicalEmotionalState
from memories.KeyValueMemory import KeyValueMemory
from memories.LineOfThought import LineOfThought
from processes.HearingProcess import HearingProcess
from processes.ReactInConversationProcess import ReactInConversationProcess
from processes.ReactInConversationWithModulationProcess import ReactInConversationWithModulationProcess
from utilities.Message import Message
from utilities.client import default_client
from PIL import Image


class EmotionalAgent(AgentLike):
    """
    A simple agent with an infinite context memory and an ability to store important information in a dictionary (this memory is not used for anything though).
    """

    def __init__(self, name: str, client=default_client, model="gpt-4.1-mini", skip_generation=False, post_modulation=False, initial_emotion="elegance", skip_LOT=False):
        super().__init__(name, verbose=True)
        self.client = client
        self.post_modulation = post_modulation

        # Memories
        #self.kv_memory = KeyValueMemory(name, self.client, model)
        self.emotional_state = GraphicalEmotionalState(self.client, skip_generation=skip_generation, initial_emotional_state=f"results/emotions/{initial_emotion}.png")
        self.flash_memory = FlashMemory(10000)
        self.LOT = LineOfThought()
        self.skip_LOT = skip_LOT

        # Processes
        self.hearing_processes = HearingProcess("hearing", self.client, model, name, self.LOT)
        if self.post_modulation:
            self.speaking_process = ReactInConversationProcess("speaking", self.client, model, name, self.LOT)
        else:
            self.speaking_process = ReactInConversationWithModulationProcess("speaking", self.client, model, name,
                                                                             None if not self.skip_LOT else self.LOT,
                                                                             self.emotional_state)

        # Commands
        self.registered_commands = {
            "flash": "Prints the content of the flash memory.",
            "tokens": "Prints the sum of token used.",
            "thoughts": "Prints the line of thoughts.",
            "emotions": "Shows the emotions in an external viewer."
        }

    def speak(self):
        """
        We react to the diverse memory/states
        """
        answer = self.speaking_process.apply(self.flash_memory.get())
        if self.post_modulation:
            print(f"Unmodulated: {answer}")
            answer = self.emotional_state.get(answer)[0]
        return answer

    def hear(self, speaker_name: str, content: str):
        """In this implementation, each new message is analysed by the KeyValueMemory process:
          - if something is worth storing in the memory, the LLM makes a call to a storage function (one or more times)
          - if nothing is interesting, the LLM do nothing.
          Then we append the message to the unbounded history.
        """
        role = "assistant" if speaker_name == self.name else "user"
        message = Message(role=role, content=content, name=speaker_name)
        self.flash_memory.put(message)
        if role != "assistant":
            #self.kv_memory.put(content)
            self.emotional_state.put(self.flash_memory.get()[-1])
            print(self.flash_memory.get())
            self.hearing_processes.apply(self.flash_memory.get())

    def flash(self):
        """
        Get the content of the flash memory
        :return:
        """
        return "\n".join([m.to_string() for m in self.flash_memory.get()])

    def tokens(self, last_n=0):
        """
        Get the completion, prompt and total token counts of all the processes.
        :param last_n: Only last n responses. If 0 (default), return sum for all responses.
        :return: String.
        """
        completion_tokens = self.speaking_process.tokens("completion", last_n)
        prompt_tokens = self.speaking_process.tokens("prompt", last_n)
        total_tokens = self.speaking_process.tokens("total", last_n)

        return "\n".join([f"- completion_tokens: {completion_tokens}",
                            f"- prompt_tokens: {prompt_tokens}",
                            f"- total_tokens: {total_tokens}"])

    def thoughts(self):
        """
        Get the content of the line of thoughts
        :return:
        """
        return "\n".join(self.LOT.get())

    def emotions(self):
        Image.open(self.emotional_state.last_location).show()
        return "<Image shown in external viewer.>"