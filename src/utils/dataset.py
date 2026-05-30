from typing import Any


def load_dataset(*args: Any, **kwargs: Any) -> Any:
    """Lazy wrapper so importing this module does not require datasets."""

    try:
        from datasets import load_dataset as hf_load_dataset
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'datasets'. Run `uv sync` after installing project dependencies."
        ) from exc
    return hf_load_dataset(*args, **kwargs)
