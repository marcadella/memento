import json

from openai import OpenAI
import os

### A script to scan all chat_completion models supported by the server and write to models.json the list of loaded ones.

api_url = os.environ.get("CHATUIT_BASE_URL", "http://127.0.0.1:1234/v1/")
api_key = os.environ.get("CHATUIT_API_KEY", "")

client = OpenAI(base_url=api_url,
                api_key=api_key,
                )
models = [m.id for m in client.models.list().data if m.capabilities["chat_completion"]]
#print(models)


def test_exchange(model):
    # The conversation is NOT propagated.
    # Each call to this function starts with a blank context (except from the system prompt and agent memory)
    client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Hello"},
        ]
    )
    # gpt-4.1-mini is the only accessible model supporting response API
    # r1 = client.responses.create(
    # model = model,
    # input = "Hello"
    # )


models_ok = []
for model in models:
    print(model)
    try:
        test_exchange(model)
        models_ok.append(model)
        print("ok")
    except Exception as e:
        print("failed")

with open("models.json", "w", encoding="utf-8") as f:
    json.dump(models_ok, f, indent=2)