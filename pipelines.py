"""
RepoGraph — dual pipeline engine
Pipeline A: Raw LLM (baseline)
Pipeline B: GraphRAG (TigerGraph + LLM)
"""

import time
import os
import pyTigerGraph as tg
from anthropic import Anthropic

# ── Clients ────────────────────────────────────────────────────────────────
llm = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-haiku-4-5-20251001"   # fast + cheap for benchmarking

conn = tg.TigerGraphConnection(
    host="https://YOUR_SUBDOMAIN.i.tgcloud.io",
    graphname="RepoGraph",
    username="tigergraph",
    password="YOUR_PASSWORD",
)

# ── GSQL Queries ───────────────────────────────────────────────────────────

GSQL_LEARNING_PATH = """
CREATE QUERY learning_path(STRING start_repo, INT max_hops) FOR GRAPH RepoGraph {
  /* Multi-hop traversal: find the learning journey from start_repo */
  OrAccum @visited;
  SetAccum<VERTEX<Repository>> @@path;
  SetAccum<STRING> @@edges_used;

  Seed = {Repository.*};
  Start = SELECT r FROM Seed:r WHERE r.repo_id == start_repo;

  @@path += Start;

  FOREACH hop IN RANGE[1, max_hops] DO
    Neighbors = SELECT nb
      FROM @@path:r -(same_ecosystem|commonly_used_with|inspired_by>)- Repository:nb
      WHERE NOT nb.@visited AND nb.repo_id != start_repo
      ACCUM nb.@visited += TRUE,
            @@path += nb,
            @@edges_used += r.name + " -> " + nb.name;
  END;

  PRINT @@path, @@edges_used;
}
"""

GSQL_DOMAIN_COVERAGE = """
CREATE QUERY domain_coverage(SET<STRING> known_repos) FOR GRAPH RepoGraph {
  /* Which domains do you cover and which are you missing? */
  MapAccum<STRING, SetAccum<STRING>> @@covered_domains;
  MapAccum<STRING, SetAccum<STRING>> @@all_domains;

  AllRepos = {Repository.*};
  KnownRepos = SELECT r FROM AllRepos:r WHERE r.repo_id IN known_repos;
  UnknownRepos = SELECT r FROM AllRepos:r WHERE r.repo_id NOT IN known_repos;

  KnownRepos = SELECT r FROM KnownRepos:r
    ACCUM @@covered_domains += (r.domain -> r.name);

  UnknownRepos = SELECT r FROM UnknownRepos:r
    ACCUM @@all_domains += (r.domain -> r.name);

  PRINT @@covered_domains, @@all_domains;
}
"""

GSQL_SHORTEST_PATH = """
CREATE QUERY shortest_path(STRING repo_a, STRING repo_b) FOR GRAPH RepoGraph {
  /* Shortest relationship path between two repos */
  MinAccum<INT> @dist;
  MapAccum<VERTEX, VERTEX> @@prev;
  SetAccum<STRING> @@path_labels;

  All = {Repository.*};
  Source = SELECT r FROM All:r WHERE r.repo_id == repo_a ACCUM r.@dist = 0;
  Target = SELECT r FROM All:r WHERE r.repo_id == repo_b;

  WHILE Source.size() > 0 LIMIT 6 DO
    Source = SELECT t
      FROM Source:s -(same_ecosystem|commonly_used_with|inspired_by|depends_on)- Repository:t
      WHERE t.@dist == GSQL_INT_MAX
      ACCUM t.@dist += s.@dist + 1,
            @@prev += (t -> s),
            @@path_labels += s.name + " -> " + t.name;
  END;

  PRINT @@path_labels;
  PRINT Target[Target.@dist AS hops];
}
"""

GSQL_CLUSTER_BY_TOPIC = """
CREATE QUERY cluster_by_topic(STRING topic_name) FOR GRAPH RepoGraph {
  /* Find all repos tagged with a topic, plus their neighbours */
  SetAccum<VERTEX<Repository>> @@cluster;

  TopicNode = {Topic.*};
  MatchedTopic = SELECT t FROM TopicNode:t WHERE t.name == topic_name;

  Tagged = SELECT r FROM MatchedTopic:t -(tagged_with<)- Repository:r
    ACCUM @@cluster += r;

  Neighbors = SELECT nb FROM @@cluster:r -(same_ecosystem)- Repository:nb
    ACCUM @@cluster += nb;

  PRINT @@cluster;
}
"""


# ── Graph context builder ──────────────────────────────────────────────────

