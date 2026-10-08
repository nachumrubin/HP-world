"""Checks the greybox layout against the design's flight-pacing goals.

    python3 Tools/layout_report.py

Prints flight times between zones at cruise speed, and fails (exit 1) if a major destination
(layout "pacing_zones") is outside the 30-60 s goal from the castle, or any zone is outside the flyable boundary.
"""

import json
import math
import os
import sys


def main():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "greybox_layout.json")
    with open(path, encoding="utf-8") as handle:
        layout = json.load(handle)

    cruise = layout["cruise_speed_mps"]
    boundary = layout["soft_boundary_m"]
    goal_min, goal_max = layout["flight_time_goal_s"]
    zones = [z for z in layout["zones"] if "anchor" in z]
    castle = next(z for z in zones if z["name"] == "Hogwarts Castle")

    names = [z["name"] for z in zones]
    width = max(len(n) for n in names)
    print(f"Flight time in seconds at cruise ({cruise} m/s):\n")
    print(" " * (width + 2) + "".join(f"{n[:10]:>12}" for n in names))
    for a in zones:
        row = []
        for b in zones:
            distance = math.dist(a["anchor"], b["anchor"])
            row.append(f"{distance / cruise:>12.0f}" if a is not b else f"{'-':>12}")
        print(f"{a['name']:<{width + 2}}" + "".join(row))

    failures = []
    for zone in zones:
        radius = math.hypot(*zone["anchor"])
        if radius > boundary:
            failures.append(f"{zone['name']} is outside the flyable boundary ({radius:.0f} m > {boundary} m)")
        if zone["name"] not in layout["pacing_zones"]:
            continue
        seconds = math.dist(castle["anchor"], zone["anchor"]) / cruise
        if not goal_min <= seconds <= goal_max:
            failures.append(f"Castle -> {zone['name']} is {seconds:.0f} s (goal {goal_min}-{goal_max} s)")

    print()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"OK: every major destination is {goal_min}-{goal_max} s from the castle and inside the {boundary} m boundary.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
