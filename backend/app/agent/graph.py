import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.guardrails import check_input, extract_last_products, verify_output
from app.agent.memory import load_session_intro, trim_messages, update_long_term_memory
from app.agent.tools import get_order_history, get_recommendations, manage_cart, search_products

load_dotenv()

TOOLS = [search_products, manage_cart, get_order_history, get_recommendations]


class AgentState(TypedDict):
    # add_messages appends instead of overwriting, so the agent<->tools loop below
    # keeps full conversation history across iterations instead of erasing it each turn.
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int
    cart_snapshot: list[dict]
    last_products: list[dict]
    blocked: bool


llm = ChatOpenAI(
    base_url="https://openrouter.ai/api/v1",
    model="nvidia/nemotron-3-super-120b-a12b:free",
    api_key=os.environ["OPENROUTER_API_KEY"],
)
llm_with_tools = llm.bind_tools(TOOLS)


def input_guardrail(state: AgentState) -> dict:
    result = check_input(state["messages"][-1].content)
    if not result["allowed"]:
        fallback = AIMessage(
            content="I can't help with that — I'm a shopping assistant. "
            "Try asking me about products, prices, or your cart."
        )
        return {"blocked": True, "messages": [fallback]}
    return {"blocked": False}


async def agent(state: AgentState) -> dict:
    response = await llm_with_tools.ainvoke(trim_messages(state["messages"]))
    return {"messages": [response]}


def output_guardrail(state: AgentState) -> dict:
    last_products = extract_last_products(state["messages"])
    last_message = state["messages"][-1]
    result = verify_output(last_message.content, last_products)

    update = {"last_products": last_products}
    if not result["safe"]:
        # Same id as the message being replaced — add_messages overwrites in place
        # instead of appending, so the hallucinated response never reaches the user.
        update["messages"] = [AIMessage(content=result["response"], id=last_message.id)]
    return update


async def memory_update(state: AgentState) -> dict:
    last_human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    if last_human:
        await update_long_term_memory(state["user_id"], last_human.content, state["last_products"])
    return {}


def route_after_input_guardrail(state: AgentState) -> str:
    return END if state["blocked"] else "agent"


graph_builder = StateGraph(AgentState)
graph_builder.add_node("input_guardrail", input_guardrail)
graph_builder.add_node("agent", agent)
graph_builder.add_node("tools", ToolNode(TOOLS))
graph_builder.add_node("output_guardrail", output_guardrail)
graph_builder.add_node("memory_update", memory_update)

graph_builder.add_edge(START, "input_guardrail")
graph_builder.add_conditional_edges(
    "input_guardrail", route_after_input_guardrail, {"agent": "agent", END: END}
)
# agent -> tools when the model requests a tool call, agent -> output_guardrail once it
# answers in plain text. This loop (vs a fixed call sequence) is what makes it agentic:
# the model decides how many tool calls it needs and reacts to each result before
# deciding to stop, instead of following a hardcoded pipeline of steps.
graph_builder.add_conditional_edges(
    "agent", tools_condition, {"tools": "tools", END: "output_guardrail"}
)
graph_builder.add_edge("tools", "agent")
graph_builder.add_edge("output_guardrail", "memory_update")
graph_builder.add_edge("memory_update", END)

graph = graph_builder.compile()


if __name__ == "__main__":
    import asyncio

    async def run():
        intro = await load_session_intro(1)
        result = await graph.ainvoke(
            {
                "messages": [intro, HumanMessage(content="Find me a bluetooth speaker under 1000 rupees")],
                "user_id": 1,
                "cart_snapshot": [],
                "last_products": [],
                "blocked": False,
            }
        )
        print("--- Final response ---")
        print(result["messages"][-1].content)
        print("\n--- Tools called ---")
        for m in result["messages"]:
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    print(f"{tc['name']}({tc['args']})")

    asyncio.run(run())
