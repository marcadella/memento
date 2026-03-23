from openai import OpenAI
import os
import json

# The following is an adaptation of https://www.aimletc.com/creating-an-ai-agent-with-self-managing-memory/

api_url = os.environ.get("CHATUIT_BASE_URL", "http://127.0.0.1:1234/v1/")
api_key = os.environ.get("CHATUIT_API_KEY", "")
model = "gpt-4.1" # Not used if using LM studio

client = OpenAI(base_url=api_url,
                api_key=api_key
                )

system_prompt = ("You are a useful chat agent helping the user to remember facts."
                 "When he tells you things, store them using `save_to_memory` tool."
                 "Answer his questions using the information you find in the `Memory` section.")
agent_memory = {}

def memory_prompt(memory_dict):
    memorized_items = [f"- {k}: {v}" for k, v in memory_dict.items()]
    return f"\n\n## Memory\n\n{"\n".join(memorized_items)}"

def save_to_memory(key, value):
    # What to do if already exists?
    agent_memory[key] = value

fn = {
    "type": "function",
    "function": {
        "name": "save_to_memory",
        "description": "Save key-value pairs to memory",
        "parameters": {
            "type": "object",
            "properties": {
               "key": {
                    "type": "string",
                    "description": "Key used for later retrieval of information. It should be one keyword describing the nature of the associated information (and not contain the piece of information itself)."
                },
                "value": {
                    "type": "string",
                    "description": "Piece of information to store"
                }
            },
            "required": ["key", "value"]
        }
    }
}

def standalone_exchange(user_prompt):
    # The conversation is NOT propagated.
    # Each call to this function starts with a blank context (except from the system prompt and agent memory)
    chat = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt + memory_prompt(agent_memory)},
            {"role": "user", "content": user_prompt}, # also supports "name" attribute to distinguish multiple entities having the same role.
        ],
        tools=[fn]
    )
    response = chat.choices[0]
    print(response.message.content)

    for tool_call in response.message.tool_calls:
        function = tool_call.function
        if function.name == "save_to_memory":
            print(f"Calling {function.name} function")
            save_to_memory(**json.loads(function.arguments))
            print(f"\n***** Memory content *****{memory_prompt(agent_memory)}\n**********")

standalone_exchange("Hei, what's up?")
standalone_exchange("My name is Albert Rotchfeld.")
standalone_exchange("What is my name?")
