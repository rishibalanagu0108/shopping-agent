# Full Milestone Spec

Full spec as given by user. Source of truth for scope per milestone — check here before starting one, don't rely on memory of prior conversation.

## M1 — Scaffold
- `uv --version`, install if missing
- `uv init backend`; `uv add fastapi uvicorn[standard] sqlalchemy aiosqlite python-dotenv langchain langchain-community langgraph openai`
- `.env` + `.env.example` with `OPENROUTER_API_KEY=`
- `backend/app/main.py`: FastAPI app + `/health`
- `npm create vite@latest frontend -- --template react` + Tailwind
- Verify `uv run uvicorn app.main:app --reload` and `npm run dev` both start

## M2 — DB schema + seed
Tables (SQLAlchemy, `backend/app/db/schema.py`):
- products(id, name, description, category, price, brand, stock, image_url, rating)
- categories(id, name)
- cart(id, user_id, product_id, quantity, added_at)
- orders(id, user_id, total, created_at)
- order_items(id, order_id, product_id, quantity, price_at_purchase)
- users(id, name, preferred_categories, price_range_max)

FTS5 on products(name, description, brand). Comment: why FTS5 > vector DB here.

`backend/scripts/seed.py`: 3 users (Shyam, Priya, Ravi, distinct prefs/price ranges), 80-100 products across Electronics/Books/Clothing/Kitchen/Sports/Toys, realistic name/2-3 sentence desc/INR price/brand/stock/`https://picsum.photos/seed/{id}/300/300`. Run `uv run python -m scripts.seed`. Print summary table (category, count, price range).

## M3 — Agent tools (pure Python, no LLM)
`backend/app/agent/tools.py`, 4 `@tool` fns:
- `search_products(query, category=None, max_price=None)` — FTS5 + WHERE filters, top 10, id/name/price/category/rating/stock. Comment why FTS5 handles "cozy winter" style queries.
- `manage_cart(action, user_id, product_id=None, quantity=1)` — add/remove/view/clear/checkout. checkout moves cart→orders+order_items, clears cart, returns summary.
- `get_order_history(user_id, limit=5)` — recent orders + items.
- `get_recommendations(user_id, category=None)` — user prefs/price range → top-rated matches, fallback to overall top-rated.

`backend/scripts/test_tools.py` — hardcoded calls to each tool, print results, no LLM.

## M4 — LangGraph agent
`backend/app/agent/graph.py`. State:
```python
class AgentState(TypedDict):
    messages: list[BaseMessage]
    user_id: int
    cart_snapshot: list[dict]
    last_products: list[dict]
    blocked: bool
```
Nodes: input_guardrail → agent (Kimi + bind_tools) → tools (ToolNode) → output_guardrail → memory_update
Edges: START→input_guardrail; input_guardrail→agent|END(if blocked); agent→tools|output_guardrail; tools→agent (loop); output_guardrail→memory_update→END
Comment: why agent→tools→agent loop = agentic vs plain chain.
CLI test: `uv run python -m app.agent.graph` — hardcoded messages, print response + tools called.

## M5 — Guardrails
`backend/app/agent/guardrails.py`
- Input (no LLM, rule-based): reject off-topic/too-short/gibberish, detect injection ("ignore previous", "act as", "forget your role"). Returns `{allowed, reason}`. Comment: why pre-LLM (cost+safety).
- Output (post-LLM): verify mentioned product names exist in DB, prices within ±10% of DB price. On fail, replace with safe fallback. Comment: anti-hallucination, Rufus-style failure mode.

## M6 — Memory
`backend/app/agent/memory.py`
- Short-term: trim `messages` to last 6 turns before each agent call. Comment why 6 + what breaks without trimming.
- Long-term (`memory_update` node): detect price pref ("under ₹500") → update users.price_range_max; repeated category browsing → update users.preferred_categories; checkout already in orders.
- Session init: new conversation loads user profile (name, prefs, last 3 orders) → inject as system message. Comment: bridges long-term→short-term memory.

## M7 — FastAPI routers
- `/api/products`: GET list (filters category/search/max_price), GET /categories, GET /{id}
- `/api/cart`: GET /{user_id}, POST /{user_id}/add {product_id,quantity}, DELETE /{user_id}/remove/{product_id}, POST /{user_id}/checkout
- `/api/agent`: POST /chat {user_id,message} → SSE stream. Events: {"type":"token","data":...}, {"type":"tool_call","data":tool_name}, {"type":"done","data":""}. Comment: why SSE over WebSocket here.
- CORS for `http://localhost:5173`

## M8 — React frontend
- Header: logo, user switcher (Shyam/Priya/Ravi — switch reloads cart + resets chat), cart icon+badge
- Product grid: category tabs, search bar (hits GET /api/products?search=), responsive cards (image/name/brand/price ₹/rating/stock/add-to-cart)
- Cart sidebar: qty +/-, remove, subtotal, checkout button + success toast
- Chat widget: fixed bottom-right, collapsed button → expanded 400x500 panel, SSE token streaming, tool-call pill ("Searching products…"), inline product chips (click scrolls grid), user switch clears chat
- Tailwind throughout, professional look

## M9 — Eval harness
`backend/scripts/eval.py`, 15 test cases (tool-call accuracy, guardrail coverage incl. injection + off-topic, multi-turn follow-up using last_products, retrieval accuracy incl. category match). Results table + overall pass %.

## M10 — README + wrap-up
- README.md: prereqs, env setup, seed, run backend+frontend, run eval
- In-chat (not a file): one paragraph per concept — agentic loops, tool use, state graphs, short/long-term memory, input/output guardrails, FTS5 vs vector DB, SSE streaming, evaluation
