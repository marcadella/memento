# memento

LLM agents with text-based memory

## What is this project about

AI agents managing their own memory is a crucial architectural shift that transforms stateless LLMs into stateful, 
autonomous agents capable of learning, recalling events, and maintaining continuity across long-term tasks. 
By giving agents read/write access to a dedicated memory storage (in our case Markdown files), 
they can decide when to store, update, or retrieve information, mimicking a human's ability to take notes and learn from experience.

In this work, we experiment with markdown-based memory, and we observe how agents with memory can cooperate and accomplish complex tasks mobilizing concepts
such as:
- **self** / **other**
- **trust**
- **teaching**

and more.

### Concepts

- An **agent** is an entity simulating one person having the ability to think, memorized, and react to a conversation using **processes**.
- A **process** is an LLM based skill.
- A **conversation** is a place where multiple agents talk to each other. Everyone in a conversation hears what everyone else is saying.

### Recommended reading

- [Blog post on text-based memory](https://dev.to/imaginex/ai-agent-memory-management-when-markdown-files-are-all-you-need-5ekk)
- [Example of implementation of agent loop with opanai function API](https://www.aimletc.com/creating-an-ai-agent-with-self-managing-memory/)


## Getting started

### Initial setup

- Create the environment: `conda env create -f environment.yml`
- Activate the environment: `conda activate memento`
- Install the package in editable mode.`pip install -e .`. This command needs to be run only once (or each time `pyproject.toml` is modified).
- If you want to use an openAI server, add the needed environment variables to your system (and restart your terminal):
  - `CHATUIT_BASE_URL`
  - `CHATUIT_API_KEY`
- Alternatively, start LM studio server and load whatever model. The expected URL is `http://127.0.0.1:1234/v1`.

### Next step

- Don't forget: `conda activate memento`
- Run `python example.py`, which is an example of running a conversation between a human and 2 AI agents.

