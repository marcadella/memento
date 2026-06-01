# Memento Graph UI: Tutorial

A step-by-step guide to installing the Memento project from scratch and
running the **graph-memory chat UI**, where you can converse with an AI
agent and watch its knowledge graph build itself in real time as the
conversation progresses.

This tutorial assumes you have no prior setup. It walks through every
dependency.

---

## What you will be running

A Streamlit web app that opens in your browser at
`http://localhost:8501`. The screen is split in two:

- **Left panel:** a normal chat interface. You type, the agent replies.
- **Right panel:** a live, interactive visualization of the agent's
  knowledge graph stored in a local Neo4j database. As you chat, new
  entity nodes and relationship edges appear. A sub-conscious
  background process also adds cross-turn connections that the agent
  noticed only by reflecting on the recent dialogue.

The goal of the demo is to see graph-based memory evolve in real time,
not just hear an agent answer.

---

## Prerequisites

You will need:

1. **Git**, to clone the repository.
2. **Anaconda or Miniconda**, to manage the Python environment.
   Download from <https://www.anaconda.com/download/> if you do not
   have it.
3. **Neo4j Desktop**, the database the graph memory is stored in.
   Download from <https://neo4j.com/download/>. Free for personal /
   academic use; registration is required.
4. **An OpenAI API key**, since the agent and the graph extractor call
   GPT models. Get one from <https://platform.openai.com/api-keys> if
   you do not already have one. A few US dollars of credit is enough
   to comfortably test the demo.

The instructions below assume **macOS or Linux**. On Windows, replace
shell commands with their PowerShell equivalents (`export` becomes
`$Env:`, paths use backslashes, etc.).

---

## Step 1: Clone the repository

Open a terminal and clone the project to a folder of your choice:

```bash
git clone https://github.com/marcadella/memento.git
cd memento
```

All commands in the rest of this tutorial assume you are inside the
`memento` directory.

---

## Step 2: Install Neo4j Desktop

The graph memory is stored in a local Neo4j database, so you need to
have a Neo4j instance running on your machine before launching the
chat UI.

1. Download Neo4j Desktop from <https://neo4j.com/download/>.
2. Install and launch it. The first launch may prompt you to register
   for a free account; accept and continue.
3. Once Neo4j Desktop opens, you will see a dashboard listing
   "Instances" (initially empty).

---

## Step 3: Create a Neo4j instance

Inside Neo4j Desktop:

1. Click **"New" → "Local DBMS"** (or **"Create instance"**, depending
   on your Desktop version).
2. Give the instance a name. The rest of this tutorial assumes the
   name **`memento`**. You can pick anything, but you will then need
   to mentally substitute that name everywhere `memento` appears
   below.
3. Set a password and **write it down**. You will need it in a
   moment.
4. Click **Create**.
5. Once the instance is created, click **Start**. Wait until its
   status changes to **RUNNING** (a green dot).

The default connection settings (which you do not need to change) are:

- Host: `127.0.0.1`
- Bolt port: `7687`
- Username: `neo4j`

---

## Step 4: Set up the Python environment

Open a terminal in the `memento` repository directory.

Create and activate the conda environment defined by the project:

```bash
conda env create -f environment.yml
conda activate memento
```

This installs Python 3.12, the OpenAI SDK, the Neo4j Python driver,
Streamlit, pyvis, and a few small utilities. Expect the install to
take a couple of minutes the first time.

Then install the project itself in editable mode (this only needs to
be done once):

```bash
pip install -e .
```

---

## Step 5: Set environment variables

The agent needs three pieces of information from your shell
environment:

- **Where the Neo4j database lives** and how to authenticate.
- **Which OpenAI account to bill** for the chat and extraction calls.

Edit your shell config file (`~/.zshrc` on macOS with zsh, or
`~/.bashrc` on most Linux distributions) and add these lines at the
bottom, replacing `<your-password>` and `<your-openai-key>` with the
real values:

```bash
# Neo4j connection
export NEO4J_URI="neo4j://127.0.0.1:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="<your-password>"

# OpenAI account
export OPENAI_API_KEY="<your-openai-key>"
```

After saving the file, reload your shell so the new variables take
effect:

```bash
source ~/.zshrc      # or `source ~/.bashrc` on Linux
conda activate memento
```

The `conda activate memento` line is needed because sourcing the
shell config deactivates the environment.

Verify the variables are now set:

```bash
echo $NEO4J_URI                # should print neo4j://127.0.0.1:7687
echo $NEO4J_USER               # should print neo4j
echo ${NEO4J_PASSWORD:+set}    # should print "set" (without revealing the password)
echo ${OPENAI_API_KEY:+set}    # should print "set"
```

If any of these print blank, double-check that you saved the right
file and re-ran `source`.

