from abc import ABC, abstractmethod
import json
from dataclasses import asdict

from utilities.Message import Message


class ProcessLike(ABC):
    """
    A process uses a stateless LLM for carrying out some kind of computation.
    """
    def __init__(self, process_name, client, model):
        self.process_name = process_name # A name to distinguish different processes in verbose mode
        self.client = client # Client to perform calls to LLM
        self.model = model   # LLM
        self.functions = []  # Implementations should fill with implemented functions

    @abstractmethod
    def messages(self, data) -> list[Message]:
        """
        Given some data, produces a sequence of messages to be used as context by the LLM.
        For instance, this method may append a system prompt to the provided context.
        """
        pass

    def apply(self, data) -> str:
        """
        Given a context, computes an output using an LLM.
        This is the main action performed by a process.

        :param data: Some input data
        :return: LLM response message
        """
        #print(self.messages(context))

        chat = self.client.chat.completions.create(
            model=self.model,
            messages=[asdict(m) for m in self.messages(data)],
            tools=self.functions
        )
        response = chat.choices[0]

        if response.message.tool_calls is not None:
            for tool_call in response.message.tool_calls:
                function = tool_call.function
                fn = getattr(self, function.name)
                print(f"Process '{self.process_name}' calling {function.name} function")
                fn(**json.loads(function.arguments))

        #print(response)

        return response.message.content
