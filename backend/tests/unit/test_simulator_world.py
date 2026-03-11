from __future__ import annotations

from backend.app.schemas.enums import Action
from simulator.maps import get_builtin_map
from simulator.world import EgoCameraConfig, GridWorld


def test_world_initial_state_and_goal_are_defined() -> None:
    world = GridWorld(get_builtin_map("straight_corridor"))
    state = world.initial_state()
    goal_x, goal_y = world.goal_xy

    assert state.x > 0
    assert state.y > 0
    assert goal_x > state.x
    assert goal_y == state.y


def test_world_forward_motion_progresses_vehicle() -> None:
    world = GridWorld(get_builtin_map("straight_corridor"))
    state = world.initial_state()

    next_state = world.apply_command(state, Action.FORWARD, 250)

    assert next_state.x > state.x
    assert next_state.collided is False


def test_world_ego_render_produces_expected_dimensions() -> None:
    world = GridWorld(get_builtin_map("straight_corridor"))
    image = world.render_ego_frame(
        world.initial_state(),
        EgoCameraConfig(width=128, height=96),
    )

    assert image.size == (128, 96)
