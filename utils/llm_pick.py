from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

# Load environment variables from .env file
load_dotenv()


def pick_llm(model_level: str) -> ChatAnthropic:
    """
    Pick the appropriate LLM based on the model level.

    Args:
        model_level (str): The level of the model ('basic', 'advanced', 'premium').

    Returns:
        ChatAnthropic: The selected LLM instance.
    """
    normalized_level = model_level.strip().lower()

    if normalized_level == "basic":
        return ChatAnthropic(model="claude-haiku-4-5", temperature=0)

    elif normalized_level == "advanced":
        return ChatAnthropic(model="claude-sonnet-4-6", temperature=0)

    elif normalized_level == "premium":
        return ChatAnthropic(model="claude-opus-4-6", temperature=0)

    else:
        raise ValueError(f"Unknown model level: {model_level}")


# Example usage, you can change the level as needed
llm = pick_llm("basic")

# Example invocation of the selected LLM
print(llm.invoke("Hello, how are you?"))
