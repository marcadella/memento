


"""
Loads prompt templates from src/prompts/ as plain strings.

Prompts are stored as .md files next to the code that uses them, so they can
be edited as prose, diffed cleanly, and reviewed as we wish.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent/"prompts"


def load_prompt(name: str) -> str:
    """
    Load a prompt template by name.

    Args:
        name: Filename without extension, e.g. "graph_extraction".

    Returns:
        The contents of src/prompts/<name>.md as a string.

    Raises:
        FileNotFoundError: If no such prompt file exists.
    """
    path = PROMPTS_DIR/f"{name}.md"
    return path.read_text(encoding="utf-8")