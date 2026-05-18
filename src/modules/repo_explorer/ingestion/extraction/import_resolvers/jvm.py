"""JVM import resolver — Java/Kotlin wildcard and member imports.

Handles:
- Wildcard imports: com.example.* → all files in com/example/
- Member imports: com.example.Constants.VALUE → com/example/Constants.java
- Kotlin top-level function imports via .kt/.kts extensions
"""

from __future__ import annotations

from .utils import SuffixIndex

JAVA_EXTENSIONS = (".java",)
KOTLIN_EXTENSIONS = (".kt", ".kts")


def resolve_jvm_wildcard(
    import_path: str,
    all_files: list[str],
    extensions: tuple[str, ...] = JAVA_EXTENSIONS,
    index: SuffixIndex | None = None,
) -> list[str] | None:
    """Resolve a wildcard JVM import (com.example.*).

    Returns list of all files in the package directory.
    """
    if not import_path.endswith(".*"):
        return None

    package_path = import_path[:-2].replace(".", "/")
    if not package_path:
        return None

    pkg_suffix = "/" + package_path + "/"

    if index is not None:
        results: list[str] = []
        for ext in extensions:
            results.extend(index.get_files_in_dir(pkg_suffix, ext))
        if results:
            return results

    results = []
    for fp in all_files:
        normalized = "/" + fp.replace("\\", "/")
        if pkg_suffix not in normalized:
            continue
        idx = normalized.index(pkg_suffix) + len(pkg_suffix)
        rest = normalized[idx:]
        if "/" in rest:
            continue
        for ext in extensions:
            if rest.endswith(ext):
                results.append(fp)
                break

    return results if results else None


def resolve_jvm_member_import(
    import_path: str,
    all_files: list[str],
    extensions: tuple[str, ...] = JAVA_EXTENSIONS,
    index: SuffixIndex | None = None,
) -> str | None:
    """Resolve a JVM member/static import (com.example.Constants.VALUE).

    The last segment may be a member name, not a file. Try stripping it.
    """
    parts = import_path.split(".")
    if len(parts) < 2:
        return None

    last = parts[-1]

    is_member = (
        last == "*"
        or last[0].islower()
        or (last.isupper() and "_" in last or last.isupper())
    )

    if is_member:
        file_path = "/".join(parts[:-1])
    else:
        file_path = "/".join(parts)

    if index is not None:
        for ext in extensions:
            result = index.get(file_path + ext)
            if result:
                return result
            result = index.get_insensitive(file_path + ext)
            if result:
                return result

    for ext in extensions:
        target = file_path + ext
        for fp in all_files:
            if fp.replace("\\", "/").endswith(target):
                return fp

    return None


def resolve_java_import(
    import_path: str,
    all_files: list[str],
    index: SuffixIndex | None = None,
) -> str | list[str] | None:
    """Resolve a Java import — wildcard or member."""
    if import_path.endswith(".*"):
        return resolve_jvm_wildcard(import_path, all_files, JAVA_EXTENSIONS, index)
    return resolve_jvm_member_import(import_path, all_files, JAVA_EXTENSIONS, index)


def resolve_kotlin_import(
    import_path: str,
    all_files: list[str],
    index: SuffixIndex | None = None,
) -> str | list[str] | None:
    """Resolve a Kotlin import — supports both .kt and .java interop."""
    extensions = KOTLIN_EXTENSIONS + JAVA_EXTENSIONS

    if import_path.endswith(".*"):
        return resolve_jvm_wildcard(import_path, all_files, extensions, index)
    return resolve_jvm_member_import(import_path, all_files, extensions, index)
