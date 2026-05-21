#!/usr/bin/env python
"""End-to-end test for GraphMemory.

Writes a handful of sample messages to the graph via GraphMemory.put(),
then queries the database to show what was stored. Intended for manual
verification during development, not a unit test. Use scripts/clear_graph.py
afterwards to remove the test data.

Usage:
    python scripts/test_graph_memory.py
"""

import os

from openai import AzureOpenAI

from graph.connection import make_driver
from memories.GraphMemory import GraphMemory
from utilities.Message import Message


TEST_AGENT_ID = "TestAgent"

TEST_MESSAGES = [
    Message(
        role="user",
        content="Marcus moved to Tromso last month and started a new job at Anthropic.",
        name="H",
    ),
    Message(
        role="user",
        content="How are you doing today?",
        name="H",
    ),
    Message(
        role="user",
        content=(
            "My favorite Norwegian dish is fiskeboller. I learned to make "
            "them from my grandmother."
        ),
        name="H",
    ),
    Message(
        role="user",
        content="Marcus also enjoys hiking in the mountains around Tromso.",
        name="H",
    ),
]


def make_client() -> AzureOpenAI:
    """Build an Azure OpenAI client from CHATUIT_* environment variables."""
    return AzureOpenAI(
        azure_endpoint=os.environ["CHATUIT_BASE_URL"],
        api_key=os.environ["CHATUIT_API_KEY"],
        api_version="2024-02-15-preview",
    )


def write_messages(memory: GraphMemory) -> None:
    """Feed every test message through GraphMemory.put()."""
    print("=== Writing messages to graph ===")
    for msg in TEST_MESSAGES:
        print(f"Processing: {msg.content}")
        memory.put(msg)
    print()


def inspect_graph(driver) -> None:
    """Query Neo4j for what was just written and print a human-readable summary."""
    print("=== Inspecting the graph ===")
    with driver.session() as session:
        # Count nodes by label.
        result = session.run(
            """
            MATCH (n) WHERE n.agent_id = $agent_id
            RETURN labels(n)[0] AS label, count(n) AS n
            ORDER BY label
            """,
            agent_id=TEST_AGENT_ID,
        )
        print(f"Nodes for {TEST_AGENT_ID}:")
        for record in result:
            print(f"  {record['label']}: {record['n']}")

        # Show all relationships.
        result = session.run(
            """
            MATCH (h:Entity)-[r:RELATES]->(t:Entity)
            WHERE r.agent_id = $agent_id
            RETURN h.name AS head, r.type AS relation, t.name AS tail
            ORDER BY h.name
            """,
            agent_id=TEST_AGENT_ID,
        )
        print()
        print(f"Relations for {TEST_AGENT_ID}:")
        for record in result:
            print(f"  ({record['head']}) -[{record['relation']}]-> ({record['tail']})")


def main() -> None:
    client = make_client()
    driver = make_driver()
    try:
        memory = GraphMemory(
            name=TEST_AGENT_ID,
            client=client,
            model="gpt-4.1-mini",
            driver=driver,
        )
        write_messages(memory)
        inspect_graph(driver)
    finally:
        driver.close()


if __name__ == "__main__":
    main()