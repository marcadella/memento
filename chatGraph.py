"""Streamlit chat UI for the graph-memory agent.

Run with:
    pip install streamlit pyvis      # one-time setup
    streamlit run chatGraph.py

Interactive chat with a GraphAgent backed by Neo4j, with a live-
updating visualization of the agent's graph memory. After each turn
the agent's subgraph is re-queried from Neo4j and re-rendered via
pyvis. Linker writes happen in a background thread; their results
typically appear on the next refresh.

Independent of exampleGraph.py and the evaluation harness. Uses its
own agent_id namespace (default 'ui_<timestamp>') so live UI graphs
do not collide with example or eval graphs.
"""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import streamlit as st
from openai import AzureOpenAI, OpenAI
from pyvis.network import Network

from agents.GraphAgent import GraphAgent
from graph.connection import make_driver


st.set_page_config(page_title="Graph Memory Chat", layout="wide")


# ---------------- session bootstrap ----------------

def _new_agent_id() -> str:
    return f"ui_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"


def _build_agent(agent_id: str, driver):
    chat_client = AzureOpenAI(
        azure_endpoint=os.environ["CHATUIT_BASE_URL"],
        api_key=os.environ["CHATUIT_API_KEY"],
        api_version="2024-02-15-preview",
    )
    extraction_client = None
    extraction_model = None
    if os.environ.get("OPENAI_API_KEY"):
        extraction_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        extraction_model = "gpt-4.1"
    return GraphAgent(
        name=agent_id,
        client=chat_client,
        driver=driver,
        model="gpt-4.1-mini",
        extraction_client=extraction_client,
        extraction_model=extraction_model,
    )


def _init_session():
    if "driver" not in st.session_state:
        st.session_state.driver = make_driver()
    if "agent_id" not in st.session_state:
        st.session_state.agent_id = _new_agent_id()
    if "agent" not in st.session_state:
        st.session_state.agent = _build_agent(st.session_state.agent_id, st.session_state.driver)
    if "history" not in st.session_state:
        st.session_state.history = []
    if "wide_graph" not in st.session_state:
        st.session_state.wide_graph = False


# ---------------- graph queries + rendering ----------------

def _query_graph(driver, agent_id: str, ent_limit: int = 100, msg_limit: int = 50,
                 recent_n: int | None = None):
    """Return (entities, messages, relates_edges, mentions_edges) for the agent.

    recent_n: if set, return only the N most recently created entities
    (ordered by first_seen DESC) instead of the top-mentions slice.
    """
    with driver.session() as session:
        if recent_n is not None:
            ent_result = session.run(
                """
                MATCH (e:Entity {agent_id: $aid})
                RETURN e.name AS name, coalesce(e.mention_count, 1) AS mentions
                ORDER BY e.first_seen DESC
                LIMIT $limit
                """,
                aid=agent_id, limit=recent_n,
            )
        else:
            ent_result = session.run(
                """
                MATCH (e:Entity {agent_id: $aid})
                RETURN e.name AS name, coalesce(e.mention_count, 1) AS mentions
                ORDER BY mentions DESC
                LIMIT $limit
                """,
                aid=agent_id, limit=ent_limit,
            )
        entities = [(r["name"], int(r["mentions"])) for r in ent_result]
        ent_names = {n for n, _ in entities}

        msg_result = session.run(
            """
            MATCH (m:Message {agent_id: $aid})
            RETURN m.id AS id, m.speaker AS speaker, m.content AS content,
                   m.timestamp AS ts
            ORDER BY m.timestamp DESC
            LIMIT $limit
            """,
            aid=agent_id, limit=msg_limit,
        )
        messages = [
            (r["id"], r["speaker"] or "?", r["content"] or "", r["ts"])
            for r in msg_result
        ]
        msg_ids = {mid for mid, *_ in messages}

        relates_result = session.run(
            """
            MATCH (h:Entity {agent_id: $aid})-[r:RELATES {agent_id: $aid}]->(t:Entity {agent_id: $aid})
            RETURN h.name AS head,
                   t.name AS tail,
                   r.type AS relation,
                   coalesce(r.source, 'extractor') AS source
            LIMIT 500
            """,
            aid=agent_id,
        )
        relates_edges = [
            (r["head"], r["tail"], r["relation"], r["source"])
            for r in relates_result
            if r["head"] in ent_names and r["tail"] in ent_names
        ]

        mentions_result = session.run(
            """
            MATCH (m:Message {agent_id: $aid})-[:MENTIONS]->(e:Entity {agent_id: $aid})
            RETURN m.id AS mid, e.name AS ename
            LIMIT 1000
            """,
            aid=agent_id,
        )
        mentions_edges = [
            (r["mid"], r["ename"])
            for r in mentions_result
            if r["mid"] in msg_ids and r["ename"] in ent_names
        ]
    return entities, messages, relates_edges, mentions_edges


