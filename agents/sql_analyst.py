import os
import sys

# Add the parent directory to the system path to allow imports from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.schema import AgentSchema
from utils.llm_pick import pick_llm

# ----------------- AI Agent Dev ------------------


def curate_question(state: AgentSchema) -> AgentSchema:
    """
    Curate the question based on the current state.

    Args:
        state (AgentSchema): The current state of the agent.

    Returns:
        AgentSchema: The updated state with the curated question.
    """
    user_question = state.user_question

    llm = pick_llm("basic")  # You can change the level as needed

    curated_question = llm.invoke(f"Curate the following question: {user_question}")

    state.curated_question = curated_question

    return state


def prompt_query_context(state: AgentSchema) -> AgentSchema:
    """
    Generate a detailed prompt with SQL DB context to help the agent generate the SQL query.

    Args:
        state (AgentSchema): The current state of the agent.

    Returns:
        AgentSchema: The updated state with the prompt query context.
    """
    curated_question = state.curated_question

    llm = pick_llm("basic")  # You can change the level as needed

    prompt_query_context = llm.invoke(
        f"Generate a detailed prompt with SQL DB context for the following curated question: {curated_question}"
    )

    state.prompt_query_context = prompt_query_context

    return state
