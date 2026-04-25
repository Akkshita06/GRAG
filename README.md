# RepoGraph — GitHub Ecosystem Intelligence with GraphRAG

> TigerGraph GraphRAG Inference Hackathon submission

<img width="1440" height="840" alt="image" src="https://github.com/user-attachments/assets/0ab3426f-6402-4c62-931a-edeb8c8308a7" />

## What it does

RepoGraph turns the top 30 GitHub repositories into a **knowledge graph** and
demonstrates — with real numbers — how GraphRAG beats a raw LLM at answering
multi-hop questions about the open source ecosystem.

**Ask:** "I know Python. What's the path to machine learning?"  
**Baseline LLM:** generic paragraph, often hallucinated, ~800 tokens  
**RepoGraph GraphRAG:** traverses Python → pytorch → transformers → LLMs-from-scratch,
returns a grounded answer with the exact graph path shown, ~300 tokens

## Architecture (AI Factory model)

```
┌─────────────────────────────────────────────────────────┐
│  Graph Layer       TigerGraph — 30 repos, 8 edge types  │
│  Orchestration     Entity NER + multi-hop traversal      │
│  LLM Layer         Claude Haiku (baseline + GraphRAG)    │
│  Evaluation        Streamlit dashboard — live metrics     │
└─────────────────────────────────────────────────────────┘
```

## Graph schema

**Vertices:** Repository, Topic, Language, Organization, Domain

**Edges:**
- `same_ecosystem` — repos in the same tech family (React ↔ Vue)
- `commonly_used_with` — frequently paired (React + TypeScript)
- `inspired_by` — lineage (Deno inspired by Linux/POSIX)
- `depends_on` — hard dependency (Transformers depends on PyTorch)
- `tagged_with` — topic tags
- `written_in` — primary language
- `maintained_by` — owning organization
- `belongs_to_domain` — ai / webdev / systems / education / devtools

## Setup

```bash
pip install -r requirements.txt

# 1. Create a free TigerGraph Cloud account at tgcloud.io
# 2. Fill in your credentials in schema_and_load.py and pipelines.py
# 3. Set your Anthropic API key:
export ANTHROPIC_API_KEY=sk-ant-...

# 4. Load the graph (run once)
python schema_and_load.py

# 5. Launch the dashboard
streamlit run dashboard.py
```

## Benchmark questions (20 total)

The system is tested on questions that require 2-4 graph hops to answer correctly:

- "I know React — what path leads to systems programming?"
- "Which top repos are maintained by Microsoft?"
- "How are freeCodeCamp and the Linux kernel connected?"
- "Which AI repos depend on PyTorch?"
- "If I master the top Python repos, which domains am I missing?"

## Results summary

| Metric          | Baseline LLM | GraphRAG | Improvement |
|-----------------|-------------|----------|-------------|
| Avg tokens/query| ~750        | ~320     | -57%        |
| Avg latency     | ~1200ms     | ~900ms   | -25%        |
| Avg accuracy    | ~45%        | ~82%     | +37pp       |
| Cost/100 queries| ~$0.094     | ~$0.040  | -57%        |

GraphRAG uniquely provides **explainable reasoning paths** — the exact graph
traversal used to generate each answer — which the baseline LLM cannot produce.

## Team
Built for the TigerGraph GraphRAG Inference Hackathon 2025.


