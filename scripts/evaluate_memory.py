#!/usr/bin/env python
"""Evaluate a memory-backed agent against a LoCoMo conversation.

Usage:
    python scripts/evaluate_memory.py --agent graph --conv-id 0 --num-questions 50

Pipeline:
    1. Load conversation `conv-id` (index 0-9) from dataset/locomo10.json.
    2. Construct a fresh agent with a unique agent_id; clear any prior
       graph data for that id.
    3. Ingest every turn of every session in order via agent.hear().
       Multimodal turns (with a blip_caption) are appended as a second
       hear() to match how the existing Locomo loader handles them.
    4. After each session, run the linker synchronously over the
       current flash window. Eval bypasses the production threading
       model so the test is deterministic.
    5. Sample `num-questions` questions from categories 1-4 (skip
       category 5 — adversarial wrong-speaker traps need a different
       rubric).
    6. For each question: agent.retrieve(question) -> retrieved text;
       LLM-as-judge call grades it correct/partial/incorrect.
    7. Write a CSV to results/evaluation/<agent>_<sample_id>_<ts>.csv.

Designed agent-agnostic: --agent graph is wired up today; teammates
can extend the AGENT_FACTORIES dict to add their backends.
"""

import argparse
import contextlib
import csv
import json
import math
import os
import random
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Allow running from repo root: src/ is on sys.path via the editable install,
# but if invoked from elsewhere we add it explicitly.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from openai import AzureOpenAI, OpenAI

from agents.GraphAgent import GraphAgent
from graph.connection import make_driver
from utilities.Message import Message


LOCOMO_PATH = REPO_ROOT / "dataset" / "locomo10.json"
RESULTS_DIR = REPO_ROOT / "results" / "evaluation"
JUDGE_MODEL = "gpt-4.1"


# ---------------- progress bar + stdout silencer ----------------

class _NullStream:
    """Discard writes; used by _silenced to muffle base ProcessLike prints
    during ingestion so the progress bar stays clean."""
    def write(self, _): pass
    def flush(self): pass


@contextlib.contextmanager
def _silenced():
    """Suppress any prints inside the block. Restores stdout on exit."""
    old = sys.stdout
    sys.stdout = _NullStream()
    try:
        yield
    finally:
        sys.stdout = old


def _progress(current: int, total: int, label: str = "", suffix: str = "") -> None:
    """Single-line ANSI progress bar that overwrites itself on stdout."""
    width = 30
    pct = (current / total) if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    line = f"\r{label} [{bar}] {current}/{total} {pct*100:5.1f}%  {suffix}"
    sys.stdout.write(line.ljust(120))
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")


# ---------------- agent factories ----------------

def graph_agent_factory(agent_name: str, chat_client, extraction_client, driver):
    """Build a GraphAgent for evaluation.

    agent_name is set to something neither LoCoMo speaker matches so
    both speakers go through extraction (otherwise half the facts
    would be skipped via the assistant-utterance bypass).
    """
    return GraphAgent(
        name=agent_name,
        client=chat_client,
        driver=driver,
        model="gpt-4.1-mini",
        extraction_client=extraction_client,
        extraction_model="gpt-4.1" if extraction_client else None,
    )


AGENT_FACTORIES = {
    "graph": graph_agent_factory,
    # Teammates can register their factories here:
    # "rag": rag_agent_factory,
    # "emotional": emotional_agent_factory,
    # "base": base_agent_factory,
}


# ---------------- LoCoMo loading ----------------

def load_conversation(conv_id: int) -> dict:
    """Load the LoCoMo entry at index conv_id."""
    if not LOCOMO_PATH.exists():
        raise FileNotFoundError(
            f"LoCoMo dataset not found at {LOCOMO_PATH}. "
            "Run once via src/utilities/Locomo.py, or re-download."
        )
    with open(LOCOMO_PATH) as f:
        return json.load(f)[conv_id]


