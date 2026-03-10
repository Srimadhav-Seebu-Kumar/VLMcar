from __future__ import annotations

import argparse
import importlib
import os
import shutil
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import ModuleType

REQUIRED_MODULES: tuple[str, ...] = (
    "fastapi",
    "pydantic",
    "httpx",
    "sqlalchemy",
    "jsonschema",
)

REQUIRED_ENV_VARS: tuple[str, ...] = (
    "APP_ENV",
    "LOG_LEVEL",
    "BACKEND_HOST",
    "BACKEND_PORT",
    "DATABASE_URL",
    "ARTIFACTS_DIR",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "MODEL_TIMEOUT_S",
    "MIN_CONFIDENCE",
    "MAX_PULSE_MS",
    "QUALITY_MIN_SCORE",
    "QUALITY_MIN_BRIGHTNESS",
    "QUALITY_MAX_BRIGHTNESS",
    "QUALITY_MIN_BLUR_SCORE",
)

MIN_PYTHON: tuple[int, int] = (3, 11)


@dataclass(frozen=True)
class CheckResult:
    """Result of one environment precondition check."""

    name: str
    ok: bool
    detail: str


def check_python_version(version: tuple[int, int] | None = None) -> CheckResult:
    """Ensure interpreter satisfies minimum supported version."""

    major_minor = version if version is not None else (sys.version_info.major, sys.version_info.minor)
    is_ok = major_minor >= MIN_PYTHON
    detail = f"detected={major_minor[0]}.{major_minor[1]} required>={MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    return CheckResult(name="python", ok=is_ok, detail=detail)


def check_modules(
    import_fn: Callable[[str], ModuleType] = importlib.import_module,
    required: Sequence[str] = REQUIRED_MODULES,
) -> CheckResult:
    """Validate that required Python modules can be imported."""

    missing: list[str] = []
    for module_name in required:
        try:
            import_fn(module_name)
        except ImportError:
            missing.append(module_name)

    if not missing:
        return CheckResult(name="python-modules", ok=True, detail="all required modules installed")

    return CheckResult(
        name="python-modules",
        ok=False,
        detail=f"missing modules: {', '.join(missing)}",
    )


def check_required_env_vars(
    env: Mapping[str, str] | None = None,
    required: Sequence[str] = REQUIRED_ENV_VARS,
) -> CheckResult:
    """Validate required configuration variables are set and non-empty."""

    env_values = env if env is not None else os.environ
    missing = [key for key in required if not env_values.get(key)]
    if not missing:
        return CheckResult(name="env-vars", ok=True, detail="all required env vars present")

    return CheckResult(
        name="env-vars",
        ok=False,
        detail=f"missing env vars: {', '.join(missing)}",
    )


def check_ollama_binary(which_fn: Callable[[str], str | None] = shutil.which) -> CheckResult:
    """Ensure Ollama CLI is available for local offline inference."""

    path = which_fn("ollama")
    if path is None:
        return CheckResult(name="ollama", ok=False, detail="ollama binary not found in PATH")

    return CheckResult(name="ollama", ok=True, detail=f"found at {path}")


def render_results(results: Sequence[CheckResult]) -> bool:
    """Print check summary and return True when all checks pass."""

    all_ok = True
    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")
        all_ok = all_ok and result.ok
    return all_ok


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local development environment prerequisites.")
    parser.add_argument(
        "--skip-ollama",
        action="store_true",
        help="Skip checking ollama binary presence.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    results: list[CheckResult] = [
        check_python_version(),
        check_modules(),
        check_required_env_vars(),
    ]
    if not args.skip_ollama:
        results.append(check_ollama_binary())

    return 0 if render_results(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
