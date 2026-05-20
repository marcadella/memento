from generics.process import ProcessLike
from memories.LineOfThought import LineOfThought
from utilities.Message import Message


class HearingProcess(ProcessLike):
    """
    Example of output process where the LLM is requested to produce an answer given a context using a system prompt.
    The agent knows its name, and it is aware that there may be multiple users taking part of the discussion.
    """
    def __init__(self, process_name, client, model, agent_name, thoughts: LineOfThought):
        super().__init__(process_name, client, model)
        self.agent_name = agent_name
        self.thoughts = thoughts

        update_lot_API = {
            "type": "function",
            "function": {
                "name": "overwrite_line_of_thought",  # Name must match implementation
                "description": "Update (overwrite) your line of thought",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_line_of_thought": {
                            "type": "string",
                            "description": "Updated version of your line of thought."
                        }
                    },
                    "required": ["new_line_of_thought"]
                }
            }
        }
        self.functions.append(update_lot_API)

    def overwrite_line_of_thought(self, new_line_of_thought):
        self.thoughts.put(new_line_of_thought)

    def messages(self, context: list[Message]) -> list[Message]:
        return [
            Message(
                role="system",
                content=f"Your name is '{self.agent_name}' and you are part of a conversation with multiple users. "
                        f"Each time it is your turn to speak, the only context you have access to is the latest part of the conversation "
                        f"and your own line of thoughts. "
                        f"Use the tool 'overwrite_line_of_thought' to update your line of thought."
                        f"Your line of thought is where you can keep track of what is the general context around you, "
                        f"what is your goal in the discussion, what are your intentions, is your plan, etc. "
                        f"Your current line of thought is: '{self.thoughts.get()}'. "
            )
        ] + context