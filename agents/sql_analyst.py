"""SQL Analyst agent -- turns a natural-language question into a safe SQL query.

This graph is the "sql" branch of the top-level Data Agent
(``agents/data_agent.py``). It runs a fixed, linear pipeline with one
safety branch built in:

    Curate_Question
        -> Prompt_Query_Context   (attach live DB schema info)
        -> Generate_SQL           (LLM writes the SQL query)
        -> Is_Safe_SQL            (a second LLM checks it's read-only)
        -> [safe]   Execute_SQL   -> Present_Final_Answer -> END
        -> [unsafe] Cancel_SQL_if_Not_Safe -> END

The safety check (``Is_Safe_SQL`` / ``is_safe_sql_condition``) exists so a
misinterpreted question can never result in an UPDATE/DELETE/DROP etc.
being run against the real database -- only read-only queries are
allowed through to ``Execute_SQL``.
"""

import os
import re
import sys

# Add the parent directory to the system path to allow imports from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from psycopg2 import DatabaseError

from models.schema import AgentSchema, JudgeAgentSchema
from utils.database import Database
from utils.llm_pick import pick_llm

# ----------------- AI Agent Dev ------------------


def clean_sql_string(raw_sql: str) -> str:
    """
    Clean the SQL string by removing any unwanted characters or formatting.

    Args:
        raw_sql (str): The raw SQL string to be cleaned.
    Returns:
        str: The cleaned SQL string.
    """
    # Remove any leading/trailing whitespace and newlines
    cleaned = raw_sql.strip()

    # LLMs sometimes wrap SQL in a markdown code fence (```sql ... ``` or
    # ``` ... ```) even when explicitly told not to. Strip those fences
    # off (leading fence first, then a trailing one) so what's left is
    # SQL text ready to hand straight to the database driver.
    cleaned = re.sub(r"^```sql\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def curate_question(state: AgentSchema) -> AgentSchema:
    """
    Curate the question based on the current state.

    Args:
        state (AgentSchema): The current state of the agent.

    Returns:
        AgentSchema: The updated state with the curated question.
    """
    user_question = state.user_question

    # Curation is a lightweight rephrasing task, so the cheap/fast model
    # tier is enough here -- no need for "advanced" reasoning yet.
    llm = pick_llm("basic")  # You can change the level as needed

    # Ask the LLM to tidy up the raw user question (fix typos, make it
    # unambiguous, etc.) before it's used to build the SQL-generation prompt.
    curated_question = llm.invoke(
        f"Curate the following question: {user_question}"
    ).content

    state.curated_question = curated_question
    # Record the curated question in the conversation history too, so the
    # full run is auditable from `messages` alone.
    state.messages = state.messages + [
        HumanMessage(content=f"Curated Question: {curated_question}")
    ]

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

    # Read DB connection settings from the environment (see .env.template)
    # rather than hard-coding them, so the same code works across
    # local/dev/prod without changes.
    connection_details = {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_DATABASE"),
    }

    # Open a fresh connection just to pull schema metadata (table/column
    # names, types, sample rows) -- a second connection is opened later
    # in execute_sql() to actually run the generated query.
    database_object = Database(connection_details)

    schema_info = database_object.get_schema_details("public")

    # Constructing the prompt query for the agent to generate the SQL query.
    # The prompt is deliberately strict about output format (raw SQL only,
    # no markdown, no explanation) because this text is executed directly
    # as SQL later -- any extra commentary here would break generate_sql().
    prompt = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language 
    query into Postgres SQL query that can be executed on the database. You are provided 
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that 
    you can understand the structure of the database and generate an accurate SQL query.
    Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    ready to be executed without any modifications. 

    Follow the steps below: 
    CRITICAL INSTRUCTIONS FOR OUTPUT FORMAT:
    1. Return ONLY the raw SQL query.
    2. NEVER use markdown formatting.
    3. NEVER wrap the query in ```sql or ``` blocks.
    4. The very first character of your response must be the SQL keyword (e.g., SELECT).
    5. Any explanation or markdown tags will cause a system crash.

    User's Original Query: {curated_question}

    Database Schema Details:
    {schema_info}
    """

    state.prompt_query_context = prompt

    return state


def generate_sql(state: AgentSchema) -> AgentSchema:
    """
    Generate the SQL query based on the curated question and prompt query context.

    Args:
        state (AgentSchema): The current state of the agent.
    Returns:
        AgentSchema: The updated state with the generated SQL query.
    """
    prompt_query_context = state.prompt_query_context

    # Writing correct SQL against a real schema needs stronger reasoning
    # than the curation step, so this uses the "advanced" model tier.
    llm = pick_llm("advanced")  # You can change the level as needed

    raw_sql_query = llm.invoke(prompt_query_context).content

    # Strip any markdown fencing the LLM might have added despite the
    # prompt's instructions not to (see clean_sql_string's docstring).
    cleaned_sql_query = clean_sql_string(raw_sql_query)

    state.generated_sql_query = cleaned_sql_query

    return state


def is_safe_sql(state: AgentSchema) -> AgentSchema:
    """
    Check if the generated SQL query is safe to execute.

    Args:
        state (AgentSchema): The current state of the agent.
    Returns:
        AgentSchema: The updated state with the safety check result.
    """
    sql_query = state.generated_sql_query

    # This is the guardrail step: a second LLM call independently reviews
    # the query generated above before anything touches the real database.
    llm = pick_llm("advanced")  # You can change the level as needed
    # Force the judge's output into JudgeAgentSchema's shape so the graph
    # can branch on `answer` ("yes"/"no") programmatically.
    llm_judge = llm.with_structured_output(schema=JudgeAgentSchema)

    safety_check_prompt = f"""
    You are an SQL Judge for data security. Your task is to determine whether the SQL query is 
    safe or not. The SQL query should only be used for data retrieval and should not modify the 
    database in any way. Neither the SQL query nor the prompt should contain any SQL commands that can modify the
    database, such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands that can change
    the structure or content of the database. If the SQL query is safe, respond with 'yes' otherwise respond with 
    'no'. Additionally, provide comments explaining your decision.

    Here's the SQL query to evaluate:
    SQL Query: {sql_query}
    """
    response = llm_judge.invoke(safety_check_prompt).model_dump()

    # "yes" means the query is read-only and safe to run; "no" means it
    # contains (or the judge suspects it contains) a data-modifying
    # statement. is_safe_sql_condition() below reads this field to decide
    # whether to route to Execute_SQL or Cancel_SQL_if_Not_Safe.
    state.is_safe = response["answer"]
    state.comments = response["comments"]

    return state


def cancel_sql_if_not_safe(state: AgentSchema) -> AgentSchema:
    """
    Cancel the SQL query execution if it is not safe.

    Args:
        state (AgentSchema): The current state of the agent.
    Returns:
        AgentSchema: The updated state with the final answer if the SQL query is not safe.
    """

    comments = state.comments

    # This node is only reached when is_safe_sql_condition() routed here
    # because state.is_safe == "no" -- so the query is deliberately never
    # executed; we just surface the judge's reasoning to the user instead.
    state.final_answer = (
        f"The generated SQL query is not safe to execute. Comments: {comments}"
    )
    state.messages = state.messages + [AIMessage(content=f"{state.final_answer}")]

    return state


def execute_sql(state: AgentSchema) -> AgentSchema:
    """
    Execute the generated SQL query if it is safe.

    Args:
        state (AgentSchema): The current state of the agent.
    Returns:
        AgentSchema: The updated state with the SQL query execution result and final answer.
    """
    sql_query = state.generated_sql_query

    # Reached only when is_safe_sql_condition() confirmed the query is
    # read-only, so it's safe to open a connection and actually run it.
    connection_details = {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_DATABASE"),
    }

    database_object = Database(connection_details)

    try:
        execution_result = database_object.execute_query(sql_query)
        state.sql_query_execution_result = str(execution_result)
    except DatabaseError as e:
        # Surface DB-level failures (bad syntax the safety check didn't
        # catch, permission errors, etc.) directly as the final answer
        # instead of letting the graph crash.
        state.sql_query_execution_result = str(e)
        state.final_answer = f"Error executing SQL query: {e}"

    return state


def present_final_answer(state: AgentSchema) -> AgentSchema:
    """
    Present the final answer to the user.

    Args:
        state (AgentSchema): The current state of the agent.
    Returns:
        AgentSchema: The updated state with the final answer presented to the user.
    """
    execution_result = state.sql_query_execution_result
    curated_question = state.curated_question

    # Summarizing a result set in plain English is a lighter task than
    # generating SQL, so the cheap/fast model tier is enough here.
    llm = pick_llm("basic")  # You can change the level as needed

    prompt = f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer. \n
    Here is the execution result: {execution_result} \n
    Here is the user's original question: {curated_question}
    """

    llm_response = llm.invoke(prompt).content  # Get the final answer from the LLM

    state.final_answer = llm_response
    state.messages = state.messages + [
        AIMessage(content=f"{llm_response}")
    ]  # Append the final answer to the messages list

    return state


# --- Build the graph: wire the linear pipeline described at the top of this file ---
sql_agent_graph = StateGraph(AgentSchema)

# Add nodes to the graph. Each node's `metadata` description is purely
# documentation for graph visualizations (e.g. LangGraph Studio) -- it
# has no effect on execution.
sql_agent_graph.add_node(
    "Curate_Question",
    curate_question,
    metadata={"description": "Curate the user's question for clarity."},
)
sql_agent_graph.add_node(
    "Prompt_Query_Context",
    prompt_query_context,
    metadata={
        "description": "Generate a detailed prompt with SQL DB context to help the agent generate the SQL query."
    },
)
sql_agent_graph.add_node(
    "Generate_SQL",
    generate_sql,
    metadata={
        "description": "Generate the SQL query based on the curated question and prompt query context."
    },
)
sql_agent_graph.add_node(
    "Is_Safe_SQL",
    is_safe_sql,
    metadata={"description": "Check if the generated SQL query is safe to execute."},
)
sql_agent_graph.add_node(
    "Cancel_SQL_if_Not_Safe",
    cancel_sql_if_not_safe,
    metadata={"description": "Cancel the SQL query execution if it is not safe."},
)
sql_agent_graph.add_node(
    "Execute_SQL",
    execute_sql,
    metadata={"description": "Execute the generated SQL query if it is safe."},
)
sql_agent_graph.add_node(
    "Present_Final_Answer",
    present_final_answer,
    metadata={"description": "Present the final answer to the user."},
)


# The first four steps are strictly linear: each one only depends on the
# previous step's output, so there's no branching yet.
sql_agent_graph.add_edge(START, "Curate_Question")
sql_agent_graph.add_edge("Curate_Question", "Prompt_Query_Context")
sql_agent_graph.add_edge("Prompt_Query_Context", "Generate_SQL")
sql_agent_graph.add_edge("Generate_SQL", "Is_Safe_SQL")


def is_safe_sql_condition(state: AgentSchema) -> str:
    """
    Condition function to check if the generated SQL query is safe.

    LangGraph conditional-edge function for the safety branch: reads the
    verdict ``is_safe_sql`` wrote into state and decides whether execution
    continues (``Execute_SQL``) or stops (``Cancel_SQL_if_Not_Safe``).

    Args:
        state (AgentSchema): The current state of the agent.
    Returns:
        str: The name of the next node to transition to based on the safety check result.
    """
    if state.is_safe.lower() == "yes":
        return "Execute_SQL"
    else:
        return "Cancel_SQL_if_Not_Safe"


# This is the one branch point in an otherwise linear graph: everything
# before Is_Safe_SQL always runs; after it, exactly one of the two
# branches below runs depending on is_safe_sql_condition()'s verdict.
sql_agent_graph.add_conditional_edges(
    "Is_Safe_SQL",
    is_safe_sql_condition,
    {"Execute_SQL": "Execute_SQL", "Cancel_SQL_if_Not_Safe": "Cancel_SQL_if_Not_Safe"},
)
# Unsafe queries end the run immediately with an explanation -- they never
# reach Execute_SQL. Safe queries run, then get summarized for the user.
sql_agent_graph.add_edge("Cancel_SQL_if_Not_Safe", END)
sql_agent_graph.add_edge("Execute_SQL", "Present_Final_Answer")
sql_agent_graph.add_edge("Present_Final_Answer", END)


# Compile the graph to ensure all nodes and edges are valid
sql_analyst = sql_agent_graph.compile()


if __name__ == "__main__":
    # Optional: render and save a PNG diagram of the compiled graph, useful
    # for visually confirming the linear pipeline + safety branch above.
    from IPython.display import Image

    img = Image(sql_analyst.get_graph().draw_mermaid_png())
    with open("sql_analyst_graph.png", "wb") as f:
        f.write(img.data)

    # Manual smoke test: every AgentSchema field has to be seeded here
    # since this script invokes the graph directly (bypassing data_agent.py,
    # which would normally build this dict for us in sql_node()).
    input_schema = {
        "messages": [],
        "user_question": "What are the different types of Payment Methods we have in our database",
        "curated_question": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "no",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": "",
    }

    # Execute the graph with the input schema
    sql_analyst_response = sql_analyst.invoke(input_schema)
