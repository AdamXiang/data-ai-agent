# AI Data Agent

A small **LangGraph** multi-agent system that turns natural-language requests into either a safe, executed **SQL query** against a PostgreSQL database, or an **ETL job** (extract from an API, transform with Pandas, load to disk) — routed automatically by a top-level agent.

This is a personal side project built to get hands-on with agentic AI patterns beyond a single prompt-and-response chatbot: multi-step state graphs, tool calling, structured LLM output, and safety guardrails around letting an LLM touch a real database.

## 🎥 Built by following this tutorial

This project was built end-to-end by following along with this YouTube video:

👉 **https://www.youtube.com/watch?v=7yOmi4IX-Rs**

All of the code in this repository was written while working through that video — full credit for the design and teaching goes to the creator. If you want the complete step-by-step explanation of *why* things are built this way, watch the video; this README covers what the finished project does and what I took away from building it.

## 🧠 What it does

There are three agents, each a separate LangGraph `StateGraph`:

| Agent | File | Job |
|---|---|---|
| **Data Agent** (router) | `agents/data_agent.py` | Looks at the user's request and classifies it as `sql` or `etl`, then hands off to the matching agent below. |
| **SQL Analyst** | `agents/sql_analyst.py` | Curates the question → pulls live DB schema context → generates a SQL query → **has a second LLM judge the query for safety** → executes it (only if safe) → summarizes the result in plain English. |
| **ETL Analyst** | `agents/etl_analyst.py` | A ReAct-style tool-calling agent that can extract data from an API into CSV/JSON/Parquet, or transform an existing file using LLM-generated Pandas code. |

```
                    ┌──────────────┐
   user request ──▶ │  Data Agent   │
                    │ (router_node) │
                    └───────┬───────┘
                 "sql" ◀────┴────▶ "etl"
                    ▼                ▼
          ┌──────────────────┐  ┌──────────────────┐
          │   SQL Analyst     │  │   ETL Analyst     │
          │ curate → context  │  │  llm_node ⇄ tool  │
          │ → generate SQL    │  │  node (ReAct loop)│
          │ → safety check    │  │  extract / trans- │
          │ → execute / answer│  │  form + Pandas    │
          └──────────────────┘  └──────────────────┘
```

Running any of the agent files directly (e.g. `python agents/sql_analyst.py`) also renders a PNG diagram of its own graph — `data_agent_graph.png`, `sql_analyst_graph.png`, and `etl_analyst_graph.png` — via LangGraph's built-in Mermaid export.

## ✨ Features

- **Natural language → SQL**, with the generated query reviewed by a second LLM call before it's ever executed (read-only queries only — INSERT/UPDATE/DELETE/DROP/etc. are rejected).
- **ETL tool-calling agent** that extracts data from a REST API and writes it to CSV/JSON/Parquet, or transforms an existing file by having the LLM write and run Pandas code.
- **Tiered model selection** (`basic` / `advanced` / `premium` in `utils/llm_pick.py`) so cheap classification steps don't use the same model as SQL/code generation.
- **Dockerized PostgreSQL** seeded with a small ride-share dataset (`users`, `vehicles`, `rides`, `payments`, `ratings`) for the SQL agent to query against.
- Fully typed agent state using **Pydantic** models (`models/schema.py`), which is what makes LangGraph's conditional routing and message-accumulation possible.

## 🧰 Tech Stack

- **Python 3.12**
- **LangChain** + **LangGraph** — agent orchestration
- **Anthropic Claude** (Haiku / Sonnet / Opus, depending on the task) via `langchain-anthropic`
- **PostgreSQL 16** (Docker) + **Adminer** for a quick DB browser UI
- **Pydantic v2** — agent state schemas & structured LLM output
- **pandas** / **requests** — ETL extract & transform
- **uv** — dependency & virtual environment management

## 📁 Project Structure

