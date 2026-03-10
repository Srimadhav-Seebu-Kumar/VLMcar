from pathlib import Path


def test_repo_contains_expected_directories() -> None:
    expected = [
        "backend",
        "firmware",
        "contracts",
        "simulator",
        "tools",
        "prompts",
        "docs",
        "notebooks",
    ]
    root = Path(__file__).resolve().parents[3]
    for item in expected:
        assert (root / item).exists()
