"""Entry point scoring for process detection.

Port of GitNexus ingestion/entry-point-scoring.ts.

Calculates entry point scores based on:
1. Call ratio (callees / (callers + 1))
2. Export status (exported functions get 2x multiplier)
3. Name patterns (language-specific + universal)
4. Framework detection (path-based multipliers)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import SupportedLanguages
from .framework_detection import detect_framework_from_path

UNIVERSAL_ENTRY_POINT_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(main|init|bootstrap|start|run|setup|configure)$", re.I),
    re.compile(r"^handle[A-Z]"),
    re.compile(r"^on[A-Z]"),
    re.compile(r"Handler$"),
    re.compile(r"Controller$"),
    re.compile(r"^process[A-Z]"),
    re.compile(r"^execute[A-Z]"),
    re.compile(r"^perform[A-Z]"),
    re.compile(r"^dispatch[A-Z]"),
    re.compile(r"^trigger[A-Z]"),
    re.compile(r"^fire[A-Z]"),
    re.compile(r"^emit[A-Z]"),
]

_LANGUAGE_ENTRY_POINT_PATTERNS: dict[str, list[re.Pattern]] = {
    SupportedLanguages.JAVASCRIPT: [
        re.compile(r"^use[A-Z]"),  # React/Vue hooks
        re.compile(r"^app$"),  # Express instance
        re.compile(r"^handler$"),  # AWS Lambda / serverless
        re.compile(r"^middleware$"),
    ],
    SupportedLanguages.TYPESCRIPT: [
        re.compile(r"^use[A-Z]"),  # React/Vue hooks
        re.compile(r"^app$"),  # Express instance
        re.compile(r"^handler$"),  # AWS Lambda / serverless
        re.compile(r"^middleware$"),
    ],
    SupportedLanguages.PYTHON: [
        re.compile(r"^app$"),
        re.compile(r"^(get|post|put|delete|patch)_", re.I),
        re.compile(r"^api_"),
        re.compile(r"^view_"),
        re.compile(r"^(upgrade|downgrade)$"),  # Alembic migrations
        re.compile(r"^(index|detail|list|create|update|delete)$"),  # Django CBV
    ],
    SupportedLanguages.JAVA: [
        re.compile(r"^do[A-Z]"),
        re.compile(r"^create[A-Z]"),
        re.compile(r"^build[A-Z]"),
        re.compile(r"Service$"),
        re.compile(r"^(setUp|tearDown)$"),  # JUnit lifecycle
    ],
    SupportedLanguages.KOTLIN: [
        re.compile(r"^on(Create|Start|Resume|Pause|Stop|Destroy)$"),
        re.compile(r"^do[A-Z]"),
        re.compile(r"Service$"),
        re.compile(r"^on(CreateView|ViewCreated|Attach|Detach)$"),  # Fragment
    ],
    SupportedLanguages.C_SHARP: [
        re.compile(r"^(Get|Post|Put|Delete|Patch)"),
        re.compile(r"Action$"),
        re.compile(r"^On[A-Z]"),
        re.compile(r"^Configure$"),
        re.compile(r"Service$"),
        re.compile(r"^Invoke(Async)?$"),  # ASP.NET middleware
        re.compile(r"^(Up|Down)$"),  # EF migrations
    ],
    SupportedLanguages.GO: [
        re.compile(r"Handler$"),
        re.compile(r"^Serve"),
        re.compile(r"^New[A-Z]"),
        re.compile(r"^init$"),  # package init
        re.compile(r"^(Before|After)(Create|Update|Delete|Save)$"),  # GORM hooks
    ],
    SupportedLanguages.RUST: [
        re.compile(r"^(get|post|put|delete)_handler$", re.I),
        re.compile(r"^handle_"),
        re.compile(r"^new$"),
        re.compile(r"^run$"),
        re.compile(r"^test_"),  # #[test] functions
    ],
    SupportedLanguages.C: [
        re.compile(r"^main$"),
        re.compile(r"^init_"),
        re.compile(r"_init$"),
        re.compile(r"^handle_"),
        re.compile(r"_handler$"),
        re.compile(r"_callback$"),
        re.compile(r"^(ISR|IRQ)"),  # Interrupt handlers
    ],
    SupportedLanguages.C_PLUS_PLUS: [
        re.compile(r"^main$"),
        re.compile(r"^Create[A-Z]"),
        re.compile(r"^Run$"),
        re.compile(r"^Start$"),
        re.compile(r"^(Tick|Update|Draw|Render)$"),  # Game/graphics loops
    ],
    SupportedLanguages.SWIFT: [
        re.compile(r"^viewDidLoad$"),
        re.compile(r"^body$"),
        re.compile(r"ViewController$"),
        re.compile(r"^(viewWill|viewDid)[A-Z]"),  # Full UIKit lifecycle
        re.compile(r"^scene\("),  # SceneDelegate
        re.compile(r"^application\("),  # AppDelegate
    ],
    SupportedLanguages.PHP: [
        re.compile(r"Controller$"),
        re.compile(r"^handle$"),
        re.compile(r"^(index|show|store|update|destroy)$"),
        re.compile(r"^(register|boot)$"),  # Service providers
        re.compile(r"^__construct$"),
    ],
    SupportedLanguages.RUBY: [
        re.compile(r"^call$"),
        re.compile(r"^perform$"),
        re.compile(r"^execute$"),
        re.compile(r"^(index|show|new|create|edit|update|destroy)$"),  # Rails actions
        re.compile(r"^(before|after|around)_"),  # ActiveRecord/Controller callbacks
    ],
    SupportedLanguages.VB6: [
        re.compile(r"^Form_(Load|Initialize|Activate|Unload|Resize)$"),
        re.compile(r"^MDIForm_(Load|Initialize)$"),
        re.compile(r"_Click$"),  # Button/control click handlers
        re.compile(r"_Change$"),  # Input change handlers
        re.compile(r"_Timer$"),  # Timer events
        re.compile(r"^Class_(Initialize|Terminate)$"),
        re.compile(r"^Sub Main$"),
    ],
}

_MERGED_PATTERNS: dict[str, list[re.Pattern]] = {
    lang: UNIVERSAL_ENTRY_POINT_PATTERNS + patterns
    for lang, patterns in _LANGUAGE_ENTRY_POINT_PATTERNS.items()
}


UTILITY_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(get|set|is|has|can|should|will|did)[A-Z]"),
    re.compile(r"^_"),
    re.compile(r"^(format|parse|validate|convert|transform)", re.I),
    re.compile(r"^(log|debug|error|warn|info)$", re.I),
    re.compile(r"^(to|from)[A-Z]"),
    re.compile(r"^(encode|decode)", re.I),
    re.compile(r"^(serialize|deserialize)", re.I),
    re.compile(r"Helper$"),
    re.compile(r"Util$"),
    re.compile(r"Utils$"),
    re.compile(r"^utils?$", re.I),
    re.compile(r"^helpers?$", re.I),
]


@dataclass
class EntryPointScoreResult:
    score: float
    reasons: list[str]


def calculate_entry_point_score(
    name: str,
    language: SupportedLanguages,
    is_exported: bool,
    caller_count: int,
    callee_count: int,
    file_path: str = "",
) -> EntryPointScoreResult:
    """Calculate an entry point score for a function/method.

    Higher scores indicate better entry point candidates.
    Score = baseScore * exportMultiplier * nameMultiplier * frameworkMultiplier
    """
    reasons: list[str] = []

    all_patterns = _MERGED_PATTERNS.get(language, UNIVERSAL_ENTRY_POINT_PATTERNS)
    is_entry_name = any(p.search(name) for p in all_patterns)

    if callee_count == 0:
        if is_entry_name:
            # Entry-point-patterned symbols (Form_Load, _Click, handler) get a
            # floor score even when they have no outgoing calls (event sinks).
            return EntryPointScoreResult(
                score=0.5, reasons=["no-outgoing-calls", "entry-pattern-override"]
            )
        return EntryPointScoreResult(score=0, reasons=["no-outgoing-calls"])

    base_score = callee_count / (caller_count + 1)
    reasons.append(f"base:{base_score:.2f}")

    export_multiplier = 2.0 if is_exported else 1.0
    if is_exported:
        reasons.append("exported")

    name_multiplier = 1.0

    # Entry-point pattern takes precedence over utility pattern.
    # Prevents HTTP GET handlers (getUser) from being demoted as utilities.
    if is_entry_name:
        name_multiplier = 1.5
        reasons.append("entry-pattern")
    elif any(p.search(name) for p in UTILITY_PATTERNS):
        name_multiplier = 0.3
        reasons.append("utility-pattern")

    framework_multiplier = 1.0
    if file_path:
        hint = detect_framework_from_path(file_path)
        if hint:
            framework_multiplier = hint.entry_point_multiplier
            reasons.append(f"framework:{hint.reason}")

    final_score = (
        base_score * export_multiplier * name_multiplier * framework_multiplier
    )

    return EntryPointScoreResult(score=final_score, reasons=reasons)


def is_test_file(file_path: str) -> bool:
    """Check if a file path is a test file (should be excluded from entry points)."""
    p = file_path.lower().replace("\\", "/")

    return (
        ".test." in p
        or ".spec." in p
        or "__tests__/" in p
        or "__mocks__/" in p
        or "/test/" in p
        or "/tests/" in p
        or "/testing/" in p
        or p.endswith("_test.py")
        or "/test_" in p
        or p.endswith("_test.go")
        or "/src/test/" in p
        or p.endswith("_spec.rb")
        or p.endswith("_test.rb")
        or "/spec/" in p
        or p.endswith("test.php")
    )


def is_utility_file(file_path: str) -> bool:
    """Check if a file path is likely a utility/helper file."""
    p = file_path.lower().replace("\\", "/")

    return (
        "/utils/" in p
        or "/util/" in p
        or "/helpers/" in p
        or "/helper/" in p
        or "/common/" in p
        or "/shared/" in p
        or "/lib/" in p
        or p.endswith("/utils.ts")
        or p.endswith("/utils.js")
        or p.endswith("_utils.py")
        or p.endswith("_helpers.py")
    )
