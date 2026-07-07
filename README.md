# Shopping Agent

AI shopping assistant (Amazon Rufus-style) — LangGraph agent with tool use, guardrails, short/long-term memory, and a React chat UI over a FastAPI backend.

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for the backend
- Node 18+ / `npm` for the frontend
- An [OpenRouter](https://openrouter.ai/) API key

## Setup

```bash
# backend
cd backend
uv sync
cp .env.example .env   # then set OPENROUTER_API_KEY=...

# seed the database (80-100 products, 3 users)
uv run python -m scripts.seed
```

```bash
# frontend
cd frontend
npm install
```

## Running

```bash
# backend — http://localhost:8000
cd backend
uv run uvicorn app.main:app --reload
```

```bash
# frontend — http://localhost:5173
cd frontend
npm run dev
```

## Eval harness

```bash
cd backend
uv run python -m scripts.eval
```

Runs 15 behavioral test cases against the live agent (real LLM calls, not mocks) across four categories:

- **Tool accuracy** — does the right `@tool` fire for the right intent (search vs. add-to-cart vs. checkout vs. recommendations vs. order history)
- **Guardrails** — injection/off-topic/gibberish/too-short rejected, legitimate queries allowed
- **Multi-turn** — does context from one turn (a named product, a cart total) correctly resolve or ground the next turn
- **Retrieval** — `search_products` correctness at the tool layer (category filtering, price filtering, free-text relevance)

Prints a pass/fail table and overall %. Since it drives a real LLM, occasional flakes reflect model non-determinism, not necessarily a regression — check the actual failure before assuming a bug.

Other scripts:

```bash
uv run python -m scripts.test_tools       # hardcoded calls to each tool, no LLM
uv run python -m scripts.test_guardrails  # input/output guardrail cases
uv run python -m app.agent.graph          # CLI smoke test of the LangGraph agent
```

## Project structure

```
backend/app/
  main.py                 FastAPI app, CORS, router registration
  db/schema.py            SQLAlchemy models
  db/database.py          async engine/session, FTS5 setup
  agent/tools.py          4 @tool functions (search, cart, orders, recommendations)
  agent/graph.py          LangGraph state graph (input_guardrail -> agent -> tools -> output_guardrail -> memory_update)
  agent/guardrails.py     rule-based input filter + LLM topic classifier; anti-hallucination output check
  agent/memory.py         short-term sliding window, long-term SQLite writeback, session init
  routers/                products, cart, orders, agent (SSE chat)
backend/scripts/
  seed.py, test_tools.py, test_guardrails.py, eval.py

frontend/src/
  components/             Header, ProductGrid, CartSidebar, ChatWidget
  pages/OrdersPage.jsx
  App.jsx, main.jsx
```