---

## Step 6: Initialize the Neo4j schema

The graph memory has a specific schema (constraints + vector indexes)
that needs to exist in Neo4j before the chat UI can write to it. A
one-off setup script applies them:

```bash
python scripts/init_neo4j.py
```

The script is idempotent: re-running it does no harm. You should see
output confirming that the constraints and the two vector indexes
were created (or already existed).

If you see an error like
`08N09: Connection exception - database unavailable`, the Neo4j
**instance** is running but the **database inside it** is stopped.
This happens occasionally with Neo4j Desktop. To fix it:

1. In Neo4j Desktop, click the **Query** button (or "Open" → "Neo4j
   Browser") to open the browser-based query tool.
2. At the top of the query view, switch the active database from
   `neo4j` to `system`.
3. Run the following Cypher command in the query input:

   ```cypher
   START DATABASE neo4j
   ```

4. Switch back to the `neo4j` database. The connection should now
   work. Re-run `python scripts/init_neo4j.py`.

---

## Step 7: Launch the chat UI

You are now ready to run the demo:

```bash
streamlit run chatGraph.py
```

A browser tab should open automatically at <http://localhost:8501>.
If it does not, copy and paste that address into your browser.

You should see a two-panel layout:

- **Left:** a chat input field at the bottom and an empty chat
  history above it.
- **Right:** an empty graph area (because nothing has been said yet)
  and a vertical filter panel.
- **Sidebar (far left):** the current session's `agent_id` (something
  like `ui_2026-06-01_14-30-22`), session controls, and a token
  usage counter.

---

## How to use the demo

Type a message in the chat input at the bottom and press Enter.

While the agent is composing its reply, an animated indicator appears
inside an assistant chat bubble. Behind the scenes, three things
happen in this order:

1. The **extractor** reads your message and stores factual triples
   into the graph (you see this immediately as new nodes and edges
   appear in the right panel).
2. The agent generates and displays its reply.
3. The **sub-conscious linker** runs in the background to add
   cross-turn connections.

After a turn, the graph panel refreshes. If the linker added new
edges (drawn in red, vs blue for extractor edges), they may appear
the *next* time you send a message, since the linker runs
asynchronously. You can also click the **Refresh graph** button in
the left sidebar to re-query Neo4j without sending a new message.

### Things to try

- Tell the agent your name and a few facts about yourself, e.g.
  *"My name is Alice. I live in Bergen. I love hiking and Norwegian
  jazz."* Watch four orange entity nodes appear (Alice, Bergen,
  hiking, Norwegian jazz) with relation edges between them.
- Ask the agent a question that uses what it has been told, e.g.
  *"What did I tell you I love?"*. Behind the scenes, the agent
  queries the graph and answers from its retrieved memory.
- Use the **filter panel** beside the graph to switch the view
  between entities only, messages only, or both, and to filter
  edges by source (extractor vs linker).
- Use the **Wide view** toggle to give the graph more horizontal
  space, useful as the graph grows.
- Click any node or edge in the graph to see its full details in a
  small info box.

### Ending and resuming

When you are done, simply close the browser tab and stop the
Streamlit process in the terminal with `Ctrl-C`. The agent's data
remains in Neo4j (under the session's `ui_<timestamp>` agent_id).

To start a fresh session next time, just launch
`streamlit run chatGraph.py` again. The sidebar shows a "New
session" button if you want to clear the chat in the middle of a
run, and a "Clear this agent's graph" button to wipe the current
session's data from Neo4j.

---

## Common issues

**"OPENAI_API_KEY not set" or HTTP 401 errors.**
The shell that launched Streamlit did not see the OpenAI key. Quit
Streamlit (`Ctrl-C`), re-run `source ~/.zshrc` and
`conda activate memento`, then `streamlit run chatGraph.py` again.

**"Connection refused" against Neo4j.**
Open Neo4j Desktop and confirm the `memento` instance is **RUNNING**.
If it is, also check that the `neo4j` database inside it has not
stopped itself (see the troubleshooting note in Step 6).

**Browser tab does not open automatically.**
Open <http://localhost:8501> manually.

**Graph appears blank after several turns.**
Click the **Refresh graph** button in the left sidebar. The graph
queries Neo4j only when the page refreshes, so a slow linker call
may delay updates until the next interaction.

**Old data from previous sessions clutters the graph.**
The graph viewer is scoped to the current session's `ui_<timestamp>`
agent_id, so it should only show that session's data. If you want to
remove old data from Neo4j entirely, open Neo4j Browser, switch to
the `neo4j` database, and run:

```cypher
MATCH (n) DETACH DELETE n
```

This wipes all nodes and edges but preserves the schema; you do not
need to re-run `init_neo4j.py` afterwards.
