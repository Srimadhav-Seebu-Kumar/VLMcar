from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MapDefinition:
    """ASCII map used by the grid simulator."""

    name: str
    description: str
    rows: tuple[str, ...]


_BUILTIN_MAPS: tuple[MapDefinition, ...] = (
    MapDefinition(
        name="straight_corridor",
        description="Simple straight lane from start to goal.",
        rows=(
            "############",
            "#>.......G##",
            "############",
        ),
    ),
    MapDefinition(
        name="left_turn",
        description="Single left turn corridor with one-cell lane width.",
        rows=(
            "############",
            "#>.....#####",
            "######.#####",
            "######.#####",
            "######.#####",
            "######G#####",
            "############",
        ),
    ),
    MapDefinition(
        name="right_turn",
        description="Single right turn corridor with one-cell lane width.",
        rows=(
            "############",
            "#####.....<#",
            "#####.######",
            "#####.######",
            "#####.######",
            "#####G######",
            "############",
        ),
    ),
)


def list_builtin_maps() -> tuple[MapDefinition, ...]:
    """Return all simulator maps."""

    return _BUILTIN_MAPS


def get_builtin_map(name: str) -> MapDefinition:
    """Resolve one named simulator map."""

    for definition in _BUILTIN_MAPS:
        if definition.name == name:
            return definition
    available = ", ".join(map_def.name for map_def in _BUILTIN_MAPS)
    raise ValueError(f"unknown map={name!r}; available={available}")
