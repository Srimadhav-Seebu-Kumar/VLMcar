from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from PIL import Image, ImageDraw

from simulator.maps import MapDefinition

_WALL_CHARS: Final[frozenset[str]] = frozenset({"#"})
_GOAL_CHAR: Final[str] = "G"
_START_HEADINGS: Final[dict[str, float]] = {
    "S": 0.0,
    ">": 0.0,
    "<": math.pi,
    "^": -math.pi / 2.0,
    "v": math.pi / 2.0,
}
_DRIVABLE_CHARS: Final[frozenset[str]] = frozenset({".", _GOAL_CHAR, *_START_HEADINGS.keys()})

_ROAD_COLOR: Final[tuple[int, int, int]] = (170, 170, 170)
_WALL_COLOR: Final[tuple[int, int, int]] = (35, 20, 20)
_GOAL_COLOR: Final[tuple[int, int, int]] = (40, 190, 80)
_CAR_COLOR: Final[tuple[int, int, int]] = (40, 90, 240)


@dataclass(frozen=True)
class KinematicsConfig:
    """Motion model for pulse-based simulator control."""

    forward_speed_cells_per_s: float = 2.2
    turn_rate_deg_per_s: float = 95.0


@dataclass(frozen=True)
class EgoCameraConfig:
    """Ego-frame projection configuration."""

    width: int = 320
    height: int = 240
    forward_range_cells: float = 4.8
    lateral_range_cells: float = 2.2
    back_range_cells: float = 0.8


@dataclass(frozen=True)
class VehicleState:
    """Continuous vehicle pose inside the grid world."""

    x: float
    y: float
    heading_rad: float
    collided: bool = False

    def as_dict(self) -> dict[str, float | bool]:
        return {
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "heading_rad": round(self.heading_rad, 6),
            "collided": self.collided,
        }


