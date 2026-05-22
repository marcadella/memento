#!/usr/bin/env python
"""Example conversation with an agent backed by graph memory.

Run from the repo root:

    python exampleGraph.py

The conversation is interactive. Type your message and the agent
responds. Type an empty line to exit. The agent's memory persists
across runs in the Neo4j database; use scripts/clear_graph.py to
wipe it.
"""

import argparse
import os

from openai import AzureOpenAI

from agents.GraphAgent import GraphAgent
from agents.HumanAgent import HumanAgent
from conversations.SingleAgentConversation import SingleAgentConversation
from graph.connection import make_driver


def main() -> None:
    parser = argparse.ArgumentParser(description="Example conversation with a graph-memory agent.")
    parser.add_argument("--name", "-n", type=str, default="exampleGraph", help="Conversation name.")
    parser.add_argument("--enact", action="store_true", help="Re-enact the conversation history.")
    parser.add_argument("--override", "-x", action="store_true", help="Override an existing conversation.")
    args = parser.parse_args()

    client = AzureOpenAI(
        azure_endpoint=os.environ["CHATUIT_BASE_URL"],
        api_key=os.environ["CHATUIT_API_KEY"],
        api_version="2024-02-15-preview",
    )

    driver = make_driver()
    try:
        agent = GraphAgent(name="A", client=client, driver=driver, model="gpt-4.1-mini")
        human = HumanAgent("H")
        conv = SingleAgentConversation(
            agent=agent,
            human_agent=human,
            conversation_name=args.name,
            override=args.override,
        )
        conv.start(enact=args.enact)
    finally:
        driver.close()


if __name__ == "__main__":
    main()