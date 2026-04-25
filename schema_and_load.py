"""
RepoGraph — schema setup + data loader
Run this once to create the graph and load GitHub repo data.
"""

import pyTigerGraph as tg
import json

# ── Connect ────────────────────────────────────────────────────────────────
conn = tg.TigerGraphConnection(
    host="https://YOUR_SUBDOMAIN.i.tgcloud.io",
    graphname="RepoGraph",
    username="tigergraph",
    password="YOUR_PASSWORD",
)
conn.getToken(conn.createSecret())

# ── Schema ─────────────────────────────────────────────────────────────────
schema = """
USE GLOBAL

CREATE VERTEX Repository (
    PRIMARY_ID repo_id STRING,
    name       STRING,
    full_name  STRING,
    stars      INT,
    forks      INT,
    description STRING,
    url        STRING,
    language   STRING,
    topics     STRING,   -- comma-separated
    org        STRING,
    domain     STRING    -- ai, webdev, systems, education, devtools, security
) WITH primary_id_as_attribute="true"

CREATE VERTEX Topic (
    PRIMARY_ID name STRING,
    name       STRING
) WITH primary_id_as_attribute="true"

CREATE VERTEX Language (
    PRIMARY_ID name STRING,
    name       STRING
) WITH primary_id_as_attribute="true"

CREATE VERTEX Organization (
    PRIMARY_ID name STRING,
    name       STRING
) WITH primary_id_as_attribute="true"

CREATE VERTEX Domain (
    PRIMARY_ID name STRING,
    name       STRING
) WITH primary_id_as_attribute="true"

CREATE UNDIRECTED EDGE same_ecosystem (FROM Repository, TO Repository,
    weight FLOAT DEFAULT 1.0,
    reason STRING)

CREATE DIRECTED EDGE tagged_with (FROM Repository, TO Topic)
CREATE DIRECTED EDGE written_in (FROM Repository, TO Language)
CREATE DIRECTED EDGE maintained_by (FROM Repository, TO Organization)
CREATE DIRECTED EDGE belongs_to_domain (FROM Repository, TO Domain)
CREATE DIRECTED EDGE commonly_used_with (FROM Repository, TO Repository,
    weight FLOAT DEFAULT 1.0)
CREATE DIRECTED EDGE inspired_by (FROM Repository, TO Repository)
CREATE DIRECTED EDGE depends_on (FROM Repository, TO Repository)

CREATE GRAPH RepoGraph (
    Repository, Topic, Language, Organization, Domain,
    same_ecosystem, tagged_with, written_in, maintained_by,
    belongs_to_domain, commonly_used_with, inspired_by, depends_on
)
"""