def _render_graph_html(entities, messages, relates_edges, mentions_edges,
                       show_entities: bool = True,
                       show_messages: bool = True,
                       edge_source: str = "all") -> str:
    """Build a pyvis graph and return its HTML as a string.

    show_entities: render :Entity nodes and :RELATES edges.
    show_messages: render :Message nodes.
    edge_source:  'all' | 'extractor' | 'linker' filter on :RELATES.
    :MENTIONS edges render only when both nodes types are visible.
    """
    net = Network(height="540px", width="100%", bgcolor="#ffffff",
                  font_color="#111", directed=True)
    net.barnes_hut(spring_length=160, gravity=-12000)

    if show_entities:
        for name, mentions in entities:
            size = 24 + min(50, mentions * 4)
            net.add_node(
                f"e::{name}", label=name, size=size,
                color={"background": "#f5a742", "border": "#9c5e00",
                       "highlight": {"background": "#ffc070", "border": "#9c5e00"}},
                borderWidth=3, borderWidthSelected=5,
                font={"size": 50, "color": "#111", "face": "arial", "strokeWidth": 0, "bold": True},
                shape="dot",
                title=f"Entity: {name} (mentions={mentions})",
                nodeType="entity", entityName=name, mentionCount=mentions,
            )

    if show_messages:
        for mid, speaker, content, _ts in messages:
            short = content if len(content) <= 40 else content[:37] + "..."
            label = f"[{speaker}] {short}"
            net.add_node(
                f"m::{mid}", label=label, size=12,
                color={"background": "#cfe2f3", "border": "#1f6fa5"},
                borderWidth=2,
                font={"size": 28, "color": "#222"},
                shape="box",
                title=f"Message by {speaker}\n\n{content}",
                nodeType="message", speaker=speaker, contentFull=content,
                messageId=mid, ts=str(_ts) if _ts is not None else "",
            )

    if show_entities:
        for head, tail, relation, source in relates_edges:
            if edge_source != "all" and source != edge_source:
                continue
            color = "#1f78b4" if source == "extractor" else "#d62728"
            net.add_edge(
                f"e::{head}", f"e::{tail}", label=relation, color=color,
                title=f"{relation} (source={source})",
                font={"size": 34, "align": "middle", "color": "#111",
                      "strokeWidth": 8, "strokeColor": "#ffffff", "bold": True},
                arrows={"to": {"enabled": True, "scaleFactor": 1.2}},
                width=3.5, selectionWidth=5,
                edgeType="relates", headName=head, tailName=tail,
                relationName=relation, edgeSource=source,
            )

    if show_entities and show_messages:
        for mid, ename in mentions_edges:
            net.add_edge(
                f"m::{mid}", f"e::{ename}",
                color={"color": "#555555", "opacity": 0.9},
                title="mentions", dashes=[6, 6], width=2,
                arrows={"to": {"enabled": True, "scaleFactor": 0.6}},
                edgeType="mentions", messageId=mid, entityName=ename,
            )

    try:
        html = net.generate_html(notebook=False)
    except AttributeError:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as tmp:
            tmp_path = tmp.name
        net.write_html(tmp_path, notebook=False)
        with open(tmp_path) as f:
            html = f.read()
        os.unlink(tmp_path)

    # Fix the initial-placement RNG so the same graph always lays out
    # the same way. Lets the user toggle filters and come back to a
    # familiar layout instead of a freshly shuffled one.
    html = html.replace(
        "var options = {",
        'var options = {"layout":{"randomSeed":42},',
        1,
    )

    # Click-to-inspect info box. Pure client-side, no Streamlit round-trip.
    click_handler = """
<script>
(function() {
    function attach() {
        if (typeof network === 'undefined' || typeof nodes === 'undefined' || typeof edges === 'undefined') {
            setTimeout(attach, 50);
            return;
        }
        var container = document.getElementById('mynetwork');
        if (container && getComputedStyle(container).position === 'static') {
            container.style.position = 'relative';
        }
        var box = document.createElement('div');
        box.id = 'graph-info-box';
        box.style.cssText = 'position:absolute;display:none;background:#fff;border:1px solid #444;border-radius:6px;padding:10px 14px;font-family:Arial,sans-serif;font-size:13px;color:#111;box-shadow:0 2px 10px rgba(0,0,0,0.2);max-width:320px;z-index:1000;line-height:1.45;';
        container.appendChild(box);

        function esc(s) {
            return String(s == null ? '' : s).replace(/[&<>\"']/g, function(c) {
                return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
            });
        }
        function show(html, pos) {
            box.innerHTML = html +
                '<div style="text-align:right;margin-top:8px;">' +
                '<a href="#" id="graph-info-close" style="color:#888;text-decoration:none;font-size:12px;">close</a></div>';
            var w = box.offsetWidth || 320, h = box.offsetHeight || 120;
            var maxX = container.clientWidth - w - 4;
            var maxY = container.clientHeight - h - 4;
            box.style.left = Math.max(4, Math.min(maxX, pos.x + 14)) + 'px';
            box.style.top = Math.max(4, Math.min(maxY, pos.y + 14)) + 'px';
            box.style.display = 'block';
            document.getElementById('graph-info-close').onclick = function(e) {
                e.preventDefault(); box.style.display = 'none';
            };
        }

        network.on('click', function(params) {
            if (params.nodes.length > 0) {
                var n = nodes.get(params.nodes[0]);
                var html;
                if (n.nodeType === 'entity') {
                    html = '<b>Entity</b><br><b>name:</b> ' + esc(n.entityName) +
                           '<br><b>mention count:</b> ' + esc(n.mentionCount);
                } else if (n.nodeType === 'message') {
                    html = '<b>Message</b><br><b>speaker:</b> ' + esc(n.speaker) +
                           '<br><b>content:</b><br><i>' + esc(n.contentFull) + '</i>' +
                           (n.ts ? '<br><b>timestamp:</b> ' + esc(n.ts) : '') +
                           '<br><b>id:</b> <code>' + esc(n.messageId) + '</code>';
                } else {
                    html = '<b>Node</b><br>' + esc(n.label || n.id);
                }
                show(html, params.pointer.DOM);
            } else if (params.edges.length > 0) {
                var e = edges.get(params.edges[0]);
                var html;
                if (e.edgeType === 'relates') {
                    var srcLabel = e.edgeSource === 'linker' ? 'linker (subconscious cross-turn)' : 'extractor (per-message)';
                    html = '<b>:RELATES</b><br><b>head:</b> ' + esc(e.headName) +
                           '<br><b>relation:</b> ' + esc(e.relationName) +
                           '<br><b>tail:</b> ' + esc(e.tailName) +
                           '<br><b>source:</b> ' + esc(srcLabel);
                } else if (e.edgeType === 'mentions') {
                    html = '<b>:MENTIONS</b><br>' +
                           '<b>message id:</b> <code>' + esc(e.messageId) + '</code>' +
                           '<br><b>entity:</b> ' + esc(e.entityName);
                } else {
                    html = '<b>Edge</b>';
                }
                show(html, params.pointer.DOM);
            } else {
                box.style.display = 'none';
            }
        });
    }
    attach();
})();
</script>
"""
    return html.replace("</body>", click_handler + "</body>")


