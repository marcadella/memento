


"""
Graph-backed memory using Neo4j as the storage layer.

On put(), extracts (head, relation, tail) triples from the message via an
LLM, then writes both the source message and the extracted triples to the
graph. Each agent's data is namespaced by agent_id so multiple agents can
share a single database without seeing each other's memory.

get() is not implemented yet. Retrieval will land in a separate branch.
"""


import os
import sys
import uuid
from datetime import datetime, timezone

from generics.memory import MemoryLike
from processes.GraphExtractionProcess import GraphExtractionProcess
from processes.GraphLinkProcess import GraphLinkProcess
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


def _vlog(*parts):
    """Verbose log to stderr, gated by the EVAL_VERBOSE env var.

    Used to trace extractor/linker decisions during smoke tests without
    polluting normal-run output. Writes to stderr so the message survives
    contexts that redirect stdout (the eval harness silences stdout
    during ingestion).
    """
    if os.environ.get("EVAL_VERBOSE"):
        print(*parts, file=sys.stderr, flush=True)


class GraphMemory(MemoryLike):
    """
    Per-agent graph memory backed by a Neo4j database."""

    def __init__(self, name: str, client, model: str, driver, extraction_client=None, extraction_model: str | None = None, linker_window_chars: int = 3000):
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
            linker_window_chars: Char budget for the slice of recent
                messages handed to the linker. Smaller = more focused
                linker (fewer entities, less noise) but misses links
                spanning further back. Decoupled from flash_memory_size
                so the chat react path can keep a wider context.
        """
        super().__init__()

        self.agent_id = name  #  The agent's identity. (Every node and relationship this memory writes carries this value)
        self.client = client  #  OpenAI/Azure client (used for embeddings + chat)
        self.driver = driver  #  Neo4j driver
        self.linker_window_chars = linker_window_chars


        self._current_message_id = None  #  Holds the id of the message currently being processed by put().

        # The LLM-driven extraction process. Falls back to the chat
        # client and model if no extraction-specific ones were passed.
        self.extraction_process = GraphExtractionProcess(
            process_name=f"{name}.graph_extraction",
            client=extraction_client or client,
            model=extraction_model or model,
            store_triple=self.store_triple
        )

        # The LLM-driven link-enrichment process. Runs in a background
        # thread after each assistant reply to find inter-turn
        # connections the per-message extractor missed. Uses the same
        # client/model split as extraction.
        self.link_process = GraphLinkProcess(
            process_name=f"{name}.graph_link",
            client=extraction_client or client,
            model=extraction_model or model,
            store_triple=self.store_triple,
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
        speaker = data.name or "user"
        self._store_message(message_id=message_id, speaker=speaker, content=data.content)


        # Pass speaker to extraction so first-person facts get
        # attributed to the actual speaker by name, not to a shared
        # 'user' entity. Critical for multi-speaker conversations
        # (e.g. LoCoMo eval where two humans both say 'I').
        preview = data.content if len(data.content) <= 120 else data.content[:117] + "..."
        _vlog(f"[extract] processing {speaker}: {preview}")
        self.extraction_process.apply((speaker, data.content))
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

    def store_triple(self, head: str = "", relation: str = "", tail: str = "", source: str = "extractor"):
        """
        Called by GraphExtractionProcess or GraphLinkProcess once per triple.

        MERGEs both entity nodes (deduplicating by (name, agent_id)) and
        creates a :RELATES relationship between them. For extractor calls,
        also writes (:Message)-[:MENTIONS]->(:Entity) edges and tags the
        :RELATES with the source_message_id of the current message. For
        linker calls, :MENTIONS is skipped (a link inferred across turns
        has no single source message) and source_message_id is null.

        Args:
            head: Subject entity.
            relation: Relation type (LLM-chosen label).
            tail: Object entity.
            source: 'extractor' (default) or 'linker'. Tags the :RELATES
                edge so origin can be queried.

        Args default to "" so a malformed LLM tool call with missing
        arguments no-ops via the stopword filter instead of raising
        TypeError. Required args are still required for correct use.
        """

        # Extractor MUST run inside put(); linker has no anchor message.
        if source == "extractor" and self._current_message_id is None:
            raise RuntimeError(
                "store_triple called outside of put(). Extractor must run via the put() pipeline."
            )

        tag = "[link]" if source == "linker" else "[extract]"
        triple_str = f"({head}) -[{relation}]-> ({tail})"

        # Deterministic noise filter: drop triples whose head or tail is
        # a stopword, the agent's own name, or empty. Prompt rules cover
        # this but the LLM ignores them sometimes.
        h_norm = head.strip().lower()
        t_norm = tail.strip().lower()
        if not h_norm or not t_norm:
            _vlog(f"{tag} DROP (empty): {triple_str}")
            return
        if h_norm in ENTITY_STOPWORDS or t_norm in ENTITY_STOPWORDS:
            _vlog(f"{tag} DROP (stopword): {triple_str}")
            return
        if h_norm == self.agent_id.lower() or t_norm == self.agent_id.lower():
            _vlog(f"{tag} DROP (agent-self): {triple_str}")
            return

        # Linker dedup: skip if any :RELATES with the same
        # (head, relation, tail) already exists for this agent. The
        # extractor intentionally uses CREATE to preserve mention
        # frequency (locked decision #4), but a linker re-emitting the
        # same inference is noise, not signal. Check before doing any
        # work (including embeddings) so duplicates are cheap.
        if source == "linker":
            with self.driver.session() as session:
                existing = session.run(
                    """
                    MATCH (h:Entity {name: $head, agent_id: $agent_id})
                          -[r:RELATES {type: $relation, agent_id: $agent_id}]->
                          (t:Entity {name: $tail, agent_id: $agent_id})
                    RETURN r LIMIT 1
                    """,
                    head=head,
                    tail=tail,
                    relation=relation,
                    agent_id=self.agent_id,
                ).single()
                if existing:
                    _vlog(f"{tag} SKIP (dedup): {triple_str}")
                    return

        # Embed both entities so they are vector-searchable later.
        head_embedding = embed_text(self.client, head)
        tail_embedding = embed_text(self.client, tail)

        timestamp = datetime.now(timezone.utc).isoformat()

        # MERGE entities + CREATE :RELATES. The `source` property tags
        # the edge so extractor vs linker edges can be told apart in
        # queries. source_message_id is null for linker edges.
        base_query = """
            MERGE (h:Entity {name: $head, agent_id: $agent_id})
            ON CREATE SET h.embedding = $head_embedding,
                          h.aliases = [],
                          h.first_seen = $timestamp,
                          h.mention_count = 1
            ON MATCH SET h.mention_count = h.mention_count + 1

            MERGE (t:Entity {name: $tail, agent_id: $agent_id})
            ON CREATE SET t.embedding = $tail_embedding,
                          t.aliases = [],
                          t.first_seen = $timestamp,
                          t.mention_count = 1
            ON MATCH SET t.mention_count = t.mention_count + 1

            CREATE (h)-[r:RELATES {
                type: $relation,
                agent_id: $agent_id,
                source_message_id: $message_id,
                created_at: $timestamp,
                source: $source
            }]->(t)
        """

        # Extractor calls also link the source message to both entities.
        # Linker edges are cross-turn inferences with no single source
        # message, so :MENTIONS is skipped for them.
        mentions_query = """
            WITH h, t
            MATCH (m:Message {id: $message_id, agent_id: $agent_id})
            MERGE (m)-[mh:MENTIONS]->(h)
            ON CREATE SET mh.agent_id = $agent_id
            MERGE (m)-[mt:MENTIONS]->(t)
            ON CREATE SET mt.agent_id = $agent_id
        """

        query = base_query + mentions_query if source == "extractor" else base_query

        with self.driver.session() as session:
            session.run(
                query,
                head=head,
                tail=tail,
                head_embedding=head_embedding,
                tail_embedding=tail_embedding,
                relation=relation,
                agent_id=self.agent_id,
                message_id=self._current_message_id,  # None for linker
                timestamp=timestamp,
                source=source,
            )

        _vlog(f"{tag} WROTE: {triple_str}")

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

    # -------- subconscious link enrichment --------

    def link(self, recent_messages: list[Message]):
        """Run the subconscious link-enrichment pass.

        Intended to be invoked in a background thread after each
        assistant reply. Pulls the entities that the recent stored
        messages touched (via :MENTIONS edges) and asks the link
        process to find inter-turn connections the per-message
        extractor missed.

        Background-thread friendly: any exception is caught and
        printed rather than re-raised, because uncaught thread
        exceptions disappear silently.

        Args:
            recent_messages: Snapshot of recent flash-memory messages,
                used only to render the prompt. The entity list comes
                from Neo4j, not from the messages directly.
        """
        try:
            if not recent_messages:
                return

            # Tighten to the linker window: walk backwards from the most
            # recent message, accumulate chars, stop when the budget is
            # full. Keeps the LLM call focused (fewer entities, less
            # noise) without forcing chat to share the same small window.
            windowed = []
            total_chars = 0
            for m in reversed(recent_messages):
                size = len(m.content) + len(m.name or "")
                if windowed and total_chars + size > self.linker_window_chars:
                    break
                windowed.insert(0, m)
                total_chars += size
            recent_messages = windowed

            # Pull entities touched by the most recent N stored messages
            # for this agent. N matches the (windowed) snapshot so the
            # entity list aligns with the message window the LLM sees.
            n = len(recent_messages)
            with self.driver.session() as session:
                ent_result = session.run(
                    """
                    MATCH (m:Message {agent_id: $agent_id})
                    WITH m ORDER BY m.timestamp DESC LIMIT $n
                    MATCH (m)-[:MENTIONS]->(e:Entity)
                    RETURN DISTINCT e.name AS name
                    """,
                    agent_id=self.agent_id,
                    n=n,
                )
                entities = [r["name"] for r in ent_result]

                # Also pull existing :RELATES edges that already connect
                # these entities. Passing them to the linker lets it
                # reason about what is already known and avoid proposing
                # duplicates (the pre-check dedup catches them anyway,
                # but giving the LLM visibility produces cleaner output).
                if entities:
                    edges_result = session.run(
                        """
                        MATCH (h:Entity {agent_id: $agent_id})-[r:RELATES {agent_id: $agent_id}]->(t:Entity {agent_id: $agent_id})
                        WHERE h.name IN $entity_names AND t.name IN $entity_names
                        RETURN h.name AS head, r.type AS type, t.name AS tail
                        """,
                        agent_id=self.agent_id,
                        entity_names=entities,
                    )
                    existing_edges = [(r["head"], r["type"], r["tail"]) for r in edges_result]
                else:
                    existing_edges = []

            if not entities:
                _vlog(f"[link] start: {n} msgs ({total_chars}c), 0 entities — skipping")
                return  # nothing was extracted yet, nothing to link

            _vlog(
                f"[link] start: {n} msgs ({total_chars}c), "
                f"{len(entities)} entities, {len(existing_edges)} existing edges"
            )

            entities_str = ", ".join(entities)
            edges_str = (
                "\n".join(f"{h} -[{t}]-> {tl}" for h, t, tl in existing_edges)
                or "(none)"
            )
            messages_str = "\n".join(
                f"{m.name or m.role.upper()}: {m.content}"
                for m in recent_messages
            )

            self.link_process.apply((entities_str, edges_str, messages_str))
        except Exception as e:
            # stderr so errors survive stdout-redirect contexts (e.g.,
            # the eval harness silences stdout during ingestion).
            print(f"[link] error: {e}", file=sys.stderr)

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