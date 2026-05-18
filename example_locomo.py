#!/usr/bin/env python

import argparse

parser = argparse.ArgumentParser(description="Example Locomo conversation. Attention, previous conversation will be overridden!")

# Add arguments
parser.add_argument("--locomoid", "-l", type=int, default=0, help="Locomo conversation id")

# Parse arguments
args = parser.parse_args()

from utilities.Locomo import Locomo

from agents.HumanAgent import HumanAgent
from conversations.SingleAgentConversation import SingleAgentConversation
from agents.BaseAgent import BaseAgent

######## Download Locomo dataset (if not done already), extract one conversation and convert it into simple dialogue

name1, name2 = Locomo().conversation(args.locomoid)
conv_name = f"locomo_{args.locomoid}"

# We create a conversation instance
conv = SingleAgentConversation(
    agent=BaseAgent(name1),
    human_agent=HumanAgent(name2),
    conversation_name=conv_name,
    override=False)
conv.start(enact=False)
# If the conversation existed already in output/<name>.yaml, it is replayed first.
# Otherwise, a new conversation is started.
# The conversation is saved in output/<name>.yaml

