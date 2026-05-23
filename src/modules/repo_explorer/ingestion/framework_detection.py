"""Framework detection — path-based and AST-based.

Port of GitNexus ingestion/framework-detection.ts.

Detects frameworks from:
1. File path patterns (e.g. Next.js pages/, Django views.py)
2. AST definition text (decorators/annotations/attributes)

Returns FrameworkHint with entry point multipliers, or None for unknown
frameworks (which causes a 1.0 multiplier — no bonus, no penalty).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import SupportedLanguages


@dataclass(frozen=True)
class FrameworkHint:
    framework: str
    entry_point_multiplier: float
    reason: str


def detect_framework_from_path(file_path: str) -> FrameworkHint | None:
    """Detect framework from file path patterns."""
    p = file_path.lower().replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p

    if "/pages/" in p and "/_" not in p and "/api/" not in p:
        if p.endswith((".tsx", ".ts", ".jsx", ".js")):
            return FrameworkHint("nextjs-pages", 3.0, "nextjs-page")

    if "/app/" in p and (
        p.endswith("page.tsx")
        or p.endswith("page.ts")
        or p.endswith("page.jsx")
        or p.endswith("page.js")
    ):
        return FrameworkHint("nextjs-app", 3.0, "nextjs-app-page")

    if "/pages/api/" in p or ("/app/" in p and "/api/" in p and p.endswith("route.ts")):
        return FrameworkHint("nextjs-api", 3.0, "nextjs-api-route")

    if "/app/" in p and (p.endswith("layout.tsx") or p.endswith("layout.ts")):
        return FrameworkHint("nextjs-app", 2.0, "nextjs-layout")

    if "/routes/" in p and p.endswith((".ts", ".js")):
        return FrameworkHint("express", 2.5, "routes-folder")

    if "/controllers/" in p and p.endswith((".ts", ".js")):
        return FrameworkHint("mvc", 2.5, "controllers-folder")

    if "/handlers/" in p and p.endswith((".ts", ".js")):
        return FrameworkHint("handlers", 2.5, "handlers-folder")

    if p.endswith("views.py"):
        return FrameworkHint("django", 3.0, "django-views")

    if p.endswith("urls.py"):
        return FrameworkHint("django", 2.0, "django-urls")

    if ("/routers/" in p or "/endpoints/" in p or "/routes/" in p) and p.endswith(
        ".py"
    ):
        return FrameworkHint("fastapi", 2.5, "api-routers")

    if "/api/" in p and p.endswith(".py") and not p.endswith("__init__.py"):
        return FrameworkHint("python-api", 2.0, "api-folder")

    if ("/controller/" in p or "/controllers/" in p) and p.endswith(".java"):
        return FrameworkHint("spring", 3.0, "spring-controller")

    if p.endswith("controller.java"):
        return FrameworkHint("spring", 3.0, "spring-controller-file")

    if ("/service/" in p or "/services/" in p) and p.endswith(".java"):
        return FrameworkHint("java-service", 1.8, "java-service")

    if ("/controller/" in p or "/controllers/" in p) and p.endswith(".kt"):
        return FrameworkHint("spring-kotlin", 3.0, "spring-kotlin-controller")

    if p.endswith("controller.kt"):
        return FrameworkHint("spring-kotlin", 3.0, "spring-kotlin-controller-file")

    if "/routes/" in p and p.endswith(".kt"):
        return FrameworkHint("ktor", 2.5, "ktor-routes")

    if "/controllers/" in p and p.endswith(".cs"):
        return FrameworkHint("aspnet", 3.0, "aspnet-controller")

    if p.endswith("controller.cs"):
        return FrameworkHint("aspnet", 3.0, "aspnet-controller-file")

    if ("/services/" in p or "/service/" in p) and p.endswith(".cs"):
        return FrameworkHint("aspnet", 1.8, "aspnet-service")

    if p.endswith("/program.cs") or p.endswith("/startup.cs"):
        return FrameworkHint("aspnet", 3.0, "aspnet-entry")

    if ("/handlers/" in p or "/handler/" in p) and p.endswith(".go"):
        return FrameworkHint("go-http", 2.5, "go-handlers")

    if "/routes/" in p and p.endswith(".go"):
        return FrameworkHint("go-http", 2.5, "go-routes")

    if p.endswith("/main.go"):
        return FrameworkHint("go", 3.0, "go-main")

    if ("/handlers/" in p or "/routes/" in p) and p.endswith(".rs"):
        return FrameworkHint("rust-web", 2.5, "rust-handlers")

    if p.endswith("/main.rs"):
        return FrameworkHint("rust", 3.0, "rust-main")

    if p.endswith(("/main.c", "/main.cpp", "/main.cc")):
        return FrameworkHint("c-cpp", 3.0, "c-main")

    if "/routes/" in p and p.endswith(".php"):
        return FrameworkHint("laravel", 3.0, "laravel-routes")

    if ("/http/controllers/" in p or "/controllers/" in p) and p.endswith(".php"):
        return FrameworkHint("laravel", 3.0, "laravel-controller")

    if p.endswith("controller.php"):
        return FrameworkHint("laravel", 3.0, "laravel-controller-file")

    if ("/bin/" in p or "/exe/" in p) and p.endswith(".rb"):
        return FrameworkHint("ruby", 2.5, "ruby-executable")

    if p.endswith(("/appdelegate.swift", "/scenedelegate.swift", "/app.swift")):
        return FrameworkHint("ios", 3.0, "ios-app-entry")

    return None


FRAMEWORK_AST_PATTERNS: dict[str, list[str]] = {
    "nestjs": ["@Controller", "@Get", "@Post", "@Put", "@Delete", "@Patch"],
    "fastapi": ["@app.get", "@app.post", "@app.put", "@app.delete", "@router.get"],
    "flask": ["@app.route", "@blueprint.route"],
    "spring": [
        "@RestController",
        "@Controller",
        "@GetMapping",
        "@PostMapping",
        "@RequestMapping",
    ],
    "aspnet": ["[ApiController]", "[HttpGet]", "[HttpPost]", "[Route]"],
    "laravel": ["Route::get", "Route::post", "Route::put", "Route::delete"],
    "actix": ["#[get", "#[post", "#[put", "#[delete", "HttpRequest", "HttpResponse"],
    "rails": ["ApplicationController", "ApplicationRecord", "before_action"],
}

_AST_PATTERNS_BY_LANGUAGE: dict[str, list[tuple[str, float, str, list[str]]]] = {
    SupportedLanguages.JAVASCRIPT: [
        ("nestjs", 3.2, "nestjs-decorator", FRAMEWORK_AST_PATTERNS["nestjs"]),
    ],
    SupportedLanguages.TYPESCRIPT: [
        ("nestjs", 3.2, "nestjs-decorator", FRAMEWORK_AST_PATTERNS["nestjs"]),
    ],
    SupportedLanguages.PYTHON: [
        ("fastapi", 3.0, "fastapi-decorator", FRAMEWORK_AST_PATTERNS["fastapi"]),
        ("flask", 2.8, "flask-decorator", FRAMEWORK_AST_PATTERNS["flask"]),
    ],
    SupportedLanguages.JAVA: [
        ("spring", 3.2, "spring-annotation", FRAMEWORK_AST_PATTERNS["spring"]),
    ],
    SupportedLanguages.KOTLIN: [
        (
            "spring-kotlin",
            3.2,
            "spring-kotlin-annotation",
            FRAMEWORK_AST_PATTERNS["spring"],
        ),
    ],
    SupportedLanguages.C_SHARP: [
        ("aspnet", 3.2, "aspnet-attribute", FRAMEWORK_AST_PATTERNS["aspnet"]),
    ],
    SupportedLanguages.PHP: [
        ("laravel", 3.0, "php-route-attribute", FRAMEWORK_AST_PATTERNS["laravel"]),
    ],
    SupportedLanguages.GO: [
        (
            "go-http",
            2.5,
            "go-http-handler",
            ["http.Handler", "http.HandlerFunc", "ServeHTTP"],
        ),
    ],
    SupportedLanguages.RUST: [
        ("actix-web", 3.0, "actix-attribute", FRAMEWORK_AST_PATTERNS["actix"]),
    ],
    SupportedLanguages.RUBY: [
        ("rails", 3.0, "rails-pattern", FRAMEWORK_AST_PATTERNS["rails"]),
    ],
}

_AST_PATTERNS_LOWERED: dict[str, list[tuple[str, float, str, list[str]]]] = {
    lang: [
        (fw, mult, reason, [p.lower() for p in patterns])
        for fw, mult, reason, patterns in configs
    ]
    for lang, configs in _AST_PATTERNS_BY_LANGUAGE.items()
}


def detect_framework_from_ast(
    language: SupportedLanguages,
    definition_text: str,
) -> FrameworkHint | None:
    """Detect framework entry points from AST definition text."""
    if not language or not definition_text:
        return None

    configs = _AST_PATTERNS_LOWERED.get(language)
    if not configs:
        return None

    normalized = definition_text.lower()

    for framework, multiplier, reason, patterns in configs:
        for pattern in patterns:
            if pattern in normalized:
                return FrameworkHint(framework, multiplier, reason)

    return None
