"""Additive insertion, route guidance and squad rally for the Garden mission.

The caller supplies its MAP entity and qualified-material brush writers.  This
module adds no visible or solid geometry and does not load or replace the base
Garden source.  Every entity is supported by the existing Plastic Platoon game.
"""
from __future__ import annotations


START_VOLUME = ((3800, -824, 8), (4120, -576, 144))
DROPSHIP_ORIGIN = (3712, -960, 36)
DROPSHIP_PATH = ((3712, -960, 230), (3424, -1120, 230))
RALLY_VOLUME = ((3008, 4600, 8), (3240, 5000, 144))

# Each volume lies inside a turn of the original serpentine garden.  These are
# one-shot reminders rather than gates: fighting, sneaking and backtracking all
# remain possible, and objective updates never alter the original enclosure.
STAGES = (
    ("first_turn", (3920, 576, 8), (4520, 624, 144),
     "Keep low. Follow the garden west and use the earth banks to break sight lines."),
    ("west_pass", (2008, 1200, 8), (2600, 1256, 144),
     "Turn north through the narrow garden pass. Watch the covered positions."),
    ("long_garden", (2008, 1936, 8), (2600, 1992, 144),
     "Head east through the next garden. Stay behind cover and search the field supplies."),
    ("east_pass", (3928, 2576, 8), (4520, 2632, 144),
     "The route continues north. Check the tight pass before crossing into the upper garden."),
    ("upper_garden", (3928, 3216, 8), (4520, 3272, 144),
     "Work west through the upper garden. Bunkers and towers guard the last approach."),
    ("last_pass", (2008, 3848, 8), (2600, 3904, 144),
     "Last narrow pass. Move north toward the sandbox perimeter."),
    ("perimeter", (2008, 4496, 8), (2600, 4552, 144),
     "Sandbox perimeter ahead. Clear a path east and assemble outside the closed boundary."),
)


def add_mission(ent, box):
    """Append supported mission entities through ``ent``; return audit metadata.

    ``ent(classname, origin=None, geometry=(), **values)`` writes entities, and
    ``box(lo, hi, qualified_texture)`` returns one MAP brush.  Messages contain
    MAP's literal ``\\n`` escape where a center-print needs a line break.
    """
    support_origin = (3856, -960, 48)

    def point(classname, **values):
        ent(classname, support_origin, **values)

    def volume(classname, lo, hi, **values):
        ent(classname, geometry=[box(lo, hi, "sandkeep/trim")], **values)

    volume("trigger_once", *START_VOLUME, target="garden_mission_start",
           _garden_logic="insertion-start")
    point("target_help", targetname="garden_mission_start", spawnflags=1,
          message="Helicopter drop-off complete. Sneak through the gardens and reach the sandbox perimeter. Do not enter the sandbox.")
    point("trigger_relay", targetname="garden_mission_start",
          message="OPERATION GARDEN GHOST\\nMove quietly through the gardens.\\nReach the sandbox. Hold outside.")
    point("trigger_relay", targetname="garden_mission_start",
          target="garden_insertion_ship", delay=5)

    ent("misc_platoon_dropship", DROPSHIP_ORIGIN,
        targetname="garden_insertion_ship", target="garden_insertion_lift",
        speed=200, angle=90, _garden_logic="friendly-insertion")
    ent("path_corner", DROPSHIP_PATH[0], targetname="garden_insertion_lift",
        target="garden_insertion_depart")
    ent("path_corner", DROPSHIP_PATH[1], targetname="garden_insertion_depart",
        pathtarget="garden_insertion_gone")
    point("trigger_relay", targetname="garden_insertion_gone",
          killtarget="garden_insertion_ship")

    for name, lo, hi, message in STAGES:
        target = "garden_guidance_" + name
        volume("trigger_once", lo, hi, target=target,
               _garden_logic="route-" + name)
        point("target_help", targetname=target, spawnflags=1, message=message)

    # This native trigger checks every living, connected player and fires once.
    # Completion deliberately leaves the squad here: the next mission's sandbox
    # interior is neither loaded nor unlocked by any target in this graph.
    volume("trigger_platoon_extract", *RALLY_VOLUME,
           target="garden_perimeter_goal", _garden_logic="all-living-rally")
    point("target_goal", targetname="garden_perimeter_goal",
          target="garden_perimeter_complete")
    point("target_help", targetname="garden_perimeter_complete", spawnflags=1,
          message="Sandbox reached. Hold outside the closed perimeter. The sandbox interior is the next operation.")
    point("trigger_relay", targetname="garden_perimeter_complete",
          message="GARDEN GHOST COMPLETE\\nSandbox reached. Hold outside.\\nEntry is the next operation.")

    return {
        "start_target": "garden_mission_start",
        "dropship_target": "garden_insertion_ship",
        "dropship_origin": DROPSHIP_ORIGIN,
        "dropship_path": DROPSHIP_PATH,
        "departure_delay_seconds": 5,
        "guidance": [
            {"name": name, "bounds": [lo, hi], "message": message}
            for name, lo, hi, message in STAGES
        ],
        "rally_volume": RALLY_VOLUME,
        "completion_target": "garden_perimeter_goal",
        "completion_class": "trigger_platoon_extract",
        "completion_requires_all_living_players": True,
        "changes_level": False,
    }
