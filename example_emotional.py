#!/usr/bin/env python

import argparse

from agents.HumanAgent import HumanAgent

parser = argparse.ArgumentParser(description="Example conversation.")

# Add arguments
parser.add_argument("--name", "-n", type=str, default="example_emotional", help="Conversation name")

# Parse arguments
args = parser.parse_args()

from conversations.SingleAgentConversation import SingleAgentConversation
from agents.EmotionalAgent import EmotionalAgent

# We create a conversation instance
conv = SingleAgentConversation(EmotionalAgent("Alex", skip_generation=False),
                               human_agent=HumanAgent("Bob"),
                               conversation_name=args.name,
                               override=True)
conv.start(enact=False)
# If the conversation existed already in output/<name>.yaml, it is replayed first.
# Otherwise, a new conversation is started.
# The conversation is saved in output/<name>.yaml