def extract_entities(question: str) -> list[str]:
    """Simple NER — match question words against known repo names."""
    known = {
        "react", "vue", "angular", "tensorflow", "pytorch", "transformers",
        "linux", "redis", "git", "vscode", "freecodecamp", "freeCodeCamp",
        "typescript", "python", "javascript", "deno", "tauri", "gin",
        "ohmyzsh", "system-design-primer", "developer-roadmap",
        "coding-interview-university", "build-your-own-x", "awesome",
        "awesome-python", "stable-diffusion-webui", "LLMs-from-scratch",
        "bitcoin", "public-apis", "free-programming-books",
    }
    words = question.lower().replace("-", " ").split()
    found = []
    for w in words:
        if w in known or w.replace(" ", "") in known:
            found.append(w)
    return found or ["freeCodeCamp"]  # fallback


def build_graph_context(question: str) -> tuple[str, dict]:
    """
    Pull relevant subgraph from TigerGraph.
    Returns (context_string, stats_dict).
    """
    entities = extract_entities(question)
    start = entities[0]

    t0 = time.time()

    # Multi-hop traversal
    try:
        result = conn.runInstalledQuery("learning_path",
                                        params={"start_repo": start, "max_hops": 3})
        paths = result[0].get("@@path", [])
        edges = result[0].get("@@edges_used", [])
    except Exception:
        # Fallback: use REST neighbor query
        result = conn.getVertexNeighbors("Repository", start, edgeTypes=["same_ecosystem","commonly_used_with"])
        paths = result
        edges = []

    elapsed = time.time() - t0

    # Format context
    context_lines = [f"Graph traversal starting from: {start}"]
    context_lines.append(f"Repos found in subgraph ({len(paths)}):")
    for p in paths[:12]:  # cap context
        attrs = p.get("attributes", p)
        context_lines.append(
            f"  - {attrs.get('name','?')} ({attrs.get('domain','?')}, "
            f"{attrs.get('stars',0):,} stars, lang={attrs.get('language','?')})"
        )
    if edges:
        context_lines.append("\nRelationship edges traversed:")
        for e in list(edges)[:10]:
            context_lines.append(f"  {e}")

    context_str = "\n".join(context_lines)
    stats = {
        "graph_query_ms": round(elapsed * 1000),
        "nodes_retrieved": len(paths),
        "edges_traversed": len(edges),
        "context_tokens": len(context_str.split()),
    }
    return context_str, stats


# ── Pipeline A: Baseline LLM ───────────────────────────────────────────────

