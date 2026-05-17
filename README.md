# memento

An exploration of agentic memory strategies

## What is this project about

AI agents managing their own memory is a crucial architectural shift that transforms stateless LLMs into stateful, 
autonomous agents capable of learning, recalling events, and maintaining continuity across long-term tasks. 
By giving agents read/write access to a dedicated memory storage, 
they can decide when to store, update, or retrieve information, mimicking a human's ability to take notes and learn from experience.

In this work, we experiment with three types of agentic memory strategies such as:
- RAG-based,
- graph-based,
- self-editing bounded text-based.

We also embed these three types of memory into an agent as sub-conscious processes, and assess how this agent performs compared to a commercial LLM when asked to solve a complex task.

### Concepts

- An **agent** is an entity having the ability to think, memorize, and react to a conversation.
- A **subconscious process** is a process running within an agent in charge of performing internal tasks such as memory access/update.
- A **conversation** is a place where multiple agents talk with each other. Everyone in a conversation hears what everyone else is saying.

### Recommended reading

Very useful resources to get started [here](https://github.com/marcadella/memento/wiki/Literature#must-read).

## Getting started

### Initial setup

- Create the environment: `conda env create -f environment.yml`
- Activate the environment: `conda activate memento`
- Install the package in editable mode.`pip install -e .`. This command needs to be run only once (or each time `pyproject.toml` is modified).
- If you want to use an openAI server, add the needed environment variables to your system (and restart your terminal):
  - `CHATUIT_BASE_URL`
  - `CHATUIT_API_KEY`
- Alternatively, start LM studio server and load whatever model. The expected URL is `http://127.0.0.1:1234/v1`.



#### NEO4j set-up

The graph memory backend uses a local Neo4j database. Each contributor runs
their own instance.

- **Install Neo4j Desktop** from [Webpage](https://neo4j.com/download/).
- **Create a local instance** named `memento` (any name works, but the rest of these instructions assume `memento`).
  - The default username is `neo4j`.
  - Note the password you set.

- **Start the instance** in Neo4j Desktop and confirm it shows as RUNNING.
- **Set the connection environment variables** in your shell config (e.g. `~/.zshrc` or `~/.bashrc`):

  ```bash
    export NEO4J_URI="neo4j://127.0.0.1:7687"
    export NEO4J_USER="neo4j"
    export NEO4J_PASSWORD="your-password"
  ```

Then reload the shell: `source ~/.zshrc`.

- **Initialize the schema:**

```bash
   conda env update -f environment.yml --prune
   conda activate memento
   python scripts/init_neo4j.py
```

The script is idempotent and prints a summary of the constraints and
indexes that were applied. It is safe to re-run after pulling schema
changes.


### Next step

- Don't forget: `conda activate memento`
- Run `python example.py`, which is an example of running a conversation between a human and 2 AI agents.

In case a package added by another contributor to `environment.yml` is missing on your machine, simply run:
- `conda env update -f environment.yml --prune`
- Then: `conda activate memento`

