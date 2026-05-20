#!/usr/bin/env python

import argparse

parser = argparse.ArgumentParser(description="Example conversation.")

# Add arguments
parser.add_argument("--name", "-n", type=str, default="example_graphical", help="Conversation name")

# Parse arguments
args = parser.parse_args()

from conversations.SingleAgentConversation import SingleAgentConversation
from agents.EmotionalAgent import EmotionalAgent

# We create a conversation instance
conv = SingleAgentConversation(EmotionalAgent("A", skip_generation=True),
                               conversation_name=args.name,
                               override=True)
conv.start(enact=False)
# If the conversation existed already in output/<name>.yaml, it is replayed first.
# Otherwise, a new conversation is started.
# The conversation is saved in output/<name>.yaml

