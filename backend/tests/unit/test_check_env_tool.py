from __future__ import annotations

from types import ModuleType

from tools.check_env import (
    CheckResult,
    check_modules,
    check_ollama_binary,
    check_python_version,
    check_required_env_vars,
    render_results,
)


def test_python_version_check_passes_for_supported_version() -> None:
    result = check_python_version((3, 11))
    assert result.ok is True


def test_python_version_check_fails_for_old_version() -> None:
    result = check_python_version((3, 10))
    assert result.ok is False


def test_modules_check_reports_missing_module() -> None:
    def import_fn(name: str) -> ModuleType:
        if name == "httpx":
            raise ImportError("missing")
        return ModuleType(name)

    result = check_modules(import_fn=import_fn, required=("fastapi", "httpx"))
    assert result.ok is False
    assert "httpx" in result.detail


def test_env_var_check_fails_when_values_missing() -> None:
    result = check_required_env_vars(env={"APP_ENV": "dev"}, required=("APP_ENV", "DATABASE_URL"))
    assert result.ok is False
    assert "DATABASE_URL" in result.detail


def test_ollama_binary_check_passes() -> None:
    result = check_ollama_binary(which_fn=lambda _name: "C:/ollama/ollama.exe")
    assert result.ok is True


def test_render_results_returns_false_for_any_fail() -> None:
    results = [
        CheckResult(name="a", ok=True, detail="ok"),
        CheckResult(name="b", ok=False, detail="fail"),
    ]
    assert render_results(results) is False
