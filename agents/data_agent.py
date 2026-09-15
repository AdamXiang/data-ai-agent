"""Top-level "Data Agent" -- routes user requests to the SQL or ETL agent.

This is the entry point for the whole system (see ``main.py``). It's a
small LangGraph graph with exactly one real decision to make:

    router_node --(sql)--> sql_node --> END
                --(etl)--> etl_node --> END

``router_node`` asks a cheap LLM to classify the user's request as either
a "sql" question (e.g. "how many rides happened last week?") or an "etl"
task (e.g. "extract data from this API and save it as CSV"), and the
matching sub-agent graph (``sql_analyst`` or ``etl_analyst``) does the
actual work. This keeps the two sub-agents focused on a single
responsibility instead of one giant agent trying to do everything.
"""

import os
import sys

# Make the project root importable (e.g. `from models.schema import ...`)
# regardless of the working directory this script is launched from.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from IPython.display import Image
from langchain.messages import HumanMessage
from langgraph.graph import START, StateGraph

from agents.etl_analyst import etl_analyst
from agents.sql_analyst import sql_analyst
from models.schema import DataAgentSchema, RouterSchema
from utils.llm_pick import pick_llm

# Routing is a cheap classification task, so use the "basic" (fastest/
# cheapest) model tier rather than the more expensive tiers used for
# actual SQL/Pandas generation.
llm = pick_llm("basic")

# Force the router's output into RouterSchema's shape ({"answer": "sql"|"etl", ...})
# so the graph can branch on `answer` directly instead of parsing free text.
llm_router = llm.with_structured_output(RouterSchema)


def router_node(state: DataAgentSchema):
    """
    This function routes the user's question to the appropriate agent (SQL or ETL) based on the content of the question.

    Args:
        state (DataAgentSchema): The current state of the Data agent, containing messages and other relevant information.
    Returns:
        DataAgentSchema: The updated state of the Data agent with the routing decision.
    """
    # The most recent message is assumed to be the user's latest request.
    user_question = state.messages[-1].content

    # Ask the LLM to classify the request, then pull just the "answer"
    # field ("sql" or "etl") out of the structured response.
    router_response = llm_router.invoke(user_question).model_dump()["answer"]

    state.route_response = router_response
    return state


def etl_node(state: DataAgentSchema):
    """
    This function invokes the ETL analyst agent to handle the user's question related to ETL operations.

    Args:
        state (DataAgentSchema): The current state of the Data agent, containing messages and other relevant information.

    Returns:
        DataAgentSchema: The updated state of the Data agent.
    """
    # Forward the user's latest message into a fresh ETLAgentSchema state
    # for the etl_analyst sub-graph -- the ETL agent doesn't need to see
    # the Data Agent's own message history, just the current request.
    messages = state.messages[-1].content
    response = etl_analyst.invoke({"messages": [HumanMessage(content=messages)]})

    # Append the ETL agent's full response (its own final state) onto
    # this graph's message list so it's visible in the overall history.
    state.messages = state.messages + [response]

    return state


def sql_node(state: DataAgentSchema):
    """
    This function invokes the SQL analyst agent to handle the user's question related to SQL operations.

    Args:
        state (DataAgentSchema): The current state of the Data agent, containing messages and other relevant information.

    Returns:
        DataAgentSchema: The updated state of the Data agent.
    """
    messages = state.messages[-1].content

    # sql_analyst uses a different, richer state shape (AgentSchema) than
    # this graph does, so every field has to be initialized explicitly
    # here -- the sub-graph doesn't share state with the Data Agent, it
    # starts a brand-new run from scratch each time.
    response = sql_analyst.invoke(
        {
            "messages": [],
            "user_question": f"{messages}",
            "curated_question": "",
            "prompt_query_context": "",
            "generated_sql_query": "",
            "is_safe": "no",
            "comments": "",
            "sql_query_execution_result": "",
            "final_answer": "",
        }
    )

    # Append the SQL agent's full response state onto this graph's
    # message list, same as etl_node does above.
    state.messages = state.messages + [response]

    return state


# --- Build the graph: START -> router_node -> (sql_node | etl_node) -> END ---
data_agent_graph = StateGraph(DataAgentSchema)

data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("etl_node", etl_node)
data_agent_graph.add_node("sql_node", sql_node)

data_agent_graph.add_edge(START, "router_node")


def route_edge(state: DataAgentSchema) -> str:
    """Decide which node to run next based on the router's classification.

    This is a LangGraph "conditional edge" function: it doesn't modify
    state, it just returns the name of the next node to visit.

    Args:
        state (DataAgentSchema): The current graph state, expected to
            already have ``route_response`` set by ``router_node``.

    Returns:
        str: Either "sql_node" or "etl_node".

    Raises:
        ValueError: If ``route_response`` is anything other than "sql" or
            "etl" (which would indicate the router LLM returned an
            unexpected value).
    """
    if state.route_response == "sql":
        return "sql_node"
    elif state.route_response == "etl":
        return "etl_node"
    else:
        raise ValueError(f"Invalid route response: {state.route_response}")


# Wire route_edge's return value ("sql_node"/"etl_node") to the actual
# graph nodes with matching names. Note: since sql_node/etl_node both
# lead straight to the implicit END, no further edges are needed after
# this branch.
data_agent_graph.add_conditional_edges(
    "router_node", route_edge, {"sql_node": "sql_node", "etl_node": "etl_node"}
)

# Compile the graph definition into a runnable object.
data_agent = data_agent_graph.compile()

# Optional: Visualize the graph and save it as a PNG file
# (Useful for sanity-checking the routing logic visually; safe to delete
# this block if you don't need the diagram regenerated on every import.)
img = Image(data_agent.get_graph().draw_mermaid_png())
with open("data_agent_graph.png", "wb") as f:
    f.write(img.data)


if __name__ == "__main__":
    # Manual smoke test: this question should route to "sql_node" since
    # it's a read query about existing data rather than an ETL task.
    response = data_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="What are the different types of Payment Methods we have in our database"
                )
            ],
            "route_response": "",
        }
    )

    print(response)
