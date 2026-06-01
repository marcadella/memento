#!/usr/bin/env python

import argparse

parser = argparse.ArgumentParser(description="Example conversation.")

# Add arguments
parser.add_argument("--name", "-n", type=str, default="exampleRAG", help="Conversation name")
parser.add_argument("--enact", action="store_true", help="Set this flag to enact the conversation history (meaning the the AI agents re-generate their parts).")
parser.add_argument("--override", '-x',  action="store_true", help="Set this flag to override an existing conversation.")
parser.add_argument("--model", '-m',  type=str, default="gpt-4.1-mini", help="model to use")
parser.add_argument("--use_open_ai", '-r',  type=str, default="y", help="(Y/n) bool to choose to use open ai models or not")


# Parse arguments
args = parser.parse_args()

from openai import OpenAI
import os

from agents.RAGAgent import RAGAgent
from conversations.SingleAgentConversation import SingleAgentConversation

######### Boilerplate

api_url = os.environ.get("CHATUIT_BASE_URL", "http://127.0.0.1:1234/v1/")
api_key = os.environ.get("CHATUIT_API_KEY", "")


no_list = ["n", "N", "no", "No", "NO", "false", "False", "FALSE"]

if args.use_open_ai in no_list:
    api_url = "http://127.0.0.1:1234/v1/"
    api_key = "dummykey"

client = OpenAI(base_url=api_url,
                api_key=api_key,
                )

model = args.model

########
# We create a conversation instance
conv = SingleAgentConversation(RAGAgent("A", client, model, verbose=False),
                               conversation_name=args.name,
                               override=args.override)
conv.start(enact=args.enact)
# If the conversation existed already in output/<name>.yaml, it is replayed first.
# Otherwise, a new conversation is started.
# The conversation is saved in output/<name>.yaml

