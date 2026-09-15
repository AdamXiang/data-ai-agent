"""Command-line entry point for the Data AI Agent.

Running this script sends a single hard-coded user request straight into
the top-level ``data_agent`` graph (see ``agents/data_agent.py``). That
graph looks at the request, decides whether it's a SQL question or an ETL
task, hands it off to the matching sub-agent (``sql_analyst`` or
``etl_analyst``), and returns the final conversation state.

This file is meant as a quick manual smoke test / usage example, not as
the "real" way the agent will be triggered in production. Swap out the
``content`` string below to try different prompts.

Usage::

    python main.py
"""

from langchain_core.messages import HumanMessage

from agents.data_agent import data_agent

if __name__ == "__main__":
    # Kick off the agent graph with a single user message. "route_response"
    # starts empty because the router node is the one that fills it in.
    response = data_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="I want to extract the data from the API endpoint 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in the csv folder"
                )
            ],
            "route_response": "",
        }
    )

    # `response` is the final DataAgentSchema state (as a dict), including
    # the full message history and whichever sub-agent handled the request.
    print(response)