```
AI_Agent/
├── agents/
│   ├── data_agent.py      # Top-level router: sql vs etl
│   ├── sql_analyst.py     # Question → SQL → safety check → execute → answer
│   └── etl_analyst.py     # ReAct agent: extract / transform tools
├── models/
│   └── schema.py          # Pydantic state schemas shared by all graphs
├── utils/
│   ├── database.py        # psycopg2 wrapper: schema introspection + query execution
│   ├── etl_tools.py        # Extract-load / transform-load / code-exec helpers
│   └── llm_pick.py         # Model-tier factory (basic/advanced/premium)
├── init/                   # SQL run automatically on first `docker compose up`
│   ├── 01-schema.sql
│   └── 02-sample-data.sql
├── data/                   # Sample CSVs used to seed the DB (alternative to init/)
├── database_feed.py        # Standalone script: create schema + COPY the CSVs in
├── docker-compose.yml      # Postgres + Adminer for local dev
├── main.py                 # Entry point: sends one request into the Data Agent
├── pyproject.toml
└── uv.lock
```

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose
- An Anthropic API key

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment variables

Copy the template and fill in your own values:

```bash
cp .env.template .env
```

```env
ANTHROPIC_API_KEY=
DB_PORT=5432
DB_DATABASE=agent_db
DB_HOST=localhost
DB_USER=agent_user
DB_PASSWORD=agent_pass
```

### 3. Start PostgreSQL

```bash
docker compose up -d
```

This automatically runs the SQL files in `init/` on first startup, creating the schema and loading sample ride-share data. Browse it at `http://localhost:8080` (Adminer) if you want to look around.

> Alternatively, `python database_feed.py` creates the same schema and loads the CSVs in `data/` directly via `COPY` — useful if you want to reload fresh data without wiping the Docker volume.

### 4. Run the agent

```bash
uv run python main.py
```

Edit the `HumanMessage` content in `main.py` (or `agents/data_agent.py`'s `__main__` block) to try your own question.

## 💬 Example requests

**SQL question:**
> "What are the different types of payment methods we have in our database?"

Routes to the SQL Analyst → generates a `SELECT DISTINCT payment_method FROM payments ...` query → safety check passes → executes → returns a plain-English answer.

**ETL task:**
> "Extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to the data/extract folder as CSV."

Routes to the ETL Analyst → calls `extract_load_tool` → saves `data/extract/extracted_data.csv`.

## 🎓 What I learned

Building this project was mainly about getting comfortable with agent *architecture*, not just prompting a model. The main things that clicked for me:

- **LangGraph state graphs** — modeling an agent as nodes + edges over a shared, typed state object (instead of one long prompt) makes each step independently testable and a lot easier to reason about.
- **Reducers for state updates** — using `Annotated[list, add]` on the `messages` field so LangGraph *appends* to conversation history instead of overwriting it, which is what lets multi-turn tool use actually accumulate context.
- **Conditional edges as real branch logic** — `route_edge`, `is_safe_sql_condition`, and `is_tool_call` are just plain functions that return a node name; that's the whole mechanism behind an agent "deciding" what to do next.
- **The ReAct tool-calling loop** — the ETL agent's `llm_node ⇄ tool_node` cycle made it click why tool calls and tool *results* both have to go back into the message history for the LLM to reason about them on the next pass.
- **Structured output beats parsing free text** — forcing the router and the SQL "judge" to respond in a fixed Pydantic schema (`with_structured_output`) instead of asking for "yes/no" in plain text removes a whole category of parsing bugs.
- **LLMs generating SQL need a safety net** — a single generation step isn't enough; having a *second*, independent LLM call review the query for read-only-ness before execution is a small addition that meaningfully reduces risk.
- **Model tiering for cost/latency** — not every step needs the strongest model. Routing and summarization run fine on a small/fast model; only SQL and Pandas code generation actually benefit from a stronger one.
- **Local dev ergonomics matter** — Docker Compose + an `init/` folder of auto-run SQL turned "spin up a realistic database to test against" into a one-command step.


## ⚠️ Known limitations

This was built as a learning project, not a production system:

- `ETLTools.execute_code` runs LLM-generated Pandas code via Python's `exec()` with no sandboxing. Fine for local experimentation with a trusted model; not safe to expose to untrusted input.
- `database_feed.py` has a small env-var fallback bug — it sets `os.environ["PORT"]` instead of `"DB_PORT"`, so the "default to 5432" fallback doesn't actually apply. Set `DB_PORT` explicitly in `.env`.
- A couple of `__main__` blocks (e.g. in `utils/etl_tools.py`) still have a hard-coded local file path from development — update it before running those scripts directly.

## 🙏 Acknowledgments

- Tutorial followed for this build: https://www.youtube.com/watch?v=7yOmi4IX-Rs
- Sample rideshare dataset generated for local testing purposes.