class GridWorld:
    """Small deterministic world used for backend-loop simulation."""

    def __init__(
        self,
        definition: MapDefinition,
        kinematics: KinematicsConfig | None = None,
    ) -> None:
        self._map = definition
        self._kinematics = kinematics or KinematicsConfig()
        self._height = len(definition.rows)
        if self._height == 0:
            raise ValueError("map must contain at least one row")
        self._width = len(definition.rows[0])
        if self._width == 0:
            raise ValueError("map rows must not be empty")
        for row in definition.rows:
            if len(row) != self._width:
                raise ValueError(f"map={definition.name!r} has non-rectangular rows")

        self._start_state, self._goal_xy = self._parse_markers(definition)

    @property
    def map_name(self) -> str:
        return self._map.name

    @property
    def map_rows(self) -> tuple[str, ...]:
        return self._map.rows

    @property
    def goal_xy(self) -> tuple[float, float]:
        return self._goal_xy

    def initial_state(self) -> VehicleState:
        return self._start_state

    def is_goal_reached(self, state: VehicleState, tolerance_cells: float = 0.45) -> bool:
        dx = state.x - self._goal_xy[0]
        dy = state.y - self._goal_xy[1]
        return math.hypot(dx, dy) <= tolerance_cells

    def apply_command(
        self, state: VehicleState, heading_deg: int, throttle: float, duration_ms: int
    ) -> VehicleState:
        """Apply continuous heading + throttle command to vehicle state."""

        duration_s = max(0.0, min(float(duration_ms), 1000.0)) / 1000.0
        if throttle <= 0.0 or duration_s <= 0.0:
            return VehicleState(x=state.x, y=state.y, heading_rad=state.heading_rad, collided=False)

        # Apply heading as turn rate
        clamped_heading = max(-90, min(90, heading_deg))
        turn_fraction = clamped_heading / 90.0
        heading_change = math.radians(self._kinematics.turn_rate_deg_per_s) * turn_fraction * duration_s
        next_heading = state.heading_rad + heading_change

        # Speed scaled by throttle
        speed = self._kinematics.forward_speed_cells_per_s * throttle
        travel = speed * duration_s
        next_x = state.x + math.cos(next_heading) * travel
        next_y = state.y + math.sin(next_heading) * travel
        if not self._is_drivable(next_x, next_y):
            return VehicleState(
                x=state.x,
                y=state.y,
                heading_rad=next_heading,
                collided=True,
            )

        return VehicleState(x=next_x, y=next_y, heading_rad=next_heading, collided=False)

    def render_ego_frame(self, state: VehicleState, config: EgoCameraConfig) -> Image.Image:
        image = Image.new("RGB", (config.width, config.height), color=_WALL_COLOR)
        pixels = image.load()
        if pixels is None:
            raise RuntimeError("failed to access image pixel buffer")
        denom_w = max(config.width - 1, 1)
        denom_h = max(config.height - 1, 1)
        cos_theta = math.cos(state.heading_rad)
        sin_theta = math.sin(state.heading_rad)
        fwd_span = config.forward_range_cells + config.back_range_cells

        for py in range(config.height):
            forward = config.forward_range_cells - (py / denom_h) * fwd_span
            for px in range(config.width):
                lateral_right = ((px / denom_w) * 2.0 - 1.0) * config.lateral_range_cells
                world_x = state.x + cos_theta * forward - sin_theta * lateral_right
                world_y = state.y + sin_theta * forward + cos_theta * lateral_right
                cell = self._sample_cell(world_x, world_y)
                pixels[px, py] = self._color_for_cell(cell)

        draw = ImageDraw.Draw(image)
        hood_y = config.height - 1
        hood = [
            (int(config.width * 0.30), hood_y),
            (int(config.width * 0.70), hood_y),
            (int(config.width * 0.60), int(config.height * 0.84)),
            (int(config.width * 0.40), int(config.height * 0.84)),
        ]
        draw.polygon(hood, fill=(25, 25, 25))
        return image

    def render_topdown(self, state: VehicleState, pixels_per_cell: int = 40) -> Image.Image:
        width_px = self._width * pixels_per_cell
        height_px = self._height * pixels_per_cell
        image = Image.new("RGB", (width_px, height_px), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        for row_idx, row in enumerate(self._map.rows):
            for col_idx, cell in enumerate(row):
                x0 = col_idx * pixels_per_cell
                y0 = row_idx * pixels_per_cell
                x1 = x0 + pixels_per_cell - 1
                y1 = y0 + pixels_per_cell - 1
                draw.rectangle((x0, y0, x1, y1), fill=self._color_for_cell(cell))

        cx = state.x * pixels_per_cell
        cy = state.y * pixels_per_cell
        heading = state.heading_rad
        nose = (
            cx + math.cos(heading) * pixels_per_cell * 0.45,
            cy + math.sin(heading) * pixels_per_cell * 0.45,
        )
        left = (
            cx + math.cos(heading + 2.4) * pixels_per_cell * 0.32,
            cy + math.sin(heading + 2.4) * pixels_per_cell * 0.32,
        )
        right = (
            cx + math.cos(heading - 2.4) * pixels_per_cell * 0.32,
            cy + math.sin(heading - 2.4) * pixels_per_cell * 0.32,
        )
        draw.polygon([nose, left, right], fill=_CAR_COLOR)
        return image

    def _parse_markers(self, definition: MapDefinition) -> tuple[VehicleState, tuple[float, float]]:
        start: VehicleState | None = None
        goal: tuple[float, float] | None = None
        for row_idx, row in enumerate(definition.rows):
            for col_idx, cell in enumerate(row):
                if cell in _START_HEADINGS:
                    if start is not None:
                        raise ValueError(f"map={definition.name!r} has multiple start cells")
                    start = VehicleState(
                        x=col_idx + 0.5,
                        y=row_idx + 0.5,
                        heading_rad=_START_HEADINGS[cell],
                    )
                if cell == _GOAL_CHAR:
                    if goal is not None:
                        raise ValueError(f"map={definition.name!r} has multiple goal cells")
                    goal = (col_idx + 0.5, row_idx + 0.5)
        if start is None:
            raise ValueError(f"map={definition.name!r} does not define a start cell")
        if goal is None:
            raise ValueError(f"map={definition.name!r} does not define a goal cell")
        return start, goal

    def _sample_cell(self, x: float, y: float) -> str:
        row_idx = math.floor(y)
        col_idx = math.floor(x)
        if row_idx < 0 or row_idx >= self._height or col_idx < 0 or col_idx >= self._width:
            return "#"
        return self._map.rows[row_idx][col_idx]

    def _is_drivable(self, x: float, y: float) -> bool:
        return self._sample_cell(x, y) in _DRIVABLE_CHARS

    def _color_for_cell(self, cell: str) -> tuple[int, int, int]:
        if cell in _WALL_CHARS:
            return _WALL_COLOR
        if cell == _GOAL_CHAR:
            return _GOAL_COLOR
        if cell in _DRIVABLE_CHARS:
            return _ROAD_COLOR
        return _WALL_COLOR
