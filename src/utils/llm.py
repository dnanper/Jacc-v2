import warnings
from typing import Any

from langchain_openai import ChatOpenAI

from .llm_guard import guard

# langchain-openai dumps parsed Responses objects, and pydantic warns once per union
# member on every structured-output call. Output is unaffected.
warnings.filterwarnings("ignore", message="Pydantic serializer warnings", category=UserWarning)


def build_llm(model: str) -> ChatOpenAI:
    """Build the LangChain OpenAI chat model used by SWE-Bench runs."""

    guard("chat")
    kwargs: dict[str, Any] = {"model": model}
    if model.startswith("gpt-5"):
        # gpt-5 reasoning models reject function tools on /v1/chat/completions.
        kwargs["use_responses_api"] = True
    else:
        kwargs["temperature"] = 0.0
    return ChatOpenAI(**kwargs)
