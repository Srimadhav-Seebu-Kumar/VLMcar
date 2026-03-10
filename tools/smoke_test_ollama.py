from __future__ import annotations

import json
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


def main() -> int:
    request = Request(
        "http://127.0.0.1:11434/api/version",
        method="GET",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
            version = payload.get("version", "unknown")
            print(f"ollama reachable: version={version}")
            return 0
    except URLError as exc:
        print(f"ollama smoke check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
