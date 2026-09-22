"""Guard blocks unapproved LLM calls and counts approved ones."""

from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils import llm_guard


def _fake_response(status: int = 200):
    return types.SimpleNamespace(status_code=status)


def test() -> None:
    llm_guard.LOG = Path(__file__).with_name("_guard_test.log")
    llm_guard.LOG.unlink(missing_ok=True)

    import os

    os.environ.pop(llm_guard.ENV_VAR, None)
    try:
        llm_guard.guard("chat")
        raise AssertionError("guard must refuse without human approval")
    except RuntimeError:
        pass

    os.environ[llm_guard.ENV_VAR] = "1"
    import httpx

    original = httpx.Client.send
    httpx.Client.send = lambda self, request, *a, **k: _fake_response()
    try:
        llm_guard.guard("chat")
        url = httpx.URL("https://api.openai.com/v1/chat/completions")
        request = httpx.Request("POST", url)
        client = httpx.Client()
        client.send(request)
        client.send(request)
        client.send(httpx.Request("GET", "http://localhost:3000/ingest"))
        assert llm_guard.LOG.read_text().count("\n") == 2, "only remote calls count"
    finally:
        httpx.Client.send = original
        llm_guard._installed = False
        llm_guard.LOG.unlink(missing_ok=True)
        os.environ.pop(llm_guard.ENV_VAR, None)
    print("ok")


if __name__ == "__main__":
    test()
