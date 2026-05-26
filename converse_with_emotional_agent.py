#!/usr/bin/env python

import argparse

from agents.HumanAgent import HumanAgent

parser = argparse.ArgumentParser(description="Conversation with an emotional agent")

# Add arguments
parser.add_argument("--name", "-n", type=str, default="example_emotional", help="Conversation name")
parser.add_argument("--initial", "-i", type=str, default="elegance", help="Initial emotion")
parser.add_argument("--skipg", action="store_true", help="Set this flag to skip emotion update.")
parser.add_argument("--skiplot", action="store_true", help="Set this flag to skip line of thought in answers.")

# Parse arguments
args = parser.parse_args()

from conversations.SingleAgentConversation import SingleAgentConversation
from agents.EmotionalAgent import EmotionalAgent

# We create a conversation instance
conv = SingleAgentConversation(EmotionalAgent("Alex", skip_generation=args.skipg, initial_emotion=args.initial, skip_LOT=args.skiplot),
                               human_agent=HumanAgent("Bob"),
                               conversation_name=args.name,
                               override=False)
conv.start(enact=True)
# If the conversation existed already in output/<name>.yaml, it is replayed first.
# Otherwise, a new conversation is started.
# The conversation is saved in output/<name>.yaml

