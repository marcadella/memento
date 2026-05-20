import base64

from generics.process import ProcessLike
from memories.GraphicalEmotionalState import GraphicalEmotionalState
from memories.LineOfThought import LineOfThought
from utilities.Context import ctx
from utilities.Message import Message


class ReactInConversationWithModulationProcess(ProcessLike):
    """
    Example of output process where the LLM is requested to produce an answer given a context using a system prompt.
    The agent knows its name, and it is aware that there may be multiple users taking part of the discussion.
    """
    def __init__(self, process_name, client, model, agent_name, LOT: LineOfThought, emotional_state: GraphicalEmotionalState):
        super().__init__(process_name, client, model)
        self.agent_name = agent_name
        self.LOT = LOT
        self.emotional_state = emotional_state

    def messages(self, context: list[Message]) -> list[Message]:
        pass

    def apply(self, data) -> str:
        """
        Given a context, computes an output using an LLM.
        This is the main action performed by a process.

        :param data: Some input data
        :return: LLM response message
        """
        ctx.append(self.process_name)
        #print(ctx.current_path())
        #print(self.messages(context))

        with open(self.emotional_state.last_location, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        input = [
                    {
                        "role": "system",
                         "content": [
                             {
                                 "type": "input_text",
                                 "text": f"Your name is '{self.agent_name}' and you are part of a theater play. "
                             },
                         ]
                    }
            ] + self._convert_context(data) + [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Your current emotional state image:"},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_b64}",
                        "detail": "low"
                    },
                ]
            },
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Your next answer should be driven by your line of thought: '{self.LOT.get()}'."
                                f"The user also showed an image which is supposed to represent your internal emotional state. "
                                f"Without explicitly mentioning it, match the tone of your answers to the emotions this image evokes. "
                    },
                ]
            }]

        response = self.client.responses.create(
            model=self.emotional_state.text_model,
            input=input
        )

        self.usages.append(response.usage)

        #print(response)
        ctx.pop()

        return response.output_text

    def _convert_context(self, context: list[Message]):
        return [message.new_api() for message in context]
