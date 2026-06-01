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
- pictorial-based.

### Video

https://filedn.com/lIFJC8ES6odhW7qS8AxmmHY/memento.mp4
and one video file in videos folder

## Getting started

### Initial setup

- Create the environment: `conda env create -f environment.yml`
- Activate the environment: `conda activate memento`
- Install the package in editable mode.`pip install -e .`. This command needs to be run only once (or each time `pyproject.toml` is modified).
- If you want to use an openAI server, add the needed environment variables to your system (and restart your terminal):
  - `CHATUIT_BASE_URL`
  - `CHATUIT_API_KEY`
- Alternatively, start LM studio server and load whatever model. The expected URL is `http://127.0.0.1:1234/v1`.
- 

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


#### NEO4j Troubleshooting

**Error `08N09: Connection exception - database unavailable` (or Python equivalent).**

The Neo4j instance is running but the `neo4j` database inside it has been stopped. The
instance and the databases inside it are managed separately. Desktop's UI does not always
expose database start/stop controls clearly, so use Neo4j Browser instead:
  1. In Desktop, click **Query** to open Neo4j Browser.
  2. At the top of the query view, switch the active database from `neo4j`
     to `system` (the `system` database manages database lifecycle).
  3. Run:

  ```cypher
    START DATABASE neo4j
  ```

  4. Switch back to `neo4j` and confirm with `RETURN 1`.



### Graph memory dev tools

Three helper scripts in `scripts/` for development:

- `python scripts/test_graph_memory.py` — populate the graph with 4 sample messages under `agent_id="TestAgent"`.
- `python scripts/test_graph_retrieval.py` — run sample queries against `TestAgent`. Requires running `test_graph_memory.py` first.
- `python scripts/clear_graph.py --agent-id TestAgent` — clear data for one agent.
- `python scripts/clear_graph.py --all` — clear everything (asks for typed `yes` confirmation).

Schema is preserved across clears.


### Graph memory chat UI

A Streamlit + pyvis demo for chatting with the graph-memory agent and
watching its Neo4j subgraph update turn-by-turn. Launch:

```bash
conda activate memento
streamlit run chatGraph.py
```

Opens at http://localhost:8501. The left pane is a chat interface; the
right pane renders the agent's entity-relation graph (orange circles
are entities, light-blue boxes are messages, blue edges are
extractor-written, red edges are linker-written). The right-side
filter panel lets you toggle node types, edge sources, and the
"recent N" entity view. Each session runs under its own
`ui_<timestamp>` agent_id so it does not collide with other agents
in Neo4j.

Streamlit and pyvis are installed by `environment.yml`. If you pulled
the branch before they were added, run `conda env update -f environment.yml --prune`
to get them.


### Next step

- Don't forget: `conda activate memento`
- Run `python converse_with_flash_agent.py`, which is an example of running a conversation between a human and an AI agents.

In case a package added by another contributor to `environment.yml` is missing on your machine, simply run:
- `conda env update -f environment.yml --prune`
- Then: `conda activate memento`

