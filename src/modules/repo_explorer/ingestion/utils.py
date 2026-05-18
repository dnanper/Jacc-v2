def generate_id(label: str, name: str) -> str:
    """Generate a deterministic node ID: ``Label:name``."""
    return f"{label}:{name}"