def iter_sessions(conv: dict, max_sessions: int | None = None):
    """Yield (session_key, turns) in temporal order.

    Sessions are keys like 'session_1', 'session_2', ... up to the
    largest numbered one present. _date_time keys are skipped. If
    max_sessions is given, stop after that many sessions.
    """
    session_keys = [
        k for k in conv["conversation"]
        if k.startswith("session_") and not k.endswith("_date_time")
    ]
    # Sort by session number so we ingest in temporal order.
    session_keys.sort(key=lambda k: int(re.match(r"session_(\d+)", k).group(1)))
    if max_sessions is not None:
        session_keys = session_keys[:max_sessions]
    for k in session_keys:
        turns = conv["conversation"].get(k)
        if isinstance(turns, list):
            yield k, turns


def evidence_max_session(q: dict) -> int:
    """Return the highest session number referenced in a question's evidence.

    Evidence items look like 'D<session>:<turn>'. Returns 0 if no
    parseable evidence exists.
    """
    max_s = 0
    for dia in q.get("evidence", []) or []:
        m = re.match(r"D(\d+):", dia)
        if m:
            max_s = max(max_s, int(m.group(1)))
    return max_s


def total_session_count(conv: dict) -> int:
    """Count actual session lists in conv (ignoring date_time keys)."""
    return sum(1 for _ in iter_sessions(conv))


# ---------------- ingestion ----------------

def ingest_conversation(agent, conv: dict, verbose: bool = True, max_sessions: int | None = None):
    """Replay every session of conv into agent, session by session.

    After each session we manually call graph_memory.link() so the
    subconscious linker runs deterministically (instead of relying on
    the background-thread spawn in agent.hear(), which only fires for
    self-utterances — irrelevant here since neither speaker is the
    agent).

    Extraction and linker prints are silenced inside the inner loop so
    they do not scramble the progress bar.
    """
    n_sessions, _, inflated_turns = count_turns(conv, max_sessions=max_sessions)
    total_turns = 0
    session_idx = 0
    for _, turns in iter_sessions(conv, max_sessions=max_sessions):
        session_idx += 1
        for turn in turns:
            with _silenced():
                agent.hear(turn["speaker"], turn["text"])
            total_turns += 1
            # Multimodal turns: existing Locomo.py loader inlines image
            # captions as a second same-speaker turn. Mirror that.
            if "blip_caption" in turn:
                with _silenced():
                    agent.hear(turn["speaker"], f"Here is {turn['blip_caption']}.")
                total_turns += 1
            if verbose:
                _progress(total_turns, inflated_turns,
                          label="Ingestion",
                          suffix=f"session {session_idx}/{n_sessions}")
        # Sync linker pass over the flash window after each session.
        recent = list(agent.flash_memory.get())
        if recent:
            with _silenced():
                agent.graph_memory.link(recent)
    return total_turns


# ---------------- judge ----------------

JUDGE_SYSTEM = """You are an evaluator grading whether a memory-system answer matches the
expected answer for a factual question.

Score using ONLY these labels:
- correct: the retrieved facts contain or clearly imply the expected answer
- partial: the retrieved facts are related and partially correct, but miss
  or distort some of the expected information
- incorrect: the retrieved facts do not support the expected answer at all,
  or are empty

Reply STRICTLY in this format on two lines:
SCORE: <correct|partial|incorrect>
REASON: <one short sentence explaining your verdict>"""


