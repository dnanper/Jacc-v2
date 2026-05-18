"""LRU cache for parsed AST trees — avoids re-parsing the same file."""

from __future__ import annotations

from collections import OrderedDict


class ASTCache:
    """Bounded LRU cache for tree-sitter parse trees.

    Capacity defaults to 50 trees. When full, the least-recently-used
    tree is evicted.
    """

    def __init__(self, capacity: int = 50) -> None:
        self._capacity = capacity
        self._cache: OrderedDict[str, object] = OrderedDict()

    def get(self, file_path: str):
        """Retrieve a cached parse tree, or None if not cached."""
        if file_path in self._cache:
            self._cache.move_to_end(file_path)
            return self._cache[file_path]
        return None

    def put(self, file_path: str, tree) -> None:
        """Store a parse tree, evicting the oldest if at capacity."""
        if file_path in self._cache:
            self._cache.move_to_end(file_path)
        else:
            if len(self._cache) >= self._capacity:
                self._cache.popitem(last=False)
        self._cache[file_path] = tree

    def clear(self) -> None:
        """Evict all cached trees."""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
