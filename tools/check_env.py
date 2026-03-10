from __future__ import annotations

import importlib
import shutil
import sys

REQUIRED_MODULES = [
    "fastapi",
    "pydantic",
    "httpx",
    "sqlalchemy",
]


def check_modules() -> list[str]:
    missing: list[str] = []
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    return missing


def check_ollama_binary() -> bool:
    return shutil.which("ollama") is not None


def main() -> int:
    missing_modules = check_modules()
    ollama_exists = check_ollama_binary()

    if missing_modules:
        print(f"Missing Python modules: {', '.join(missing_modules)}", file=sys.stderr)
    else:
        print("All required Python modules are installed.")

    if not ollama_exists:
        print("Ollama binary not found in PATH.", file=sys.stderr)
    else:
        print("Ollama binary detected.")

    return 0 if not missing_modules and ollama_exists else 1


if __name__ == "__main__":
    raise SystemExit(main())
