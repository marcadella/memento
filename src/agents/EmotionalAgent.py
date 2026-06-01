from generics.agent import AgentLike
from memories.FlashMemory import FlashMemory
from memories.PictorialEmotionalState import PictorialEmotionalState
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
    An agent with a flash memory, a line of thought (LOT) and an emotional state.
    """

    def __init__(self, name: str, client=default_client, model="gpt-4.1-mini", skip_generation=False, post_modulation=False, initial_emotion="elegance", skip_LOT=False):
        super().__init__(name, verbose=True)
        self.client = client
        self.post_modulation = post_modulation

        # Memories
        self.emotional_state = PictorialEmotionalState(self.client, skip_generation=skip_generation, initial_emotional_state=f"results/emotions/{initial_emotion}.png")
        self.flash_memory = FlashMemory(10000)
        self.LOT = LineOfThought()
        self.skip_LOT = skip_LOT

        # Processes
        self.hearing_processes = HearingProcess("hearing", self.client, model, name, self.LOT)
        if self.post_modulation:
            # With post modulation, the agent produces an output, which is modulated afterward.
            self.speaking_process = ReactInConversationProcess("speaking", self.client, model, name, self.LOT)
        else:
            # Here, the modulation is integrated withing the generation process.
            self.speaking_process = ReactInConversationWithModulationProcess(process_name="speaking", client=self.client, model="gpt-4.1", agent_name=name,
                                                                             LOT=None if not self.skip_LOT else self.LOT,
                                                                             emotional_state=self.emotional_state)

        # Commands
        self.registered_commands = {
            "flash": "Prints the content of the flash memory.",
            "tokens": "Prints the sum of token used.",
            "thoughts": "Prints the line of thoughts.",
            "emotions": "Shows the emotional state picture in an external viewer."
        }

    def speak(self):
        """
        Conscious speaking process.
        React to the different states (flash, line of thought, and emotional state) and generates an output.
        """
        answer = self.speaking_process.apply(self.flash_memory.get())
        if self.post_modulation:
            # Optional post modulation.
            print(f"Unmodulated: {answer}")
            answer = self.emotional_state.get(answer)[0]
        return answer

    def hear(self, speaker_name: str, content: str):
        """Conscious hearing process.
        In this implementation, each new message is:
        - appended to the flash memory,
        - affects the emotional state,
        - update the line of thoughts
        """
        role = "assistant" if speaker_name == self.name else "user"
        message = Message(role=role, content=content, name=speaker_name)
        self.flash_memory.put(message)
        if role != "assistant":
            self.emotional_state.put(self.flash_memory.get()[-1])
            self.hearing_processes.apply(self.flash_memory.get())

    def flash(self):
        """
        Get the content of the flash memory
        :return:
        """
        return "\n".join([m.to_string() for m in self.flash_memory.get()])

    def tokens(self, last_n=0):
        """
        Get the token counts of all the processes.
        :param last_n: Only last n responses. If 0 (default), return sum for all responses.
        :return: String.
        """
        output_tokens = self.speaking_process.tokens("output", last_n)
        input_tokens = self.speaking_process.tokens("input", last_n)
        total_tokens = self.speaking_process.tokens("total", last_n)

        return "\n".join([f"- output_tokens: {output_tokens}",
                            f"- input_tokens: {input_tokens}",
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