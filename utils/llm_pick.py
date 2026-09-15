"""Factory helper for picking which Claude model an agent node should use.

Different nodes across the SQL and ETL agents need different amounts of
"reasoning power" -- a quick question-curation step can run on a small,
cheap model, while generating a correct SQL query or writing Pandas code
benefits from a stronger model. Rather than hard-coding a model name in
every node, callers ask for a "level" (``basic`` / ``advanced`` /
``premium``) and this module maps that to a concrete ``ChatAnthropic``
instance. This keeps model choice centralized in one place, so upgrading
a model later only requires a change here.
"""

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

# Load environment variables (e.g. ANTHROPIC_API_KEY) from a local .env
# file, so `ChatAnthropic` can authenticate without extra setup.
load_dotenv()


def pick_llm(model_level: str) -> ChatAnthropic:
    """
    Pick the appropriate LLM based on the model level.

    This acts as a small factory: instead of every agent node hard-coding
    a specific Claude model name, they ask for a tier and get back a
    ready-to-use ``ChatAnthropic`` client. ``temperature=0`` is used for
    every tier so responses stay as deterministic and repeatable as
    possible, which matters for tasks like generating SQL.

    Args:
        model_level (str): The level of the model ('basic', 'advanced', 'premium').
            - "basic": fastest/cheapest, good for simple classification or
              rephrasing tasks (e.g. routing, question curation).
            - "advanced": stronger reasoning, used for tasks like SQL
              generation and safety judging.
            - "premium": the most capable (and most expensive) tier, for
              when accuracy matters more than latency/cost.

    Returns:
        ChatAnthropic: The selected LLM instance.

    Raises:
        ValueError: If ``model_level`` is not one of "basic", "advanced",
            or "premium" (case-insensitive, surrounding whitespace ignored).
    """
    # Normalize the input so callers can pass "Basic", " basic ", etc.
    # without triggering a false "unknown level" error.
    normalized_level = model_level.strip().lower()

    if normalized_level == "basic":
        return ChatAnthropic(model="claude-haiku-4-5", temperature=0)

    elif normalized_level == "advanced":
        return ChatAnthropic(model="claude-sonnet-4-6", temperature=0)

    elif normalized_level == "premium":
        return ChatAnthropic(model="claude-opus-4-6", temperature=0)

    else:
        # Fail loudly rather than silently falling back to a default model,
        # so a typo in a caller's code doesn't go unnoticed.
        raise ValueError(f"Unknown model level: {model_level}")
