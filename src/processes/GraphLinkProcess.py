"""Subconscious link-enrichment process.

Runs after each assistant reply in a background thread. Looks at a
window of recent turns plus the entities those turns touched, and
asks the LLM to find inter-entity connections the per-message
extractor missed. Edges it writes are tagged source='linker' so
they can be told apart from extractor edges in queries.
"""

import json
from dataclasses import asdict
from typing import Callable

from generics.process import ProcessLike
from utilities.Context import ctx
from utilities.Message import Message
from utilities.prompts import load_prompt


class GraphLinkProcess(ProcessLike):
    """LLM process that infers missing links across multiple turns.

    Tool surface mirrors GraphExtractionProcess so the prompt-author
    intuition transfers. The dispatched store_triple here delegates
    to GraphMemory.store_triple with source='linker' so :RELATES
    edges from this process can be distinguished from extractor edges.
    """

    def __init__(self, process_name: str, client, model: str, store_triple: Callable):
        super().__init__(process_name, client, model)

        # Bound method from GraphMemory; we'll forward to it with
        # source='linker' so the writes are tagged.
        self._delegate_store_triple = store_triple
        self.prompt_template = load_prompt("graph_link")

        self.functions.append({
            "type": "function",
            "function": {
                "name": "store_triple",
                "description": (
                    "Store a single missing connection as a (head, relation, tail) "
                    "triple. Only call when a real link spans multiple turns AND "
                    "was not already captured by the per-message extractor. "
                    "Most invocations should produce zero calls."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "head": {
                            "type": "string",
                            "description": (
                                "Subject entity. For first-person utterances use the "
                                "speaker's name (the part before the colon in each "
                                "Recent turn), never the literal word 'user'. Use "
                                "names exactly as they appear in the recent entities "
                                "list."
                            ),
                        },
                        "relation": {
                            "type": "string",
                            "description": "Relation type in lowercase snake_case.",
                        },
                        "tail": {
                            "type": "string",
                            "description": (
                                "Object entity. Same entity-style as head; "
                                "no phrases or pronouns."
                            ),
                        },
                    },
                    "required": ["head", "relation", "tail"],
                },
            },
        })

    def store_triple(self, head: str = "", relation: str = "", tail: str = ""):
        """Tool dispatcher target.

        Base ProcessLike.apply() calls this via getattr(self, "store_triple").
        We forward to the GraphMemory store_triple with source='linker' so
        the edge is tagged.
        """
        self._delegate_store_triple(head=head, relation=relation, tail=tail, source="linker")

    def messages(self, data) -> list[Message]:
        """Build the link-process prompt.

        Args:
            data: Tuple (entities_str, edges_str, messages_str). The
                caller is GraphMemory.link(), which assembles all three
                from recent flash context and recent :MENTIONS / :RELATES
                edges in Neo4j. edges_str gives the linker visibility
                into already-known relationships so it can avoid
                proposing duplicates and reason about what is genuinely
                missing.

        Returns:
            Single system message; no chat history.
        """
        entities_str, edges_str, messages_str = data
        content = self.prompt_template.format(
            entities=entities_str,
            existing_edges=edges_str,
            messages=messages_str,
        )
        return [Message(role="system", content=content)]

    def apply(self, data) -> str:
        """Mirror of base ProcessLike.apply() with the tool-call print
        removed.

        The linker runs in a background daemon thread. Base apply()'s
        per-call print would land mid-input-prompt and corrupt the
        user's H: line. Silenced here so the linker stays invisible
        unless something goes wrong (errors still surface via the
        try/except in GraphMemory.link()).
        """
        ctx.append(self.process_name)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[asdict(m) for m in self.messages(data)],
            tools=self.functions,
        )
        self.usages.append(response.usage)
        response = response.choices[0]

        if response.message.tool_calls is not None:
            for tool_call in response.message.tool_calls:
                function = tool_call.function
                fn = getattr(self, function.name)
                fn(**json.loads(function.arguments))

        ctx.pop()
        return response.message.content
