


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


# Deterministic backstop for the extraction prompt. Triples whose head
# or tail (case-insensitive) lands in this set are dropped before they
# reach Neo4j. The extractor is told to avoid these in the prompt, but
# the LLM still leaks them occasionally; this catches every time.
ENTITY_STOPWORDS: frozenset[str] = frozenset({
    # short answers
    "yes", "no", "yeah", "yep", "nope", "sure", "okay", "ok",
    "maybe", "perhaps",
    # greetings / farewells / thanks
    "hi", "hello", "hey", "bye", "goodbye", "thanks", "thx",
    # generic placeholders
    "thing", "things", "stuff", "something", "anything", "nothing",
    "someone", "anyone", "everyone",
    # pronouns
    "it", "this", "that", "these", "those",
    "me", "you", "we", "us", "them", "him", "her", "they",
    "he", "she", "i",
    # agent-self labels
    "assistant", "ai", "bot", "chatbot",
})


class GraphMemory(MemoryLike):
    """
    Per-agent graph memory backed by a Neo4j database."""

    def __init__(self, name: str, client, model: str, driver, extraction_client=None, extraction_model: str | None = None):
        """
        Args:
            name: Agent's name. Used as agent_id to namespace this memory's
                data within the shared Neo4j database.

            client: OpenAI or AzureOpenAI client. Used for embeddings (always)
                and for extraction (unless extraction_client is provided).
            model: Chat model name or Azure deployment name. Used as fallback
                for extraction if extraction_model is not provided.
            driver: A connected Neo4j driver. Caller manages its lifecycle.
            extraction_client: Optional. Separate client used only for triple
                extraction. Lets you route extraction to a different provider
                (e.g. standard OpenAI for access to gpt-4.1) while keeping
                chat and embeddings on Azure. Defaults to `client`.
            extraction_model: Optional. Model used for triple extraction.
                Defaults to the chat model. Set to a stronger model
                (e.g. 'gpt-4.1') to reduce noisy / meta extractions.
        """
        super().__init__()

        self.agent_id = name  #  The agent's identity. (Every node and relationship this memory writes carries this value)
        self.client = client  #  OpenAI/Azure client (used for embeddings + chat)
        self.driver = driver  #  Neo4j driver


        self._current_message_id = None  #  Holds the id of the message currently being processed by put().

        # The LLM-driven extraction process. Falls back to the chat
        # client and model if no extraction-specific ones were passed.
        self.extraction_process = GraphExtractionProcess(
            process_name=f"{name}.graph_extraction",
            client=extraction_client or client,
            model=extraction_model or model,
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

    def store_triple(self, head: str = "", relation: str = "", tail: str = ""):
        """
        Called by GraphExtractionProcess once per extracted triple.

        MERGEs both entity nodes (deduplicating by (name, agent_id)) and
        creates a :RELATES relationship between them. Provenance is
        recorded via source_message_id pointing at the current :Message.

        Args default to "" so a malformed LLM tool call with missing
        arguments no-ops via the stopword filter instead of raising
        TypeError. Required args are still required for correct use.
        """

        # Defensive check: this method should only run during put(). If it gets called any other way, something is wired wrong.
        if self._current_message_id is None:
            raise RuntimeError(
                "store_triple called outside of put(). Extraction should only run via the put() pipeline."
            )

        # Deterministic noise filter: drop triples whose head or tail is
        # a stopword, the agent's own name, or empty. Prompt rules cover
        # this but the LLM ignores them sometimes.
        h_norm = head.strip().lower()
        t_norm = tail.strip().lower()
        if not h_norm or not t_norm:
            return
        if h_norm in ENTITY_STOPWORDS or t_norm in ENTITY_STOPWORDS:
            return
        if h_norm == self.agent_id.lower() or t_norm == self.agent_id.lower():
            return

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

                // Link the source message to the entities it mentioned.
                // MERGE so the same entity mentioned twice in one
                // message does not create duplicate :MENTIONS edges.
                // Complements the source_message_id property on :RELATES:
                // that property answers "which message produced this
                // exact fact"; :MENTIONS answers "which entities did
                // this message touch."
                WITH h, t
                MATCH (m:Message {id: $message_id, agent_id: $agent_id})
                MERGE (m)-[mh:MENTIONS]->(h)
                ON CREATE SET mh.agent_id = $agent_id
                MERGE (m)-[mt:MENTIONS]->(t)
                ON CREATE SET mt.agent_id = $agent_id
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

    def get(self, query=None) -> list[str]:
        """
        Retrieve memory relevant to a query using hybrid retrieval.

        Combines vector search over entities (with 1-hop traversal in both
        directions) and vector search over messages. Returns formatted
        strings ready to drop into a prompt.

        Args:
            query: Natural-language query. If None or empty, returns [].

        Returns:
            A list of strings, each describing one retrieved fact or
            quoted past message. Empty list if query is empty.
        """

        # No query --> nothing to retrieve. Empty list, no DB call.
        if not query or not query.strip():
            return []

        # Embed the query once. Used for both vector searches below.
        query_embedding = embed_text(self.client, query)

        results: list[str] = []

        with self.driver.session() as session:
            # Vector search on entities (top 5 for this agent), then 1-hop
            # traversal in both directions. The new Cypher 25 SEARCH clause
            # replaces the deprecated db.index.vector.queryNodes procedure.
            # WHERE inside SEARCH filters at index level.

            entity_query = """
            MATCH (e:Entity)
            SEARCH e IN (
                VECTOR INDEX entity_embedding
                FOR $query_embedding
                LIMIT 5
            )
            WHERE e.agent_id = $agent_id
            OPTIONAL MATCH (e)-[r:RELATES]-(other:Entity)
            WHERE r.agent_id = $agent_id
            RETURN startNode(r).name AS head,
                r.type AS relation,
                endNode(r).name AS tail
            """

            result = session.run(entity_query, query_embedding=query_embedding, agent_id=self.agent_id)

            # Format each triple. Skip rows where the seed entity had no
            # relations (OPTIONAL MATCH gives those rows with nulls).
            for record in result:
                if record["relation"] is None:
                    continue

                results.append(f"{record['head']} {record['relation']} {record['tail']}")


            # Vector search on messages (top 3 for this agent). Same new
            # SEARCH syntax. No traversal needed.

            message_query = """
            MATCH (m:Message)
            SEARCH m IN (
                VECTOR INDEX message_embedding
                FOR $query_embedding
                LIMIT 3
            )
            WHERE m.agent_id = $agent_id
            RETURN m.speaker AS speaker, m.content AS content
            """

            result = session.run(message_query, query_embedding=query_embedding, agent_id=self.agent_id)

            for record in result:
                results.append(f"{record['speaker']} said: {record['content']}")

        return results
    
    def get_retrieve_tooling(self) -> dict:
        """Expose graph retrieval as an LLM tool.

        Returns a dict with the OpenAI tool schema, an explanation for the
        system prompt, and the callable that the tool dispatcher invokes.
        Mirrors the pattern in RAGMemory.get_retrieve_tooling() so agents
        can wire memory backends in interchangeably.

        Returns:
            Dict with keys:
                api: OpenAI tool/function schema
                explanation: text for the system prompt describing the tool
                func: the callable invoked when the LLM calls the tool
        """
        
        api = {
            "type": "function",
            "function": {
                "name": "retrieve_from_graph",
                "description": (
                    "Retrieve facts and past messages relevant to a query "
                    "from the graph memory. Use this when you need to recall "
                    "what you know about a person, place, topic, or past "
                    "conversation."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "A natural-language query describing what to "
                                "recall. Examples: 'what do I know about "
                                "Marcus', 'what has the user said about food'."
                            ),
                        },
                    },
                    "required": ["query"],
                },
            },
        }

        explanation = (
            "You have access to long-term graph memory via a tool called "
            "'retrieve_from_graph'. Call it with a natural-language query "
            "when you need to recall facts about people, places, or topics "
            "the user has mentioned in past conversations. The tool returns "
            "a list of facts and quoted messages."
        )

        return {"api": api, "explanation": explanation, "func": self.get}