import os

from openai import OpenAI

api_url = os.environ.get("CHATUIT_BASE_URL", None)
api_key = os.environ.get("CHATUIT_API_KEY", os.environ.get("OPENAI_API_KEY", None))
default_client = OpenAI(base_url=api_url, api_key=api_key)