# ── Seed data: Top GitHub repos with rich relationships ────────────────────
REPOS = [
    # (repo_id, name, stars, lang, org, domain, topics, description)
    ("freeCodeCamp",           "freeCodeCamp",           502000, "JavaScript", "freeCodeCamp", "education",   "javascript,web,learning,html,css",         "Learn to code for free"),
    ("free-programming-books", "free-programming-books", 341000, "None",       "EbookFoundation","education","books,programming,resources,learning",      "Free programming books"),
    ("awesome",                "awesome",                340000, "None",       "sindresorhus",   "devtools",  "awesome-list,curated",                      "Awesome lists"),
    ("build-your-own-x",       "build-your-own-x",       330000, "None",       "codecrafters-io","education","tutorial,learning,systems",                  "Build your own X from scratch"),
    ("public-apis",            "public-apis",            320000, "Python",     "public-apis",    "devtools",  "api,rest,web",                              "Public APIs list"),
    ("coding-interview-university","coding-interview-university",310000,"None","jwasham",       "education", "interview,algorithms,learning",              "CS study plan"),
    ("developer-roadmap",      "developer-roadmap",      305000, "TypeScript", "kamranahmedse",  "education", "roadmap,learning,career,web",               "Developer roadmaps"),
    ("system-design-primer",   "system-design-primer",   282000, "Python",     "donnemartin",    "education", "system-design,interview,architecture",      "System design primer"),
    ("javascript-algorithms",  "javascript-algorithms",  195000, "JavaScript", "trekhleb",       "education", "javascript,algorithms,data-structures",     "JS algorithms & data structures"),
    ("react",                  "react",                  244000, "JavaScript", "facebook",       "webdev",    "javascript,ui,frontend,library",            "React UI library"),
    ("vue",                    "vue",                    209000, "TypeScript", "vuejs",           "webdev",   "javascript,ui,frontend,framework",          "Vue.js framework"),
    ("angular",                "angular",                97000,  "TypeScript", "angular",         "webdev",   "typescript,ui,frontend,framework",          "Angular framework"),
    ("tensorflow",             "tensorflow",             194000, "C++",        "google",          "ai",       "machine-learning,deep-learning,python,ai",  "ML framework"),
    ("transformers",           "transformers",           159000, "Python",     "huggingface",     "ai",       "nlp,machine-learning,python,ai,llm",        "Hugging Face Transformers"),
    ("pytorch",                "pytorch",                86000,  "Python",     "pytorch",         "ai",       "machine-learning,deep-learning,python,ai",  "PyTorch ML framework"),
    ("stable-diffusion-webui", "stable-diffusion-webui",162000, "Python",     "AUTOMATIC1111",   "ai",       "ai,image-generation,stable-diffusion",      "Stable Diffusion WebUI"),
    ("LLMs-from-scratch",      "LLMs-from-scratch",      90000,  "Python",     "rasbt",           "ai",       "llm,python,ai,education,machine-learning",  "Build LLMs from scratch"),
    ("linux",                  "linux",                  230000, "C",          "torvalds",        "systems",  "kernel,os,c,systems",                       "Linux kernel"),
    ("redis",                  "redis",                  73000,  "C",          "redis",           "systems",  "database,cache,c,systems",                  "Redis in-memory DB"),
    ("git",                    "git",                    55000,  "C",          "git",             "devtools", "vcs,c,devtools",                            "Git source"),
    ("vscode",                 "vscode",                 168000, "TypeScript", "microsoft",       "devtools", "editor,typescript,devtools",                "VS Code editor"),
    ("ohmyzsh",                "ohmyzsh",                176000, "Shell",      "ohmyzsh",         "devtools", "zsh,shell,terminal,devtools",               "Oh My Zsh"),
    ("TypeScript",             "TypeScript",             102000, "TypeScript", "microsoft",       "webdev",   "typescript,javascript,language",            "TypeScript language"),
    ("Python",                 "cpython",                65000,  "Python",     "python",          "systems",  "python,language,interpreter",               "CPython interpreter"),
    ("bitcoin",                "bitcoin",                88000,  "C++",        "bitcoin",         "systems",  "blockchain,cryptocurrency,c++",             "Bitcoin core"),
    ("deno",                   "deno",                   106000, "Rust",       "denoland",        "systems",  "javascript,typescript,runtime,rust",        "Deno runtime"),
    ("gin",                    "gin",                    88000,  "Go",         "gin-gonic",       "webdev",   "go,web,framework,api",                      "Gin web framework"),
    ("tauri",                  "tauri",                  105000, "Rust",       "tauri-apps",      "devtools", "rust,desktop,app,webdev",                   "Tauri desktop apps"),
    ("awesome-python",         "awesome-python",         220000, "Python",     "vinta",           "education","python,awesome-list,curated",               "Awesome Python list"),
    ("awesome-go",             "awesome-go",             169000, "Go",         "avelino",         "education","go,awesome-list,curated",                   "Awesome Go list"),
]

# Explicit relationships beyond auto-inferred ones
SAME_ECOSYSTEM = [
    ("react", "vue",      0.9, "frontend frameworks"),
    ("react", "angular",  0.8, "frontend frameworks"),
    ("vue",   "angular",  0.8, "frontend frameworks"),
    ("tensorflow", "pytorch",       0.95, "deep learning"),
    ("tensorflow", "transformers",  0.9,  "ML/AI"),
    ("pytorch",    "transformers",  0.95, "ML/AI"),
    ("pytorch",    "LLMs-from-scratch", 0.9, "LLM education"),
    ("linux",  "redis",   0.7,  "systems C"),
    ("linux",  "git",     0.75, "systems C"),
    ("deno",   "TypeScript", 0.85, "JS runtime"),
    ("vscode", "TypeScript", 0.9,  "Microsoft TS"),
    ("freeCodeCamp", "developer-roadmap", 0.9, "learning path"),
    ("freeCodeCamp", "coding-interview-university", 0.85, "CS learning"),
    ("system-design-primer", "coding-interview-university", 0.9, "interview prep"),
    ("awesome-python", "awesome-go", 0.7, "language awesome lists"),
    ("awesome", "awesome-python", 0.8, "awesome ecosystem"),
    ("awesome", "awesome-go",    0.8, "awesome ecosystem"),
]