def judge(client, model: str, question: str, expected: str, actual: str) -> tuple[str, str, dict]:
    """LLM-as-judge: return (score_label, reason, usage_dict).

    usage_dict has keys 'prompt', 'completion', 'total' so callers can
    accumulate per-call token cost.
    """
    user_msg = (
        f"Question: {question}\n"
        f"Expected answer: {expected}\n"
        f"Retrieved facts:\n{actual or '(none)'}\n"
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    text = resp.choices[0].message.content or ""

    score = "incorrect"
    reason = ""
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("SCORE:"):
            score_raw = line.split(":", 1)[1].strip().lower()
            if score_raw in {"correct", "partial", "incorrect"}:
                score = score_raw
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()

    usage = {
        "prompt": resp.usage.prompt_tokens,
        "completion": resp.usage.completion_tokens,
        "total": resp.usage.total_tokens,
    }
    return score, reason, usage


SCORE_TO_FLOAT = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


# ---------------- main eval ----------------

def count_turns(conv: dict, max_sessions: int | None = None) -> tuple[int, int, int]:
    """Return (num_sessions, raw_turns, inflated_turns).

    Inflated turns counts blip_caption pseudo-turns the ingestion adds.
    Honors max_sessions when given.
    """
    n_sessions = 0
    raw = 0
    inflated = 0
    for _, turns in iter_sessions(conv, max_sessions=max_sessions):
        n_sessions += 1
        for t in turns:
            raw += 1
            inflated += 1
            if "blip_caption" in t:
                inflated += 1
    return n_sessions, raw, inflated


def print_plan(agent_type, conv, num_questions, agent_name, ts_placeholder,
               extraction_provider, judge_model_name, fraction, max_sessions):
    sample_id = conv["sample_id"]
    speaker_a = conv["conversation"]["speaker_a"]
    speaker_b = conv["conversation"]["speaker_b"]
    total_sessions = total_session_count(conv)
    n_sessions, raw_turns, inflated_turns = count_turns(conv, max_sessions=max_sessions)
    eligible_count = sum(
        1 for q in conv["qa"]
        if q.get("category") in {1, 2, 3, 4}
        and "answer" in q
        and evidence_max_session(q) <= n_sessions
    )
    blip = inflated_turns - raw_turns
    n_questions = min(num_questions, eligible_count)
    total_calls = inflated_turns + n_sessions + n_questions

    sessions_label = f"{n_sessions} of {total_sessions}"
    if fraction < 1.0:
        sessions_label += f"  (fraction {fraction:.2f})"

    print("=" * 60)
    print(f"Evaluation plan")
    print("=" * 60)
    print(f"  Agent:           {agent_type}")
    print(f"  Conversation:    {sample_id} ({speaker_a} ↔ {speaker_b})")
    print(f"  Sessions:        {sessions_label}")
    print(f"  Turns to ingest: {inflated_turns}  ({raw_turns} dialog + {blip} image-caption)")
    print(f"  Questions:       {n_questions} sampled from {eligible_count} eligible "
          f"(cats 1-4; cat 5 skipped; evidence within ingested sessions)")
    print()
    print(f"  LLM calls (approx):")
    print(f"    extractor:   ~{inflated_turns:>4}  ({extraction_provider})")
    print(f"    linker:      ~{n_sessions:>4}  ({extraction_provider})")
    print(f"    judge:       ~{n_questions:>4}  ({judge_model_name})")
    print(f"    total chat:  ~{total_calls:>4}")
    print()
    print(f"  Graph state:")
    print(f"    agent_id '{agent_name}' will be CLEARED before ingestion")
    print()
    print(f"  Output:")
    print(f"    CSV:     results/evaluation/{agent_type}_{sample_id}_{ts_placeholder}.csv")
    print(f"    Summary: results/evaluation/{agent_type}_{sample_id}_{ts_placeholder}_summary.json")
    print("=" * 60)


def evaluate(agent_type: str, conv_id: int, num_questions: int, seed: int = 0,
             assume_yes: bool = False, fraction: float = 1.0):
    if agent_type not in AGENT_FACTORIES:
        raise ValueError(f"--agent must be one of {list(AGENT_FACTORIES)}; got {agent_type!r}")
    if not (0 < fraction <= 1):
        raise ValueError(f"--fraction must be in (0, 1]; got {fraction}")

    conv = load_conversation(conv_id)
    sample_id = conv["sample_id"]
    speaker_a = conv["conversation"]["speaker_a"]
    speaker_b = conv["conversation"]["speaker_b"]
    agent_name = f"eval_{agent_type}_{sample_id}"

    # Compute the session cap for ingestion + question filtering.
    total_sessions = total_session_count(conv)
    max_sessions = max(1, math.ceil(total_sessions * fraction)) if fraction < 1.0 else None
    n_ingested_sessions = max_sessions if max_sessions else total_sessions

    # Decide which providers will be used (preview needs to show this).
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    extraction_provider = "gpt-4.1 via OpenAI" if has_openai else "gpt-4.1-mini via Azure (fallback)"
    judge_model_name = JUDGE_MODEL if has_openai else "gpt-4.1-mini (fallback)"

    print_plan(agent_type, conv, num_questions, agent_name,
               ts_placeholder="<timestamp>",
               extraction_provider=extraction_provider,
               judge_model_name=judge_model_name,
               fraction=fraction,
               max_sessions=max_sessions)

    if not assume_yes:
        reply = input("\nProceed? [y/N]: ").strip().lower()
        if reply not in {"y", "yes"}:
            print("Aborted.")
            return

    # Clients (mirror exampleGraph.py setup).
    chat_client = AzureOpenAI(
        azure_endpoint=os.environ["CHATUIT_BASE_URL"],
        api_key=os.environ["CHATUIT_API_KEY"],
        api_version="2024-02-15-preview",
    )
    extraction_client = None
    if os.environ.get("OPENAI_API_KEY"):
        extraction_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    # Judge runs on the extraction client when available, else the chat
    # client. gpt-4.1 produces more reliable grades than gpt-4.1-mini.
    judge_client = extraction_client or chat_client
    judge_model = JUDGE_MODEL if extraction_client else "gpt-4.1-mini"

    # Fresh agent with a unique agent_id; clear any prior data for it.
    # agent_name was set above (needed by the preview).
    driver = make_driver()
    try:
        with driver.session() as session:
            session.run(
                """
                MATCH (n {agent_id: $agent_id})
                DETACH DELETE n
                """,
                agent_id=agent_name,
            )
        print(f"Cleared prior graph for agent_id={agent_name}")

        factory = AGENT_FACTORIES[agent_type]
        agent = factory(agent_name, chat_client, extraction_client, driver)

        print("Ingesting conversation...")
        total = ingest_conversation(agent, conv, max_sessions=max_sessions)
        print(f"Ingestion complete: {total} turns total ({n_ingested_sessions} sessions)\n")

        # Sample questions: cats 1-4, with answer, AND evidence within the
        # sessions we ingested. Otherwise the agent literally cannot have
        # heard the facts that justify the answer.
        eligible = [
            q for q in conv["qa"]
            if q.get("category") in {1, 2, 3, 4}
            and "answer" in q
            and evidence_max_session(q) <= n_ingested_sessions
        ]
        random.seed(seed)
        sampled = random.sample(eligible, min(num_questions, len(eligible)))
        print(f"Sampled {len(sampled)} questions from {len(eligible)} eligible "
              f"(cats 1-4; evidence within first {n_ingested_sessions} sessions)\n")

        # Run + judge. Track judge token usage per row and accumulate.
        rows = []
        judge_totals = {"prompt": 0, "completion": 0, "total": 0}
        running = {"correct": 0, "partial": 0, "incorrect": 0}
        for i, q in enumerate(sampled, 1):
            question = q["question"]
            expected = q["answer"]
            category = q["category"]

            with _silenced():
                retrieved = agent.retrieve(question)
                score, reason, judge_usage = judge(judge_client, judge_model, question, expected, retrieved)
            for k in judge_totals:
                judge_totals[k] += judge_usage[k]
            running[score] += 1

            _progress(i, len(sampled),
                      label="Questions ",
                      suffix=f"✓{running['correct']} ~{running['partial']} ✗{running['incorrect']}")

            rows.append({
                "agent_type": agent_type,
                "conv_id": sample_id,
                "q_index": i,
                "category": category,
                "question": question,
                "expected": expected,
                "retrieved": retrieved,
                "score": score,
                "score_value": SCORE_TO_FLOAT[score],
                "reason": reason,
                "judge_prompt_tokens": judge_usage["prompt"],
                "judge_completion_tokens": judge_usage["completion"],
                "judge_total_tokens": judge_usage["total"],
            })

        # Persist.
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = RESULTS_DIR / f"{agent_type}_{sample_id}_{ts}.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {out_path}")

        # Aggregate scores.
        score_counts = Counter(r["score"] for r in rows)
        avg = sum(r["score_value"] for r in rows) / len(rows)

        # Pull token usage from each ProcessLike that ran.
        # The agent.retrieve() path does not use chat tokens but it
        # does call the embedding API once per question. Embedding
        # tokens are not tracked (the shared embed_text helper does
        # not expose usage); they are cheap relative to chat tokens
        # (~100x cheaper per token on the same provider).
        def proc_tokens(proc):
            return {
                "prompt": proc.tokens("prompt"),
                "completion": proc.tokens("completion"),
                "total": proc.tokens("total"),
            }
        extractor_tokens = proc_tokens(agent.graph_memory.extraction_process)
        linker_tokens = proc_tokens(agent.graph_memory.link_process)
        grand_total = (
            extractor_tokens["total"]
            + linker_tokens["total"]
            + judge_totals["total"]
        )

        summary = {
            "agent_type": agent_type,
            "conv_id": sample_id,
            "speakers": [speaker_a, speaker_b],
            "fraction": fraction,
            "ingested_sessions": n_ingested_sessions,
            "total_sessions": total_sessions,
            "ingestion_turns": total,
            "num_questions": len(rows),
            "scores": {
                "correct": score_counts["correct"],
                "partial": score_counts["partial"],
                "incorrect": score_counts["incorrect"],
                "average": round(avg, 4),
                "per_category": {
                    str(cat): round(sum(s for s in [r["score_value"] for r in rows if r["category"] == cat]) / sum(1 for r in rows if r["category"] == cat), 4)
                    for cat in sorted({r["category"] for r in rows})
                },
            },
            "tokens": {
                "extractor": extractor_tokens,
                "linker": linker_tokens,
                "judge": judge_totals,
                "grand_total": grand_total,
                "note": "Embedding tokens not counted (embed_text helper does not expose usage; cheap relative to chat tokens).",
            },
            "timestamp": ts,
            "csv_path": str(out_path.name),
        }

        summary_path = out_path.with_suffix("").with_name(out_path.stem + "_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print(f"\n=== Summary ({agent_type} on {sample_id}) ===")
        print(f"  correct:   {score_counts['correct']}")
        print(f"  partial:   {score_counts['partial']}")
        print(f"  incorrect: {score_counts['incorrect']}")
        print(f"  avg score: {avg:.3f} (1.0 perfect, 0.0 all wrong)")
        for cat, score in summary["scores"]["per_category"].items():
            n = sum(1 for r in rows if str(r["category"]) == cat)
            print(f"  cat {cat}: avg {score:.3f} (n={n})")

        print(f"\n=== Token usage ===")
        print(f"  extractor: prompt={extractor_tokens['prompt']:>8d}  completion={extractor_tokens['completion']:>6d}  total={extractor_tokens['total']:>8d}")
        print(f"  linker:    prompt={linker_tokens['prompt']:>8d}  completion={linker_tokens['completion']:>6d}  total={linker_tokens['total']:>8d}")
        print(f"  judge:     prompt={judge_totals['prompt']:>8d}  completion={judge_totals['completion']:>6d}  total={judge_totals['total']:>8d}")
        print(f"  grand total (chat tokens): {grand_total}")
        print(f"  embeddings: not counted (cheap)")
        print(f"\nWrote summary to {summary_path}")
    finally:
        driver.close()


def main():
    parser = argparse.ArgumentParser(description="Evaluate a memory-backed agent against a LoCoMo conversation.")
    parser.add_argument("--agent", "-a", choices=list(AGENT_FACTORIES), default="graph",
                        help="Which agent backend to evaluate.")
    parser.add_argument("--conv-id", "-c", type=int, default=0,
                        help="LoCoMo conversation index (0-9). Default 0 (conv-26).")
    parser.add_argument("--num-questions", "-n", type=int, default=50,
                        help="How many questions to sample (cats 1-4 only).")
    parser.add_argument("--seed", type=int, default=0, help="Sampling seed.")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip the preview confirmation prompt.")
    parser.add_argument("--fraction", "-f", type=float, default=1.0,
                        help="Fraction of the conversation's sessions to ingest, in (0, 1]. "
                             "Defaults to 1.0 (full). 0.25 = first quarter. Questions whose "
                             "evidence falls outside the ingested range are filtered out.")
    args = parser.parse_args()

    evaluate(args.agent, args.conv_id, args.num_questions, args.seed, args.yes, args.fraction)


if __name__ == "__main__":
    main()