# ---------------- ops ----------------

def _token_summary(agent) -> dict:
    out = {}
    for label, proc in (
        ("react", agent.react_process),
        ("extractor", agent.graph_memory.extraction_process),
        ("linker", agent.graph_memory.link_process),
    ):
        out[label] = {
            "prompt": proc.tokens("prompt"),
            "completion": proc.tokens("completion"),
            "total": proc.tokens("total"),
        }
    return out


def _clear_graph_for_agent(driver, agent_id: str):
    with driver.session() as session:
        session.run("MATCH (n {agent_id: $aid}) DETACH DELETE n", aid=agent_id)


# ---------------- UI ----------------

def main():
    _init_session()
    agent = st.session_state.agent

    with st.sidebar:
        st.header("Session")
        st.code(st.session_state.agent_id, language=None)
        st.text(f"Turns: {len(st.session_state.history)}")

        if st.button("Refresh graph", use_container_width=True,
                     help="Re-query Neo4j without sending a message. Useful when the linker is still writing in the background."):
            st.rerun()

        if st.button("New session (fresh agent)", use_container_width=True):
            st.session_state.agent_id = _new_agent_id()
            st.session_state.agent = _build_agent(st.session_state.agent_id, st.session_state.driver)
            st.session_state.history = []
            st.rerun()

        with st.expander("Clear this agent's graph"):
            st.caption("Drops all nodes/edges with this agent_id from Neo4j. The conversation history in the UI is kept.")
            if st.button("Clear graph", type="primary", use_container_width=True):
                _clear_graph_for_agent(st.session_state.driver, st.session_state.agent_id)
                st.success("Cleared.")
                st.rerun()

        st.divider()
        st.subheader("Tokens (cumulative)")
        toks = _token_summary(agent)
        total = sum(t["total"] for t in toks.values())
        for label, t in toks.items():
            st.text(f"{label:>9}: {t['total']:>6}  (p={t['prompt']} c={t['completion']})")
        st.text(f"{'total':>9}: {total:>6}")

    chat_ratio, graph_ratio = (0.35, 2) if st.session_state.wide_graph else (1, 1)
    col_chat, col_graph = st.columns([chat_ratio, graph_ratio])

    with col_chat:
        st.subheader("Chat")
        chat_box = st.container(height=600)
        with chat_box:
            for msg in st.session_state.history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

    with col_graph:
        st.subheader("Graph memory")
        graph_col, filter_col = st.columns([3.5, 1])

        with filter_col:
            wide_label = "Compact view" if st.session_state.wide_graph else "Wide view"
            if st.button(wide_label, use_container_width=True,
                         help="Shrink the chat column so the graph gets more horizontal space."):
                st.session_state.wide_graph = not st.session_state.wide_graph
                st.rerun()
            st.markdown("**View**")
            view_mode = st.radio(
                "view", ["All", "Entities only", "Messages only"],
                index=0, label_visibility="collapsed",
            )
            st.markdown("**Edge source**")
            edge_source = st.radio(
                "edge_source", ["All", "Extractor", "Linker"],
                index=0, label_visibility="collapsed",
                help="Filter :RELATES edges by their origin. :MENTIONS edges are not affected.",
            )
            st.markdown("**Recent entities**")
            recent_choice = st.radio(
                "recent", ["All", "1", "3", "5", "7"],
                index=0, label_visibility="collapsed",
                help="Show only the N most recently created entities (sorted by first_seen).",
            )
            st.divider()
            st.caption(
                "**Nodes**  \n"
                "🟠 Entity  \n"
                "🟦 Message  \n\n"
                "**Edges**  \n"
                "🟦 extractor  \n"
                "🟥 linker  \n"
                "▫ dashed = :MENTIONS"
            )

        show_entities = view_mode in ("All", "Entities only")
        show_messages = view_mode in ("All", "Messages only")
        edge_source_key = edge_source.lower()
        recent_n = None if recent_choice == "All" else int(recent_choice)

        with graph_col:
            entities, messages, relates_edges, mentions_edges = _query_graph(
                st.session_state.driver, st.session_state.agent_id,
                recent_n=recent_n,
            )
            renderable = (show_entities and entities) or (show_messages and messages)
            if renderable:
                html = _render_graph_html(
                    entities, messages, relates_edges, mentions_edges,
                    show_entities=show_entities,
                    show_messages=show_messages,
                    edge_source=edge_source_key,
                )
                st.components.v1.html(html, height=560)
            else:
                st.info("Nothing to show with the current filters. Start chatting or change the view.")
            n_ext = sum(1 for _, _, _, s in relates_edges if s == "extractor")
            n_link = sum(1 for _, _, _, s in relates_edges if s == "linker")
            st.caption(
                f"{len(entities)} entities · {len(relates_edges)} :RELATES "
                f"({n_ext} extractor, {n_link} linker) · "
                f"{len(messages)} messages · {len(mentions_edges)} :MENTIONS"
            )

    # Streamlit auto-pins a top-level chat_input to the bottom of the page.
    if user_input := st.chat_input("Type a message..."):
        st.session_state.history.append({"role": "user", "content": user_input})
        # Render the new turn into chat_box live so the user sees their
        # message + a typing indicator the instant they hit Enter. All
        # blocking LLM calls happen inside the spinner block.
        with chat_box:
            with st.chat_message("user"):
                st.write(user_input)
            with st.chat_message("assistant"):
                with st.spinner("..."):
                    agent.hear("user", user_input)  # sync extraction
                    reply = agent.speak()           # sync chat generation
                st.write(reply)
        st.session_state.history.append({"role": "assistant", "content": reply})
        # Broadcast reply to the agent (skips extraction for assistant,
        # spawns the subconscious linker daemon thread). Linker results
        # may not appear in the graph this rerun but will by the next.
        agent.hear(agent.name, reply)
        st.rerun()


if __name__ == "__main__":
    main()
