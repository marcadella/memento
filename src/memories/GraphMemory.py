


"""
Graph-backed memory using Neo4j as the storage layer.

On put(), extracts (head, relation, tail) triples from the message via an
LLM, then writes both the source message and the extracted triples to the
graph. Each agent's data is namespaced by agent_id so multiple agents can
share a single database without seeing each other's memory.

get() is not implemented yet. Retrieval will land in a separate branch.
"""


import uuid
from datetime import datetime, timezone

from generics.memory import MemoryLike
from processes.GraphExtractionProcess import GraphExtractionProcess
from utilities.Message import Message
from utilities.embeddings import embed_text


class GraphMemory(MemoryLike):
    """
    Per-agent graph memory backed by a Neo4j database."""

    def __init__(self, name: str, client, model: str, driver):
        """
        Args:
            name: Agent's name. Used as agent_id to namespace this memory's
                data within the shared Neo4j database.

            client: OpenAI or AzureOpenAI client (for embeddings and extraction).
            model: Chat model name or Azure deployment name.
            driver: A connected Neo4j driver. Caller manages its lifecycle.
        """
        super().__init__()

        self.agent_id = name  #  The agent's identity. (Every node and relationship this memory writes carries this value)
        self.client = client  #  OpenAI/Azure client
        self.driver = driver  #  Neo4j driver

        
        self._current_message_id = None  #  Holds the id of the message currently being processed by put().

        # The LLM-driven extraction process...
        self.extraction_process = GraphExtractionProcess(
            process_name=f"{name}.graph_extraction",
            client=client,
            model=model,
            store_triple=self.store_triple
        )

    # -------- write path --------

    def put(self, data: Message, metadata=None):
        """
        Store a message and any triples extractable from it.

        Args:
            data: The Message to store. data.name is the speaker,
                data.content is the text.
            metadata: Unused, present for MemoryLike compatibility.
        """

        message_id = str(uuid.uuid4())  #  Generate unique id for this message. (Using UUIDs so no two messages can collide, even across agents)

        # Stash the id on self so store_triple can see it during extraction.
        self._current_message_id = message_id

        # Write the :Message node to Neo4j (with embedding, speaker, etc.).
        self._store_message(message_id=message_id, speaker=data.name or "unknown", content=data.content)

        
        self.extraction_process.apply(data.content)  # Run the extractor...
        self._current_message_id = None  # Reset so any accidental call to store_triple outside of put() raises an error



    def _store_message(self, message_id: str, speaker: str, content: str):
        """
        Write a :Message node to Neo4j with an embedding.
        """

        # Embed the message content
        embedding = embed_text(self.client, content)

        # UTC timestamp so messages can be ordered across timezones...
        timestamp = datetime.now(timezone.utc).isoformat()

        # Single Cypher write. CREATE (not MERGE) because UUIDs are unique by construction, so we never have an existing node to match on.
        with self.driver.session() as session:
            session.run(
                """
                CREATE (m:Message {
                    id: $id,
                    agent_id: $agent_id,
                    speaker: $speaker,
                    content: $content,
                    embedding: $embedding,
                    timestamp: $timestamp
                })
                """,
                id=message_id,
                agent_id=self.agent_id,
                speaker=speaker,
                content=content,
                embedding=embedding,
                timestamp=timestamp,
            )

    def store_triple(self, head: str, relation: str, tail: str):
        """
        Called by GraphExtractionProcess once per extracted triple.

        MERGEs both entity nodes (deduplicating by (name, agent_id)) and
        creates a :RELATES relationship between them. Provenance is
        recorded via source_message_id pointing at the current :Message.
        """

        # Defensive check: this method should only run during put(). If it gets called any other way, something is wired wrong.
        if self._current_message_id is None:
            raise RuntimeError(
                "store_triple called outside of put(). Extraction should only run via the put() pipeline."
            )

        # Embed both entities so they are vector-searchable later.
        head_embedding = embed_text(self.client, head)
        tail_embedding = embed_text(self.client, tail)

        # Single transaction: MERGE both entities and CREATE the relation.
        with self.driver.session() as session:
            session.run(
                """
                // Find-or-create the head entity. ON CREATE runs only
                // when the node is new; ON MATCH runs only when it
                // already existed. This avoids re-embedding entities
                // we have seen before.
                MERGE (h:Entity {name: $head, agent_id: $agent_id})
                ON CREATE SET h.embedding = $head_embedding,
                              h.aliases = [],
                              h.first_seen = $timestamp,
                              h.mention_count = 1
                ON MATCH SET h.mention_count = h.mention_count + 1

                // Same pattern for the tail entity.
                MERGE (t:Entity {name: $tail, agent_id: $agent_id})
                ON CREATE SET t.embedding = $tail_embedding,
                              t.aliases = [],
                              t.first_seen = $timestamp,
                              t.mention_count = 1
                ON MATCH SET t.mention_count = t.mention_count + 1

                // CREATE (not MERGE) so the same fact heard twice
                // becomes two relationships with separate provenance.
                // This preserves "how often was this mentioned" and
                // lets us trace each claim back to its source message.
                CREATE (h)-[r:RELATES {
                    type: $relation,
                    agent_id: $agent_id,
                    source_message_id: $message_id,
                    created_at: $timestamp
                }]->(t)
                """,
                head=head,
                tail=tail,
                head_embedding=head_embedding,
                tail_embedding=tail_embedding,
                relation=relation,
                agent_id=self.agent_id,
                message_id=self._current_message_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    # -------- read path --------

    def get(self, query=None) -> list:
        """
        Retrieve memory matching a query.
        Not implemented yet. Retrieval (hybrid vector + graph traversal).
        """
        # TODO 

        raise NotImplementedError("GraphMemory.get() is not implemented yet!")