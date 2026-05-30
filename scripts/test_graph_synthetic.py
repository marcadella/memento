#!/usr/bin/env python
"""Fast, cheap smoke tests for the graph memory pipeline.

Runs short synthetic conversations designed to exercise specific
behaviors of the extractor and (especially) the cross-turn linker.
Each fixture declares the edges that SHOULD exist after ingestion;
the script ingests, triggers the linker, queries the graph, and
reports pass/fail per fixture.

Use this for fast iteration on extraction prompt, linker prompt, or
filter changes. Cost per fixture: ~5-10 LLM calls (gpt-4.1 if
OPENAI_API_KEY is set, otherwise gpt-4.1-mini). Total runtime:
seconds, not minutes.

Usage:
    python scripts/test_graph_synthetic.py

Inspect the test graphs afterward in Neo4j Browser:
    MATCH (n) WHERE n.agent_id STARTS WITH 'test_synth_' RETURN n LIMIT 100

Clean them up:
    MATCH (n) WHERE n.agent_id STARTS WITH 'test_synth_' DETACH DELETE n

Add a new fixture by appending to FIXTURES. Each fixture is just a
name, description, list of (speaker, text) turns, and a list of
expected edges. Head/tail matching is case-insensitive; relation
labels are not checked (LLM-chosen, varies).
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from openai import AzureOpenAI, OpenAI

from agents.GraphAgent import GraphAgent
from graph.connection import make_driver


# ---------------- fixtures ----------------

# Each expected edge: (head, tail, source) where source is 'extractor'
# or 'linker'. Relation label is intentionally not checked since the
# LLM chooses it freely; we only verify that an edge with the given
# endpoints + provenance exists.

FIXTURES = [
    {
        "name": "karaoke_qa",
        "description": (
            "Q-then-A across turns. The song name arrives as a standalone "
            "answer; the per-message extractor cannot link it back to the "
            "speaker. The linker should connect Anna -> Shake it off."
        ),
        "turns": [
            ("Anna", "I love karaoke."),
            ("Bob", "Cool, what's your go-to song?"),
            ("Anna", "Shake it off by Taylor Swift."),
        ],
        "expected": [
            {"head": "Anna", "tail": "karaoke", "source": "extractor"},
            {"head": "Shake it off", "tail": "Taylor Swift", "source": "extractor"},
            {"head": "Anna", "tail": "Shake it off", "source": "linker"},
        ],
    },
    {
        "name": "distributed_entity",
        "description": (
            "Entity introduced in turn 1, its location revealed two turns later. "
            "Extractor cannot connect Anthropic -> San Francisco from the "
            "third turn alone. Linker should fill it in."
        ),
        "turns": [
            ("Anna", "My brother Marcus works at Anthropic."),
            ("Bob", "Cool, where is Anthropic based?"),
            ("Anna", "San Francisco."),
        ],
        "expected": [
            {"head": "Anna", "tail": "Marcus", "source": "extractor"},
            {"head": "Marcus", "tail": "Anthropic", "source": "extractor"},
            {"head": "Anthropic", "tail": "San Francisco", "source": "linker"},
        ],
    },
    {
        "name": "self_contained_message",
        "description": (
            "A single self-contained message with all the inter-entity facts. "
            "Extractor should catch everything; linker should add NOTHING new "
            "(and our pre-check dedup should prevent re-emits)."
        ),
        "turns": [
            ("Anna", "I work at Microsoft in Seattle as a software engineer."),
        ],
        "expected": [
            {"head": "Anna", "tail": "Microsoft", "source": "extractor"},
            {"head": "Microsoft", "tail": "Seattle", "source": "extractor"},
        ],
    },
]


# ---------------- runner ----------------

def query_edges(driver, agent_id: str):
    """Return all :RELATES edges for an agent as (head, rel, tail, source)."""
    with driver.session() as session:
        result = session.run(
            """
            MATCH (h:Entity {agent_id: $aid})-[r:RELATES {agent_id: $aid}]->(t:Entity {agent_id: $aid})
            RETURN h.name AS head, r.type AS relation, t.name AS tail, r.source AS source
            """,
            aid=agent_id,
        )
        return [(r["head"], r["relation"], r["tail"], r["source"]) for r in result]


def find_match(expected: dict, edges: list):
    """Return the first edge matching expected head/tail (case-insensitive)
    and source. None if no match."""
    exp_h = expected["head"].lower()
    exp_t = expected["tail"].lower()
    exp_src = expected["source"]
    for h, r, t, src in edges:
        if h.lower() == exp_h and t.lower() == exp_t and src == exp_src:
            return (h, r, t, src)
    return None


def clear_agent(driver, agent_id: str):
    with driver.session() as session:
        session.run("MATCH (n {agent_id: $aid}) DETACH DELETE n", aid=agent_id)


def run_fixture(fixture: dict, chat_client, extraction_client, driver) -> bool:
    name = fixture["name"]
    agent_id = f"test_synth_{name}"

    print(f"\n=== {name} ===")
    print(f"  {fixture['description']}")

    clear_agent(driver, agent_id)

    # Agent name must not match any speaker in the fixture, so both
    # speakers go through extraction (see GraphAgent.hear() for the
    # assistant-bypass logic). Using agent_id itself as the name
    # guarantees this.
    agent = GraphAgent(
        name=agent_id,
        client=chat_client,
        driver=driver,
        model="gpt-4.1-mini",
        extraction_client=extraction_client,
        extraction_model="gpt-4.1" if extraction_client else None,
    )

    # Ingest.
    for speaker, text in fixture["turns"]:
        agent.hear(speaker, text)

    # Trigger the linker synchronously (the production thread spawn in
    # GraphAgent.hear() only fires on assistant turns, which never
    # happens here since agent.name matches no speaker).
    recent = list(agent.flash_memory.get())
    if recent:
        agent.graph_memory.link(recent)

    edges = query_edges(driver, agent_id)
    n_extractor = sum(1 for _, _, _, s in edges if s == "extractor")
    n_linker = sum(1 for _, _, _, s in edges if s == "linker")
    print(f"  edges in graph: {len(edges)}  ({n_extractor} extractor, {n_linker} linker)")

    # Check expectations.
    passed = 0
    for exp in fixture["expected"]:
        match = find_match(exp, edges)
        if match:
            print(f"  ✓ {match[0]} -[{match[1]}]-> {match[2]}  ({match[3]})")
            passed += 1
        else:
            print(f"  ✗ MISSING: {exp['head']} -[*]-> {exp['tail']}  (expected source={exp['source']})")

    # Show any unexpected edges for context (not failures, just info).
    expected_pairs = {(e["head"].lower(), e["tail"].lower()) for e in fixture["expected"]}
    extras = [(h, r, t, s) for h, r, t, s in edges if (h.lower(), t.lower()) not in expected_pairs]
    if extras:
        print(f"  (additional edges, not part of expectations:)")
        for h, r, t, s in extras:
            print(f"    · {h} -[{r}]-> {t}  ({s})")

    all_passed = passed == len(fixture["expected"])
    print(f"  result: {passed}/{len(fixture['expected'])} expected edges found  {'PASS' if all_passed else 'FAIL'}")
    return all_passed


def main():
    chat_client = AzureOpenAI(
        azure_endpoint=os.environ["CHATUIT_BASE_URL"],
        api_key=os.environ["CHATUIT_API_KEY"],
        api_version="2024-02-15-preview",
    )
    extraction_client = None
    if os.environ.get("OPENAI_API_KEY"):
        extraction_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        print("Using standard OpenAI (gpt-4.1) for extraction + linker.")
    else:
        print("OPENAI_API_KEY not set; falling back to Azure gpt-4.1-mini for extraction + linker.")

    driver = make_driver()
    try:
        passed = sum(run_fixture(f, chat_client, extraction_client, driver) for f in FIXTURES)
        total = len(FIXTURES)
        print(f"\n=== Summary ===")
        print(f"  {passed}/{total} fixtures passed")
        sys.exit(0 if passed == total else 1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
