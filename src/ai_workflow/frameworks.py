"""Resolve and validate supported framework selections from PRD text."""

from __future__ import annotations

import re
from pathlib import Path

ALLOWED_FRAMEWORKS = {
    "frontend": ("react", "nextjs"),
    "mobile": ("flutter",),
    "backend": ("django-drf", "fastapi"),
    "deployment": ("aws",),
}

_PATTERNS = {
    "react": re.compile(r"(?:\bReact\b|\breact(?:\.js|js)\b)"),
    "nextjs": re.compile(r"\bnext(?:\.js|js)\b", re.IGNORECASE),
    "flutter": re.compile(r"\bflutter\b", re.IGNORECASE),
    "django-drf": re.compile(
        r"\b(?:django\s+rest\s+framework|django[- ]?drf|drf)\b", re.IGNORECASE
    ),
    "fastapi": re.compile(r"\bfastapi\b", re.IGNORECASE),
    "aws": re.compile(r"\b(?:aws|amazon\s+web\s+services)\b", re.IGNORECASE),
}

_DECLARATION = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*{1,2})?"
    r"(?P<side>frontend|mobile|backend)\s+(?:framework|technology|stack)"
    r"(?:\*{1,2})?\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

_DEPLOYMENT_DECLARATION = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*{1,2})?"
    r"(?:deployment\s+(?:provider|platform|cloud)|cloud\s+provider)"
    r"(?:\*{1,2})?\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

_AWS_PROVIDER_VALUE = re.compile(r"^\s*(?:aws|amazon\s+web\s+services)\s*[.!]?\s*$", re.I)


def validate_framework(side: str, value: str) -> str:
    """Return a supported canonical value or fail with the complete allowlist."""
    allowed = ALLOWED_FRAMEWORKS[side]
    if value not in allowed:
        raise RuntimeError(
            f"unsupported {side} framework {value!r}; choose one of: {', '.join(allowed)}"
        )
    return value


def detect_prd_frameworks(prd: Path) -> dict[str, str]:
    """Detect explicit supported framework names and reject invalid declarations."""
    text = prd.read_text(encoding="utf-8")
    detected: dict[str, str] = {}
    for line in text.splitlines():
        declaration = _DECLARATION.match(line)
        if not declaration:
            continue
        side = declaration.group("side").lower()
        value = declaration.group("value")
        side_matches = [name for name in ALLOWED_FRAMEWORKS[side] if _PATTERNS[name].search(value)]
        if not side_matches:
            raise RuntimeError(
                f"unsupported {side} framework declaration {value!r}; choose one of: "
                f"{', '.join(ALLOWED_FRAMEWORKS[side])}"
            )
        if len(side_matches) > 1:
            raise RuntimeError(
                f"PRD declares multiple {side} frameworks in {value!r}; choose exactly one"
            )
        if side in detected and detected[side] != side_matches[0]:
            raise RuntimeError(
                f"PRD declares conflicting {side} frameworks: "
                f"{detected[side]}, {side_matches[0]}; choose exactly one"
            )
        detected[side] = side_matches[0]

    for side, allowed in ALLOWED_FRAMEWORKS.items():
        if side in {"deployment", *detected}:
            continue
        matches = [name for name in allowed if _PATTERNS[name].search(text)]
        if len(matches) > 1:
            raise RuntimeError(
                f"PRD declares multiple {side} frameworks: {', '.join(matches)}; choose exactly one"
            )
        if matches:
            detected[side] = matches[0]
    for line in text.splitlines():
        declaration = _DEPLOYMENT_DECLARATION.match(line)
        if not declaration:
            continue
        value = declaration.group("value")
        if not _AWS_PROVIDER_VALUE.fullmatch(value):
            raise RuntimeError(
                f"unsupported deployment provider declaration {value!r}; choose one of: aws"
            )
        detected["deployment"] = "aws"
    return detected


def resolve_frameworks(
    prd: Path,
    frontend: str = "unknown",
    mobile: str = "unknown",
    backend: str = "unknown",
    deployment: str = "unknown",
) -> dict[str, str]:
    """Combine CLI and PRD selections while rejecting conflicts and unsupported values."""
    provided = {
        "frontend": frontend,
        "mobile": mobile,
        "backend": backend,
        "deployment": deployment,
    }
    declared = detect_prd_frameworks(prd)
    resolved: dict[str, str] = {}
    for side in ("frontend", "mobile", "backend", "deployment"):
        selected = provided[side]
        if selected != "unknown":
            validate_framework(side, selected)
        from_prd = declared.get(side)
        if selected != "unknown" and from_prd and selected != from_prd:
            raise RuntimeError(
                f"{side} framework conflict: command selects {selected}, PRD declares {from_prd}"
            )
        resolved[side] = selected if selected != "unknown" else from_prd or "unknown"
    return resolved
