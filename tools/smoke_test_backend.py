from __future__ import annotations

import sys
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    url = "http://127.0.0.1:8000/health"
    try:
        with urlopen(url, timeout=2) as response:
            body = response.read().decode("utf-8")
            print(f"backend healthy: {body}")
            return 0
    except URLError as exc:
        print(f"backend smoke check failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
