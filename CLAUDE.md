# Shopping Agent

AI shopping agent (Amazon Rufus-style). Learning project — user is backend dev (Python/FastAPI/Node) learning AI eng. Build by milestone, **stop after each one for confirmation**. Explain the AI concept demonstrated, wait for "yes continue" before next.

## Stack (fixed, no substitutes)

- Pkg mgr: `uv` (backend), `npm` (frontend). Never `pip install`.
- Backend: Python, FastAPI, uvicorn
- Agent: LangGraph + LangChain (`langgraph`, `langchain`, `langchain-community`)
- LLM: Kimi (Moonshot) via `ChatOpenAI(base_url="https://api.moonshot.cn/v1", model="moonshot-v1-8k")`, key in `.env` as `MOONSHOT_API_KEY`
- DB: SQLite only — `aiosqlite` + `sqlalchemy` async. Product search via SQLite **FTS5**, no vector DB.
- Frontend: React + Vite + Tailwind
- Streaming: SSE for agent chat

## Structure

```
backend/app/{main.py, db/{schema.py,database.py}, agent/{graph.py,tools.py,guardrails.py,memory.py}, routers/{products.py,cart.py,agent.py}}
backend/scripts/{seed.py,eval.py,test_tools.py}
frontend/src/{components/{ProductGrid,CartSidebar,ChatWidget}.jsx, App.jsx, main.jsx}
```

## Milestones (see MILESTONES.md for full spec)

1. Scaffold (uv + vite + tailwind, health check)
2. DB schema + seed (SQLAlchemy models, FTS5, 80-100 products)
3. Agent tools (4 `@tool` fns, no LLM yet — test script)
4. LangGraph agent (Kimi LLM, state graph, agent↔tools loop)
5. Guardrails (input: rule-based pre-LLM; output: anti-hallucination post-LLM)
6. Memory (short-term sliding window + long-term SQLite writeback + session init)
7. FastAPI routers (products, cart, agent/chat via SSE)
8. React frontend (header, product grid, cart sidebar, chat widget)
9. Eval harness (15 test cases: tool accuracy, guardrails, retrieval)
10. README + concept wrap-up

## Rules

- Stop after every milestone, wait for explicit "yes continue"
- Comments only on real AI-eng decisions (why this tool structure/state shape/guardrail), skip boilerplate comments
- `uv add` for new deps, run via `uv run`. Frontend deps via `npm` in `frontend/`
- If lib conflict or missing file: stop and ask, don't guess
- Eval harness is required, not optional
