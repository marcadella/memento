

# LLM-driven extraction of (head, relation, tail) triples from text.

"""
Mirrors the structure of KeyValueProcess: registers a single tool function that the LLM
may call zero or more times per input, and dispatches each tool call to a user-supplied callback.
"""

from typing import Callable

from generics.process import ProcessLike
from utilities.Message import Message
from utilities.prompts import load_prompt

class GraphExtractionProcess(ProcessLike):
    """
    Extracts triples from a single message via LLM tool calls.

    On each call to apply(text), the process asks the LLM to read the text
    and emit zero or more store_triple(head, relation, tail) tool calls.
    Each tool call is forwarded to the store_triple callback provided at
    construction time.

    The process is stateless. State lives in the callback's owner
    (typically a GraphMemory instance that writes to Neo4j).
    """

    def __init__(self, process_name: str, client, model: str, store_triple: Callable[[str, str, str], None]):
        super().__init__(process_name, client, model)


        self.store_triple = store_triple
        self.prompt_template = load_prompt("graph_extraction")

        store_triple_api = {
            "type": "function",
            "function": {
                "name": "store_triple",
                "description": (
                    "Store a single factual relationship extracted from the text as a (head, relation, tail) triple. Call this tool "
                    "ONCE per distinct fact. If the text contains no extractable facts, do not call the tool."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "head": {
                            "type": "string",
                            "description": (
                                "The subject entity. Must be a specific named entity such as a person, place, organization, "
                                "or concept. If the subject is the speaker (first-person 'I' or 'my'), use the literal string 'user' as the head."
                            ),
                        },
                        "relation": {
                            "type": "string",
                            "description": (
                                "The relationship type in lowercase snake_case. Examples: 'works_at', 'lives_in', 'is_a', 'favorite_food', 'born_in'."
                            ),
                        },
                        "tail": {
                            "type": "string",
                            "description": (
                                "The object entity. Same entity-style as head: "
                                "a specific named entity, not a sentence "
                                "fragment or descriptive phrase."
                            ),
                        },
                    },
                    "required": ["head", "relation", "tail"],
                },
            },
        }
        self.functions.append(store_triple_api)

    def messages(self, context: str) -> list[Message]:
        """
        Build the prompt for triple extraction.

        Args:
            context: The text to extract triples from.

        Returns:
            A list with a single system message containing instructions
            and the input text.

        """

        return [Message(role="system", content=self.prompt_template.format(context=context))]