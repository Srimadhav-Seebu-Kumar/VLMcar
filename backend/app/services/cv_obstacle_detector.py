"""OpenCV-based obstacle zone detector for synthetic indoor scenes.

Segments floor vs obstacle pixels by color, divides the image into a 3x3 grid
(left/center/right × near/mid/far), and reports obstacle density per zone.
"""
from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image


def detect_obstacle_zones(image_bytes: bytes) -> dict:
    """Analyze image for obstacles and return zone-based spatial metadata.

    Returns a dict with:
        obstacle_zones: {zone_name: fraction_blocked}  (0.0–1.0)
        clear_path: best lateral direction ("LEFT", "CENTER", "RIGHT", or "NONE")
        closest_obstacle_zone: name of the zone with highest near-row obstacle density
        obstacles_detected: approximate number of obstacle contours
    """
    img = np.array(Image.open(BytesIO(image_bytes)).convert("RGB"))
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

    # --- Build obstacle mask ---
    # In synthetic scenes: floor is warm tan/brown, walls are cool gray, ceiling is light gray.
    # Obstacles are distinctly colored (dark brown furniture, orange cones, blue boxes, skin tones).
    #
    # Strategy: identify floor, wall, ceiling pixels, then everything else is "obstacle".

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # Ceiling: very light, top portion (y < 35% of height)
    ceiling_mask = np.zeros((h, w), dtype=np.uint8)
    ceiling_region = gray[: int(h * 0.35), :]
    ceiling_mask[: int(h * 0.35), :] = (ceiling_region > 200).astype(np.uint8) * 255

    # Floor: warm-toned, bottom portion (y > 50% of height)
    # Floor has R > G > B pattern and medium brightness
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    floor_color = (
        (r > 120) & (r < 210) &
        (g > 100) & (g < 190) &
        (b > 70) & (b < 170) &
        (r >= g) & (g >= b)  # warm tone: R >= G >= B
    )
    floor_region_mask = np.zeros((h, w), dtype=bool)
    floor_region_mask[int(h * 0.45):, :] = True
    floor_mask = (floor_color & floor_region_mask).astype(np.uint8) * 255

    # Wall: gray tones (low saturation), side regions
    wall_color = (
        (hsv[:, :, 1] < 40) &  # low saturation (gray)
        (gray > 140) & (gray < 210)
    )
    wall_mask = wall_color.astype(np.uint8) * 255

    # Background = ceiling | floor | wall
    background = cv2.bitwise_or(ceiling_mask, floor_mask)
    background = cv2.bitwise_or(background, wall_mask)

    # Obstacle = everything that's not background and not very bright (to exclude ceiling bleed)
    obstacle_mask = cv2.bitwise_not(background)
    # Exclude very bright pixels (ceiling artifacts)
    obstacle_mask[gray > 220] = 0
    # Exclude very dark pixels (perspective lines)
    obstacle_mask[gray < 30] = 0

    # Clean up noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    obstacle_mask = cv2.morphologyEx(obstacle_mask, cv2.MORPH_OPEN, kernel)
    obstacle_mask = cv2.morphologyEx(obstacle_mask, cv2.MORPH_CLOSE, kernel)

    # --- Zone decomposition (3x3 grid) ---
    col_splits = [0, w // 3, 2 * w // 3, w]
    row_splits = [0, int(h * 0.45), int(h * 0.7), h]  # far / mid / near
    zone_names_row = ["far", "mid", "near"]
    zone_names_col = ["left", "center", "right"]

    zones: dict[str, float] = {}
    for ri in range(3):
        for ci in range(3):
            zone = obstacle_mask[row_splits[ri]:row_splits[ri + 1],
                                 col_splits[ci]:col_splits[ci + 1]]
            total_px = zone.size
            obstacle_px = int(np.count_nonzero(zone))
            frac = round(obstacle_px / total_px, 3) if total_px > 0 else 0.0
            zones[f"{zone_names_col[ci]}_{zone_names_row[ri]}"] = frac

    # --- Determine clear path ---
    col_density = {}
    for col_name in zone_names_col:
        col_density[col_name] = sum(
            zones[f"{col_name}_{row}"] for row in zone_names_row
        ) / 3.0

    # Near + mid rows matter most for immediate navigation
    near_mid_density = {}
    for col_name in zone_names_col:
        near_mid_density[col_name] = (
            zones[f"{col_name}_near"] * 0.6 + zones[f"{col_name}_mid"] * 0.4
        )

    min_col = min(near_mid_density, key=near_mid_density.get)
    clear_path = min_col.upper() if near_mid_density[min_col] < 0.15 else "NONE"

    # If center is clear, prefer FORWARD
    if near_mid_density["center"] < 0.05:
        clear_path = "CENTER"

    # --- Closest obstacle zone ---
    near_zones = {k: v for k, v in zones.items() if k.endswith("_near")}
    closest = max(near_zones, key=near_zones.get) if near_zones else "none"

    # --- Contour count ---
    contours, _ = cv2.findContours(obstacle_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    significant = [c for c in contours if cv2.contourArea(c) > 200]

    return {
        "obstacle_zones": zones,
        "clear_path": clear_path,
        "closest_obstacle_zone": closest if near_zones[closest] > 0.02 else "none",
        "obstacles_detected": len(significant),
        "center_blocked": near_mid_density["center"] > 0.10,
    }
