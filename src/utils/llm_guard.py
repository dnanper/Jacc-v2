"""Human-approval gate for paid LLM traffic.

Any code path that would spend money on a provider API calls ``guard()`` first.
It refuses unless the human started the process with ``JACC_LLM_OK=1``; a Claude
Code hook blocks the agent from setting that variable itself. Once approved,
every successful outbound request is appended to ``.tmp/llm_calls.log`` so the
Stop hook can report the count.
"""

from __future__ import annotations

import os
import pathlib
import threading

ENV_VAR = "JACC_LLM_OK"
LOG = pathlib.Path(__file__).resolve().parents[2] / ".tmp" / "llm_calls.log"
_LOCK = threading.Lock()
_installed = False


def guard(what: str = "llm") -> None:
    """Abort unless the human approved real LLM calls for this process."""
    if os.environ.get(ENV_VAR) != "1":
        raise RuntimeError(
            f"Real LLM calls are blocked ({what}). Stub the model in tests, or "
            "ask the human to re-run with: JACC_LLM_OK=1 <command>"
        )
    _install_counter()


def _install_counter() -> None:
    """Count successful non-local HTTP responses by patching httpx once."""
    global _installed
    if _installed:
        return
    import httpx

    send = httpx.Client.send

    def counted(self, request, *args, **kwargs):
        response = send(self, request, *args, **kwargs)
        host = request.url.host
        if response.status_code < 400 and host not in ("localhost", "127.0.0.1"):
            with _LOCK:
                LOG.parent.mkdir(parents=True, exist_ok=True)
                with LOG.open("a") as fh:
                    fh.write(f"{host}{request.url.path}\n")
        return response

    # ponytail: sync httpx only; patch AsyncClient.send too if async calls appear.
    httpx.Client.send = counted
    _installed = True
