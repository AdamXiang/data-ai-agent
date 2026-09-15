"""ETL Analyst agent -- a ReAct-style agent that extracts/transforms data.

This graph handles requests like "extract data from this API and save it
as CSV" or "transform this file and filter for X". It follows the
classic ReAct (Reason + Act) tool-calling loop:

    START -> llm_node --(no tool call)--> END
                       --(tool call)--> tool_node --> llm_node (loop)

``llm_node`` asks the LLM what to do next given the conversation so far.
If the LLM decides it needs a tool (extract or transform), ``tool_node``
runs it and feeds the result back into the conversation, and the loop
repeats until the LLM responds without requesting another tool call.
"""

import os
import sys

# Make the project root importable (e.g. `from models.schema import ...`)
# regardless of the working directory this script is launched from.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import tool
from langgraph.graph import END, START, StateGraph

from models.schema import ETLAgentSchema
from utils.etl_tools import ETLTools
from utils.llm_pick import pick_llm


@tool
def extract_load_tool(url: str, output_folder: str, format: str) -> str:
    """
    This tool extracts the data from the API (url) and loads it into the
    the desired location (output_folder).

    Args:
        url (str): The API endpoint from which to extract data.
        output_folder (str): The folder where the extracted data will be saved.
        format (str): The format in which to save the extracted data (csv, json, parquet).

    Returns:
        str: A message indicating the success or failure of the operation.

    """
    # This tool is a thin LangChain wrapper: all the real extract/load
    # logic lives in ETLTools.extract_load (utils/etl_tools.py), kept
    # there so it can be unit tested without the @tool decorator/LLM layer.
    etl_tools = ETLTools()
    return etl_tools.extract_load(url, output_folder, format)


@tool
def transform_load_tool(
    input_file_path: str, output_folder: str, output_format: str, user_question: str
) -> str:
    """
    This tool transforms the data from the specified file and loads it into the
    desired location (output_folder).

    Args:
        input_file_path (str): The path to the file containing the data to be transformed.
        output_folder (str): The folder where the transformed data will be saved.
        output_format (str): The format in which to save the transformed data (csv, json, parquet).

    Returns:
        str: A message indicating the success or failure of the operation.

    """
    etl_tools = ETLTools()

    # Read a small preview of the source file so the prompt below can
    # show the LLM real column names/values instead of asking it to
    # guess the schema blind.
    top_3_rows = etl_tools.transform_load_context(input_file_path)

    # Writing correct Pandas code needs stronger reasoning than routing
    # or curation, so this uses the "advanced" model tier.
    llm = pick_llm("advanced")

    prompt = f"""
            You are a Python Data Analyst who uses Pandas to analyze data. 
            You need to provide only the Pandas Code that will help to perform the right ETL operations on the data stored in the file : {input_file_path}
            as per the user's question. Do not provide any explanation or comments, only
            the code should be provided. The code should be in a format that can be executed 
            in a Python environment with Pandas installed. 
            Don't write anything else than Pandas Code. \n
            
            Create the Pandas Dataframe from the data stored in the file : {input_file_path} and then 
            write the code to transform and save the data at {output_folder}.
            Here's the user's question: {user_question}\n
            Here's the context of the data you will be analyzing: {top_3_rows}\n

        """

    response = llm.invoke(prompt).content

    # Optional Cleaning: the LLM is asked for raw code, but it sometimes
    # wraps the answer in a ```python ... ``` markdown fence anyway --
    # strip that off so `exec()` receives plain Python.
    pandas_code = response.strip().strip("```").strip().lstrip("python").strip()

    # Execute the Pandas code
    # (see ETLTools.execute_code's docstring for the security caveats of
    # running LLM-generated code directly)
    results = etl_tools.execute_code(pandas_code)

    return f"The data is transformed and saved at {output_folder} in {output_format} format. \n\n Pandas Code Executed: \n {pandas_code} \n\n Execution Result: \n {results}"


# The full set of tools the ETL agent's LLM is allowed to call.
tools = [extract_load_tool, transform_load_tool]


# ETL planning/tool selection needs more reasoning than simple routing,
# so this uses the "advanced" model tier, same as transform_load_tool above.
llm = pick_llm("advanced")
# bind_tools() makes the LLM aware of the available tools' names/schemas
# so it can request a tool call instead of only returning plain text.
llm_bind = llm.bind_tools(tools)


