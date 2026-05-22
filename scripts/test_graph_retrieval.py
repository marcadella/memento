#!/usr/bin/env python
"""End-to-end test for GraphMemory.get().

Runs several queries through GraphMemory.get() against whatever is already
in the graph for TestAgent. Run scripts/test_graph_memory.py first to
populate the graph with sample data.

Intended for manual verification during development. Use
scripts/clear_graph.py afterwards to remove the test data.

Usage:
    python scripts/test_graph_memory.py       # populate first
    python scripts/test_graph_retrieval.py    # then test retrieval
"""

import os

from openai import AzureOpenAI

from graph.connection import make_driver
from memories.GraphMemory import GraphMemory


TEST_AGENT_ID = "TestAgent"

TEST_QUERIES = [
    "Tell me about Marcus.",
    "What does the user like to eat?",
    "Where is Anthropic located?",
    "What do I know about Norway?",
]


def make_client() -> AzureOpenAI:
    """Build an Azure OpenAI client from CHATUIT_* environment variables."""
    return AzureOpenAI(
        azure_endpoint=os.environ["CHATUIT_BASE_URL"],
        api_key=os.environ["CHATUIT_API_KEY"],
        api_version="2024-02-15-preview",
    )


def run_queries(memory: GraphMemory) -> None:
    """Run each test query through GraphMemory.get() and print results."""
    print("=== Retrieving ===")
    for q in TEST_QUERIES:
        print(f"\nQuery: {q}")
        results = memory.get(q)
        if not results:
            print("  (no results)")
            continue
        for r in results:
            print(f"  - {r}")


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
        run_queries(memory)
    finally:
        driver.close()


if __name__ == "__main__":
    main()