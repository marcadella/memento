#!/usr/bin/env python

import argparse

parser = argparse.ArgumentParser(description="Conversation with an agent possessing only a flash memory")

# Add arguments
parser.add_argument("--name", "-n", type=str, default="example", help="Conversation name")
parser.add_argument("--enact", action="store_true", help="Set this flag to enact the conversation history (meaning the the AI agents re-generate their parts).")
parser.add_argument("--override", '-x',  action="store_true", help="Set this flag to override an existing conversation.")

# Parse arguments
args = parser.parse_args()

from agents.BaseAgent import BaseAgent
from conversations.SingleAgentConversation import SingleAgentConversation

# We create a conversation instance
conv = SingleAgentConversation(BaseAgent("A", verbose=False),
                               conversation_name=args.name,
                               override=args.override)
conv.start(enact=args.enact)
# If the conversation existed already in output/<name>.yaml, it is replayed first.
# Otherwise, a new conversation is started.
# The conversation is saved in output/<name>.yaml