def llm_node(state: ETLAgentSchema):
    """Ask the LLM what to do next, given the conversation so far.

    This is the "Reason" half of the ReAct loop: the LLM looks at the
    full message history (including any prior tool results) and either
    responds with plain text (meaning it's done) or with one or more
    tool calls (meaning it wants ``tool_node`` to run something first).

    Args:
        state (ETLAgentSchema): Current graph state; only ``messages`` is used.

    Returns:
        ETLAgentSchema: The updated state with the LLM's response
        appended to ``messages``.
    """
    messages = state.messages

    prompt = f"""
            You are a Python Data Analyst who has access to tools that can extract and load, 
            transform and load data. You will be provided with a user's question 
            and you would need to perform the right ETL operations as per the user's question. 
            If the operation is performed then inform the user and end the coversation.
            Here's the chat history: {messages}\n
    """

    # Despite the name, this may or may not be a "final" answer -- it can
    # also be a tool-call request, which is_tool_call() checks below.
    final_answer = llm_bind.invoke(prompt)

    state.messages = messages + [final_answer]

    return state


def tool_node(state: ETLAgentSchema):
    """
    This node is responsible for invoking the appropriate tool based on the user's question and the context provided by the LLM.

    This is the "Act" half of the ReAct loop: it reads the tool call(s)
    the LLM requested in its last message, actually runs each matching
    Python tool, and wraps every result in a ``ToolMessage`` so the LLM
    can see the outcome on the next pass through ``llm_node``.

    Args:
        state (ETLAgentSchema): Current graph state; the last message in
            ``state.messages`` is expected to contain ``tool_calls``
            (i.e. it must be an AI message that requested one or more tools).

    Returns:
        ETLAgentSchema: The updated state with one ToolMessage per tool
        call appended to ``messages``.
    """
    tools_results = []

    # Build a name -> tool lookup once so each requested tool_call can be
    # dispatched by name in the loop below.
    tools_by_name = {tool.name: tool for tool in tools}

    # LangGraph stores tool call requests on the most recent AI message.
    tool_calls = state.messages[-1].tool_calls

    for tool_call in tool_calls:
        # Look up and run the specific tool the LLM asked for, passing
        # along the arguments the LLM supplied.
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])

        # tool_call_id links this result back to the specific tool call
        # that requested it -- required so the LLM can match results to
        # requests when multiple tools are called at once.
        tools_results.append(
            ToolMessage(content=observation, tool_call_id=tool_call["id"])
        )

    state.messages = state.messages + tools_results

    return state


# --- Nodes & Edges: wire up the ReAct loop described at the top of this file ---
etl_analyst_graph = StateGraph(ETLAgentSchema)
etl_analyst_graph.add_node("llm_node", llm_node)
etl_analyst_graph.add_node("tool_node", tool_node)

etl_analyst_graph.add_edge(START, "llm_node")


def is_tool_call(state: ETLAgentSchema) -> str:
    """Decide whether the LLM's last message requested a tool call.

    LangGraph conditional-edge function: doesn't modify state, just tells
    the graph where to go next based on whether ``llm_node``'s latest
    response included any tool calls.

    Args:
        state (ETLAgentSchema): Current graph state.

    Returns:
        str: "tool_node" if a tool was requested (loop continues),
        otherwise "end" (the LLM gave a plain-text final answer).
    """
    tool_calls = state.messages[-1].tool_calls

    if tool_calls:
        return "tool_node"
    else:
        return "end"


etl_analyst_graph.add_conditional_edges(
    "llm_node", is_tool_call, {"tool_node": "tool_node", "end": END}
)

# After a tool runs, always go back to the LLM so it can decide the next
# step (another tool call, or a final answer) using the fresh tool result.
etl_analyst_graph.add_edge("tool_node", "llm_node")

etl_analyst = etl_analyst_graph.compile()


if __name__ == "__main__":
    # Compile the Graph (already compiled above via etl_analyst_graph.compile(),
    # this comment just marks the start of the manual smoke test below)

    # Optional: render and save a PNG diagram of the compiled graph, useful
    # for visually confirming the llm_node <-> tool_node loop is wired correctly.
    from IPython.display import Image

    img = Image(etl_analyst.get_graph().draw_mermaid_png())
    with open("etl_analyst_graph.png", "wb") as f:
        f.write(img.data)

    # Manual smoke test #1: an extract-only request. Should trigger exactly
    # one call to extract_load_tool and then a plain-text final answer.
    response = etl_analyst.invoke(
        {
            "messages": [
                HumanMessage(
                    content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder"
                )
            ]
        }
    )

    # Manual smoke test #2 (disabled): a transform request that filters the
    # previously extracted data down to a single Pokemon. Kept here,
    # commented out, as a ready-to-use example -- update the hard-coded
    # /Users/adamchang/... paths for your own machine before re-enabling.
    #     response = etl_analyst.invoke(
    #          {"messages":[HumanMessage(content=f"""
    #             I want to transform the data stored in the '/Users/adamchang/Desktop/Side_Project/AI_Agent/data/extractextracted_data.csv' file
    #             and save the transformed data in the '/Users/adamchang/Desktop/Side_Project/AI_Agent/data/transform' folder in the csv format.
    #             The transformation should filter the data to show bulbasaur pokemon only.
    # """)]}
    #     )

    print(response)
