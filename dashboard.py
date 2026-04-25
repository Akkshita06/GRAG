"""
RepoGraph — Streamlit Comparison Dashboard
Run: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import time
import json
from pipelines import pipeline_baseline, pipeline_graphrag, score_answer, BENCHMARK_QUESTIONS

st.set_page_config(
    page_title="RepoGraph — GraphRAG vs Baseline",
    page_icon="🔬",
    layout="wide",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
    border: 1px solid #e9ecef;
}
.metric-label { font-size: 12px; color: #6c757d; margin-bottom: 4px; }
.metric-value { font-size: 26px; font-weight: 600; color: #212529; }
.win-badge {
    background: #d1fae5; color: #065f46;
    border-radius: 6px; padding: 2px 10px;
    font-size: 12px; font-weight: 600;
}
.answer-box {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 16px;
    min-height: 200px;
    font-size: 14px;
    line-height: 1.6;
}
.graph-path-box {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
    padding: 12px;
    font-size: 12px;
    font-family: monospace;
    color: #065f46;
}
.section-header {
    font-size: 13px;
    font-weight: 600;
    color: #6c757d;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────
st.title("RepoGraph")
st.markdown("**GraphRAG vs Baseline LLM** — GitHub ecosystem intelligence")
st.divider()

# ── Sidebar: controls ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("Query")
    mode = st.radio("Question mode", ["Custom question", "Benchmark questions"])

    if mode == "Custom question":
        user_q = st.text_area(
            "Ask anything about GitHub repos",
            value="I know Python and ML. What's the best path to learn web development?",
            height=100,
        )
        run_btn = st.button("Run both pipelines", type="primary", use_container_width=True)
        gt_keywords = st.text_input(
            "Ground truth keywords (comma-sep, optional)",
            value="javascript, react, vue, frontend",
        )
    else:
        selected_q = st.selectbox(
            "Choose benchmark question",
            [q["question"] for q in BENCHMARK_QUESTIONS],
        )
        run_btn = st.button("Run benchmark question", type="primary", use_container_width=True)
        matched = next(q for q in BENCHMARK_QUESTIONS if q["question"] == selected_q)
        gt_keywords = ", ".join(matched["ground_truth_keywords"])

    st.divider()
    st.markdown("**About**")
    st.markdown("""
    - **Pipeline A** — raw question → LLM  
    - **Pipeline B** — TigerGraph multi-hop → LLM  
    - Graph has **30 repos**, **8 edge types**
    """)

    run_full_benchmark = st.button("Run full benchmark (10 Qs)", use_container_width=True)

# ── Session state ──────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = []
if "current" not in st.session_state:
    st.session_state.current = None

# ── Run single query ───────────────────────────────────────────────────────
if run_btn:
    question = user_q if mode == "Custom question" else selected_q
    kw_list = [k.strip() for k in gt_keywords.split(",") if k.strip()]

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<p class="section-header">Pipeline A — Baseline LLM</p>', unsafe_allow_html=True)
        with st.spinner("Calling LLM directly..."):
            t0 = time.time()
            baseline = pipeline_baseline(question)
            baseline["accuracy"] = score_answer(baseline["answer"], kw_list)

    with col_b:
        st.markdown('<p class="section-header">Pipeline B — GraphRAG</p>', unsafe_allow_html=True)
        with st.spinner("Querying TigerGraph → building context → calling LLM..."):
            graphrag = pipeline_graphrag(question)
            graphrag["accuracy"] = score_answer(graphrag["answer"], kw_list)

    st.session_state.current = {
        "question": question,
        "baseline": baseline,
        "graphrag": graphrag,
    }
    st.session_state.results.append(st.session_state.current)

# ── Display current result ─────────────────────────────────────────────────
if st.session_state.current:
    cur = st.session_state.current
    b = cur["baseline"]
    g = cur["graphrag"]

    st.markdown(f"### Q: *{cur['question']}*")
    st.markdown("")

    # Metric row
    cols = st.columns(5)
    metrics = [
        ("Tokens used", b["tokens_total"], g["tokens_total"], "lower"),
        ("Latency (ms)", b["latency_ms"],  g["latency_ms"],   "lower"),
        ("Cost (USD)",  f"${b['cost_usd']:.5f}", f"${g['cost_usd']:.5f}", "lower"),
        ("Accuracy (%)", b["accuracy"],    g["accuracy"],     "higher"),
        ("Graph nodes", "—", g.get("graph_stats", {}).get("nodes_retrieved", "—"), "info"),
    ]

    for col, (label, bval, gval, better) in zip(cols, metrics):
        with col:
            try:
                bnum, gnum = float(str(bval).replace("$","")), float(str(gval).replace("$",""))
                if better == "lower":
                    winner = "B wins" if gnum < bnum else "A wins"
                    pct = round(abs(bnum - gnum) / max(bnum, 0.0001) * 100)
                    badge = f"{'GraphRAG' if gnum < bnum else 'Baseline'} -{pct}%"
                else:
                    winner = "B wins" if gnum > bnum else "A wins"
                    badge = f"GraphRAG +{round(gnum - bnum, 1)}%" if gnum > bnum else ""
            except Exception:
                badge = ""

            st.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">{label}</div>
              <div style="display:flex;justify-content:space-around;margin-top:6px">
                <div>
                  <div style="font-size:11px;color:#adb5bd">Baseline</div>
                  <div class="metric-value" style="font-size:20px">{bval}</div>
                </div>
                <div>
                  <div style="font-size:11px;color:#adb5bd">GraphRAG</div>
                  <div class="metric-value" style="font-size:20px;color:#0d9488">{gval}</div>
                </div>
              </div>
              {f'<div style="margin-top:8px"><span class="win-badge">{badge}</span></div>' if badge else ""}
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")

    # Side-by-side answers
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Pipeline A — Baseline LLM answer**")
        st.markdown(f'<div class="answer-box">{b["answer"]}</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown("**Pipeline B — GraphRAG answer**")
        st.markdown(f'<div class="answer-box">{g["answer"]}</div>', unsafe_allow_html=True)
        if g.get("graph_path"):
            with st.expander("Show graph traversal path"):
                st.markdown(f'<div class="graph-path-box">{g["graph_path"]}</div>', unsafe_allow_html=True)

    st.divider()

# ── Full benchmark results table ───────────────────────────────────────────
if run_full_benchmark:
    st.markdown("### Full benchmark — 10 questions")
    rows = []
    progress = st.progress(0)

    for i, q in enumerate(BENCHMARK_QUESTIONS):
        b = pipeline_baseline(q["question"])
        g = pipeline_graphrag(q["question"])
        b["accuracy"] = score_answer(b["answer"], q["ground_truth_keywords"])
        g["accuracy"]  = score_answer(g["answer"],  q["ground_truth_keywords"])

        rows.append({
            "Question": q["question"][:55] + "...",
            "Category": q["category"],
            "Baseline tokens": b["tokens_total"],
            "GraphRAG tokens": g["tokens_total"],
            "Token saving %": round((b["tokens_total"] - g["tokens_total"]) / b["tokens_total"] * 100, 1),
            "Baseline ms": b["latency_ms"],
            "GraphRAG ms": g["latency_ms"],
            "Baseline acc %": b["accuracy"],
            "GraphRAG acc %": g["accuracy"],
        })
        progress.progress((i + 1) / len(BENCHMARK_QUESTIONS))

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # Summary
    avg_token_save = df["Token saving %"].mean()
    avg_acc_gain   = (df["GraphRAG acc %"] - df["Baseline acc %"]).mean()
    st.success(
        f"Average token savings: **{avg_token_save:.1f}%** | "
        f"Average accuracy gain: **+{avg_acc_gain:.1f}%**"
    )

# ── Historical results ─────────────────────────────────────────────────────
if len(st.session_state.results) > 1:
    st.markdown("### Query history this session")
    hist_rows = []
    for r in st.session_state.results:
        hist_rows.append({
            "Question": r["question"][:50] + "...",
            "Baseline tokens": r["baseline"]["tokens_total"],
            "GraphRAG tokens": r["graphrag"]["tokens_total"],
            "Savings": f"{round((r['baseline']['tokens_total'] - r['graphrag']['tokens_total']) / r['baseline']['tokens_total'] * 100)}%",
            "Baseline acc": f"{r['baseline']['accuracy']}%",
            "GraphRAG acc": f"{r['graphrag']['accuracy']}%",
        })
    st.dataframe(pd.DataFrame(hist_rows), use_container_width=True)
