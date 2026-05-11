
from openai import OpenAI, AzureOpenAI


EMBEDDING_MODEL = "text-embedding-3-small"

# Embedding helpers for memory backends. Seems like ChatUiT uses Azure to wrap Openai
def embed_text(client: OpenAI|AzureOpenAI, text: str, model: str = EMBEDDING_MODEL) -> list[float]:
    """
    Compute an embedding for a single piece of text.

    Args:
        client: An OpenAI or AzureOpenAI client.
        text: The text to embed. Must be non-empty.
        model: Model name (OpenAI) or deployment name (Azure).

    Returns:
        A list of floats. 1536 long for text-embedding-3-small.

    Raises:
        ValueError: If text is empty or whitespace-only.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    response = client.embeddings.create(model=model, input=text)
    return response.data[0].embedding