COMMONLY_USED_WITH = [
    ("react",      "TypeScript",  0.9),
    ("vue",        "TypeScript",  0.85),
    ("tensorflow", "Python",      1.0),
    ("pytorch",    "Python",      1.0),
    ("transformers","pytorch",    0.95),
    ("gin",        "redis",       0.8),
    ("vscode",     "git",         0.9),
    ("ohmyzsh",    "git",         0.85),
    ("tauri",      "vscode",      0.8),
    ("LLMs-from-scratch", "transformers", 0.9),
    ("stable-diffusion-webui", "pytorch", 0.95),
]

INSPIRED_BY = [
    ("deno",   "linux"),
    ("gin",    "react"),          # minimal API inspired by express/react ecosystem
    ("tauri",  "vscode"),
    ("LLMs-from-scratch", "transformers"),
    ("stable-diffusion-webui", "tensorflow"),
]

DEPENDS_ON = [
    ("stable-diffusion-webui", "pytorch"),
    ("transformers", "pytorch"),
    ("LLMs-from-scratch", "pytorch"),
    ("react", "TypeScript"),
    ("vue",   "TypeScript"),
    ("deno",  "TypeScript"),
]


def load_all():
    print("Loading vertices...")

    domains_seen, langs_seen, orgs_seen, topics_seen = set(), set(), set(), set()

    for (rid, name, stars, lang, org, domain, topics_str, desc) in REPOS:
        # Repo vertex
        conn.upsertVertex("Repository", rid, {
            "name": name, "full_name": f"{org}/{name}", "stars": stars,
            "forks": int(stars * 0.15), "description": desc,
            "url": f"https://github.com/{org}/{name}",
            "language": lang, "topics": topics_str, "org": org, "domain": domain,
        })

        # Language
        if lang != "None" and lang not in langs_seen:
            conn.upsertVertex("Language", lang, {"name": lang})
            langs_seen.add(lang)
        if lang != "None":
            conn.upsertEdge("Repository", rid, "written_in", "Language", lang)

        # Organization
        if org not in orgs_seen:
            conn.upsertVertex("Organization", org, {"name": org})
            orgs_seen.add(org)
        conn.upsertEdge("Repository", rid, "maintained_by", "Organization", org)

        # Domain
        if domain not in domains_seen:
            conn.upsertVertex("Domain", domain, {"name": domain})
            domains_seen.add(domain)
        conn.upsertEdge("Repository", rid, "belongs_to_domain", "Domain", domain)

        # Topics
        for t in topics_str.split(","):
            t = t.strip()
            if t and t not in topics_seen:
                conn.upsertVertex("Topic", t, {"name": t})
                topics_seen.add(t)
            if t:
                conn.upsertEdge("Repository", rid, "tagged_with", "Topic", t)

    print("Loading edges...")
    for (a, b, w, reason) in SAME_ECOSYSTEM:
        conn.upsertEdge("Repository", a, "same_ecosystem", "Repository", b,
                        {"weight": w, "reason": reason})

    for (a, b, w) in COMMONLY_USED_WITH:
        conn.upsertEdge("Repository", a, "commonly_used_with", "Repository", b,
                        {"weight": w})

    for (a, b) in INSPIRED_BY:
        conn.upsertEdge("Repository", a, "inspired_by", "Repository", b)

    for (a, b) in DEPENDS_ON:
        conn.upsertEdge("Repository", a, "depends_on", "Repository", b)

    print("Done! Graph loaded.")


if __name__ == "__main__":
    load_all()
