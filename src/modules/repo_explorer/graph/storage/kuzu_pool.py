"""Process-wide singleton managing one kuzu.Database per repo path.

Solves the Kuzu file-locking problem: multiple Database instances on the
same path cause lock conflicts. This pool ensures exactly ONE Database
per path, with multiple Connection objects for concurrent access.

Usage:
    pool = KuzuPool.get()
    db = pool.get_database("/path/to/lbug")        # shared instance
    conn = pool.get_connection("/path/to/lbug")     # new connection

    with pool.write_session("/path/to/lbug") as conn:
        conn.execute("CREATE ...")                  # exclusive write
    # auto-publishes "repo_changed" event on exit
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager

import kuzu
from graph.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class KuzuPool:
    """Singleton pool managing shared kuzu.Database instances."""

    _instance: KuzuPool | None = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self._databases: dict[str, kuzu.Database] = {}
        self._db_lock = threading.Lock()
        self._write_locks: dict[str, threading.Lock] = {}
        self._read_only_paths: set[str] = set()
        self.event_bus = EventBus()

    @classmethod
    def get(cls) -> KuzuPool:
        """Get the process-wide singleton instance."""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = KuzuPool()
                    logger.info("KuzuPool initialized")
        return cls._instance

    def get_database(self, db_path: str, read_only: bool = False) -> kuzu.Database:
        """Get or create the shared Database for a path.

        Args:
            db_path: Absolute or relative path to the KuzuDB directory.
            read_only: If True, open in read-only mode (multiple processes OK).
                If False (default), open read-write; on lock failure, auto-
                fallback to read-only with a warning.
        """
        db_path = os.path.abspath(db_path)

        with self._db_lock:
            if db_path in self._databases:
                # Upgrade: caller needs read-write but cached instance is read-only
                if not read_only and db_path in self._read_only_paths:
                    logger.info(
                        "KuzuPool: upgrading %s from read-only to read-write",
                        db_path,
                    )
                    old_db = self._databases.pop(db_path)
                    self._write_locks.pop(db_path, None)
                    self._read_only_paths.discard(db_path)
                    del old_db
                    # Fall through to _create_database
                else:
                    return self._databases[db_path]

        return self._create_database(db_path, read_only=read_only)

    def _create_database(self, db_path: str, read_only: bool = False) -> kuzu.Database:
        """Create a new Database instance with extensions loaded."""
        with self._db_lock:
            # Double-check after acquiring lock
            if db_path in self._databases:
                return self._databases[db_path]

            # Ensure parent directory exists
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

            # Clean up empty directory (Kuzu can't open it)
            if os.path.isdir(db_path) and not os.listdir(db_path):
                os.rmdir(db_path)

            try:
                db = kuzu.Database(db_path, read_only=read_only)
            except (RuntimeError, OSError) as exc:
                err_msg = str(exc).lower()
                lock_keywords = ("lock", "locked", "busy", "permission")
                if not read_only and any(kw in err_msg for kw in lock_keywords):
                    logger.warning(
                        "KuzuPool: lock conflict for %s — falling back to "
                        "read-only (%s)",
                        db_path,
                        exc,
                    )
                    db = kuzu.Database(db_path, read_only=True)
                    self._read_only_paths.add(db_path)
                else:
                    raise

            # Load extensions (only for read-write databases)
            if db_path not in self._read_only_paths:
                conn = kuzu.Connection(db)
                for ext_cmd in (
                    "INSTALL fts; LOAD EXTENSION fts;",
                    "INSTALL VECTOR; LOAD EXTENSION VECTOR;",
                ):
                    try:
                        conn.execute(ext_cmd)
                    except Exception as exc:
                        logger.debug("Extension (may already exist): %s", exc)
                del conn  # release setup connection

            mode = "read-only" if db_path in self._read_only_paths else "read-write"
            self._databases[db_path] = db
            self._write_locks[db_path] = threading.Lock()
            logger.info("KuzuPool: opened database at %s (%s)", db_path, mode)
            return db

    def get_connection(self, db_path: str, read_only: bool = False) -> kuzu.Connection:
        """Get a new Connection from the shared Database."""
        db = self.get_database(db_path, read_only=read_only)
        return kuzu.Connection(db)

    def is_read_only(self, db_path: str) -> bool:
        """Check if a database was opened in read-only mode."""
        return os.path.abspath(db_path) in self._read_only_paths

    @contextmanager
    def write_session(self, db_path: str):
        """Context manager for exclusive write access.

        Acquires a per-path write lock, yields a Connection, and publishes
        a 'repo_changed' event on successful exit.
        """
        db_path = os.path.abspath(db_path)
        if db_path in self._read_only_paths:
            raise RuntimeError(
                f"Database at {db_path} is read-only "
                "(another process holds the write lock)"
            )
        db = self.get_database(db_path)

        write_lock = self._write_locks[db_path]
        write_lock.acquire()
        conn = kuzu.Connection(db)
        try:
            yield conn
        finally:
            del conn
            write_lock.release()
            self.event_bus.publish(
                "repo_changed",
                {
                    "db_path": db_path,
                    "timestamp": time.time(),
                },
            )

    def close(self, db_path: str) -> None:
        """Close and remove a Database (e.g., on repo delete)."""
        db_path = os.path.abspath(db_path)
        with self._db_lock:
            db = self._databases.pop(db_path, None)
            self._write_locks.pop(db_path, None)
            self._read_only_paths.discard(db_path)
            if db is not None:
                del db
                logger.info("KuzuPool: closed database at %s", db_path)

    def close_all(self) -> None:
        """Shutdown — close all databases."""
        with self._db_lock:
            paths = list(self._databases.keys())
            for path in paths:
                db = self._databases.pop(path, None)
                self._write_locks.pop(path, None)
                if db is not None:
                    del db
            self._read_only_paths.clear()
            logger.info("KuzuPool: closed all %d database(s)", len(paths))

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing). Closes all databases first."""
        if cls._instance is not None:
            cls._instance.close_all()
            cls._instance = None
