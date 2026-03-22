# Module: `backend/app/services/inference`

## Overview
Inference abstractions, prompt construction, response parsing, and Ollama adapter implementation.

## Architecture Diagram
```mermaid
graph TB
    root["backend/app/services/inference"]
    root --> __init___py["__init__.py"]
    root --> base_py["base.py"]
    root --> ollama_native_py["ollama_native.py"]
    root --> parser_py["parser.py"]
    root --> prompt_manager_py["prompt_manager.py"]
```

## Submodules
| Submodule | Source | Kind |
| --- | --- | --- |
| `__init__.py` | `backend/app/services/inference/__init__.py` | Python module |
| `base.py` | `backend/app/services/inference/base.py` | Python module |
| `ollama_native.py` | `backend/app/services/inference/ollama_native.py` | Python module |
| `parser.py` | `backend/app/services/inference/parser.py` | Python module |
| `prompt_manager.py` | `backend/app/services/inference/prompt_manager.py` | Python module |

## Routes
This module does not declare HTTP routes.

## Functions
No top-level functions were detected in this module.
