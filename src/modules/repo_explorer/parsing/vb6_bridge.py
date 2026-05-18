"""VB6 parser bridge — delegates parsing to Node.js + web-tree-sitter WASM.

Calls the JS bridge script (parse_vb.mjs) which uses the tree-sitter-vb-dotnet
WASM grammar to parse VB6 code. The JSON AST is converted to mock tree-sitter
node objects that integrate with CSG's existing pipeline.

This avoids needing a C compiler or native Python tree-sitter binding for VB6.

Note: VB6 retains its own bridge script (parse_vb.mjs) because it requires
specialized VB6→VB.NET preprocessing. The generic WASM bridge
(wasm_bridge.py + parse_generic.mjs) is used for other WASM-bridged languages.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

# Re-export WASMNode/WASMTree as VB6Node/VB6Tree for backwards compatibility.
# All code that references VB6Node/VB6Tree continues to work unchanged.
from .wasm_bridge import WASMNode as VB6Node  # noqa: F401
from .wasm_bridge import WASMTree as VB6Tree  # noqa: F401
from .wasm_bridge import _json_to_node

logger = logging.getLogger(__name__)

_JS_BRIDGE_DIR = Path(__file__).resolve().parent / "js_bridge"
_PARSE_SCRIPT = _JS_BRIDGE_DIR / "parse_vb.mjs"
_NODE_BIN: str | None = None


def _find_node() -> str | None:
    """Find the Node.js binary."""
    global _NODE_BIN
    if _NODE_BIN is not None:
        return _NODE_BIN
    _NODE_BIN = shutil.which("node")
    return _NODE_BIN


# ── Bridge call ──────────────────────────────────────────────────────


def parse_vb6(content: str, file_path: str | None = None) -> VB6Tree:
    """Parse VB6 source code via the Node.js bridge.

    Args:
        content: VB6 source code as a string.
        file_path: Optional file path (used for .frm/.cls preprocessing).

    Returns:
        A VB6Tree with a root VB6Node, compatible with tree-sitter API.

    Raises:
        RuntimeError: If Node.js is not available or parsing fails.
    """
    node_bin = _find_node()
    if node_bin is None:
        raise RuntimeError(
            "Node.js not found. Install Node.js to enable VB6 parsing.\n"
            "VB6 support uses web-tree-sitter (WASM) via a Node.js bridge."
        )

    # Pass source via stdin to avoid temp files
    ext = Path(file_path).suffix.lower() if file_path else ".bas"
    fake_name = file_path or f"module{ext}"

    try:
        result = subprocess.run(
            [node_bin, str(_PARSE_SCRIPT), "-", fake_name],
            input=content,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_JS_BRIDGE_DIR),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"VB6 parser timed out for {file_path}")
    except FileNotFoundError:
        raise RuntimeError(f"Node.js not found at {node_bin}")

    if result.returncode != 0:
        logger.warning("VB6 parse error for %s: %s", file_path, result.stderr[:500])
        raise RuntimeError(f"VB6 parser failed: {result.stderr[:200]}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"VB6 parser returned invalid JSON: {exc}")

    ast_data = data.get("ast", {})
    errors = data.get("errors", [])

    if errors:
        logger.debug("VB6 parse: %d errors in %s", len(errors), file_path)

    root = _json_to_node(ast_data)
    return VB6Tree(root_node=root)


def is_vb6_available() -> bool:
    """Check if VB6 parsing is available (Node.js + WASM grammar present)."""
    node = _find_node()
    if node is None:
        return False
    wasm = _JS_BRIDGE_DIR / "tree-sitter-vb_dotnet.wasm"
    return wasm.exists()
