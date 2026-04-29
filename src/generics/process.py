from abc import ABC, abstractmethod
import json


class ProcessLike(ABC):
    """
    A process uses a stateless LLM for carrying out some kind of computation.
    """
    def __init__(self, process_name, client, model):
        self.process_name = process_name
        self.client = client
        self.model = model
        self.functions = [] # Implementations should fill with implemented functions

    @abstractmethod
    def messages(self, context: list):
        """
        Given a context, produces a sequence of messages to be used as context by the LLM.
        For instance, this method may append a system prompt to the provided context.
        """
        pass

    def apply(self, context: list):
        """
        Given a context, computes an output using an LLM
        :param context: A list of messages
        :return: LLM response message
        """
        #print(self.messages(context))

        chat = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages(context),
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