def pipeline_baseline(question: str) -> dict:
    prompt = f"""You are a GitHub expert. Answer this question about GitHub repositories 
and the open source ecosystem as accurately as possible.

Question: {question}

Give a detailed, specific answer."""

    t0 = time.time()
    resp = llm.messages.create(
        model=MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed_ms = round((time.time() - t0) * 1000)
    answer = resp.content[0].text
    input_tokens  = resp.usage.input_tokens
    output_tokens = resp.usage.output_tokens
    total_tokens  = input_tokens + output_tokens

    # Cost estimate (Haiku pricing ~$0.25/M input, $1.25/M output)
    cost_usd = (input_tokens * 0.00000025) + (output_tokens * 0.00000125)

    return {
        "pipeline": "Baseline LLM",
        "answer": answer,
        "tokens_input": input_tokens,
        "tokens_output": output_tokens,
        "tokens_total": total_tokens,
        "latency_ms": elapsed_ms,
        "cost_usd": round(cost_usd, 6),
        "graph_context_used": False,
        "graph_path": None,
    }


# ── Pipeline B: GraphRAG ───────────────────────────────────────────────────

def pipeline_graphrag(question: str) -> dict:
    graph_context, graph_stats = build_graph_context(question)

    prompt = f"""You are a GitHub ecosystem expert powered by a knowledge graph.
You have been given VERIFIED graph data from TigerGraph showing real relationships 
between the top GitHub repositories. Use ONLY this data to answer the question.

=== GRAPH CONTEXT (verified data) ===
{graph_context}
=====================================

Question: {question}

Answer using the graph data above. Be specific about which repositories are connected 
and how. Show the reasoning path through the graph."""

    t0 = time.time()
    resp = llm.messages.create(
        model=MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed_ms = round((time.time() - t0) * 1000)
    answer = resp.content[0].text
    input_tokens  = resp.usage.input_tokens
    output_tokens = resp.usage.output_tokens
    total_tokens  = input_tokens + output_tokens
    cost_usd = (input_tokens * 0.00000025) + (output_tokens * 0.00000125)

    return {
        "pipeline": "GraphRAG",
        "answer": answer,
        "tokens_input": input_tokens,
        "tokens_output": output_tokens,
        "tokens_total": total_tokens,
        "latency_ms": elapsed_ms + graph_stats["graph_query_ms"],
        "cost_usd": round(cost_usd, 6),
        "graph_context_used": True,
        "graph_path": graph_context,
        "graph_stats": graph_stats,
    }


# ── Accuracy scorer ────────────────────────────────────────────────────────

def score_answer(answer: str, ground_truth_keywords: list[str]) -> float:
    """Simple keyword-based accuracy: % of expected keywords found."""
    answer_lower = answer.lower()
    hits = sum(1 for kw in ground_truth_keywords if kw.lower() in answer_lower)
    return round(hits / len(ground_truth_keywords) * 100, 1) if ground_truth_keywords else 0.0


# ── Benchmark question bank ────────────────────────────────────────────────

BENCHMARK_QUESTIONS = [
    {
        "question": "I know JavaScript and React. What's the fastest path to learn machine learning?",
        "ground_truth_keywords": ["python", "tensorflow", "pytorch", "machine learning", "transformers"],
        "category": "learning path",
    },
    {
        "question": "Which top GitHub repos are maintained by Microsoft?",
        "ground_truth_keywords": ["vscode", "typescript", "microsoft"],
        "category": "org lookup",
    },
    {
        "question": "What repos should I study if I want to work on systems programming?",
        "ground_truth_keywords": ["linux", "redis", "c", "systems", "git"],
        "category": "domain query",
    },
    {
        "question": "How are freeCodeCamp and the system-design-primer related?",
        "ground_truth_keywords": ["education", "learning", "interview", "developer"],
        "category": "relationship",
    },
    {
        "question": "Which AI repos are most commonly used together?",
        "ground_truth_keywords": ["pytorch", "transformers", "tensorflow", "python"],
        "category": "cluster",
    },
    {
        "question": "What's the connection between the Linux kernel and React?",
        "ground_truth_keywords": ["c", "javascript", "ecosystem", "programming"],
        "category": "shortest path",
    },
    {
        "question": "I want to build desktop apps. Which repos form a learning path for me?",
        "ground_truth_keywords": ["tauri", "rust", "vscode", "typescript"],
        "category": "learning path",
    },
    {
        "question": "Which repositories teach both web development and algorithms?",
        "ground_truth_keywords": ["javascript-algorithms", "freeCodeCamp", "developer-roadmap"],
        "category": "multi-domain",
    },
    {
        "question": "What Go repositories are in the top GitHub repos?",
        "ground_truth_keywords": ["gin", "awesome-go", "deno"],
        "category": "language filter",
    },
    {
        "question": "Which education repos have the most stars?",
        "ground_truth_keywords": ["freeCodeCamp", "free-programming-books", "awesome"],
        "category": "ranking",
    },
]


def run_benchmark():
    """Run all benchmark questions through both pipelines."""
    results = []
    for i, q in enumerate(BENCHMARK_QUESTIONS):
        print(f"\n[{i+1}/{len(BENCHMARK_QUESTIONS)}] {q['question'][:60]}...")

        baseline = pipeline_baseline(q["question"])
        graphrag  = pipeline_graphrag(q["question"])

        baseline["accuracy"] = score_answer(baseline["answer"], q["ground_truth_keywords"])
        graphrag["accuracy"]  = score_answer(graphrag["answer"],  q["ground_truth_keywords"])

        results.append({
            "question": q["question"],
            "category": q["category"],
            "baseline": baseline,
            "graphrag": graphrag,
        })

        print(f"  Baseline: {baseline['tokens_total']} tokens, {baseline['latency_ms']}ms, acc={baseline['accuracy']}%")
        print(f"  GraphRAG: {graphrag['tokens_total']} tokens, {graphrag['latency_ms']}ms, acc={graphrag['accuracy']}%")

    return results


if __name__ == "__main__":
    # Quick single test
    q = "I know Python. What path leads me to AI and LLMs?"
    print("=== BASELINE ===")
    b = pipeline_baseline(q)
    print(b["answer"])
    print(f"\nTokens: {b['tokens_total']} | Cost: ${b['cost_usd']}")

    print("\n=== GRAPHRAG ===")
    g = pipeline_graphrag(q)
    print(g["answer"])
    print(f"\nTokens: {g['tokens_total']} | Cost: ${g['cost_usd']}")
    print(f"\nGraph path used:\n{g['graph_path']}")
