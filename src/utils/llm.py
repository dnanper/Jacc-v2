from typing import Any

from langchain_openai import ChatOpenAI


def build_llm(model: str) -> ChatOpenAI:
    """Build the LangChain OpenAI chat model used by SWE-Bench runs."""

    kwargs: dict[str, Any] = {"model": model}
    if not model.startswith("gpt-5"):
        kwargs["temperature"] = 0.0
    return ChatOpenAI(**kwargs)
