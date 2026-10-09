"""Apply the four-block Tyrant revision to the preserved approved-art source."""

import copy


TYRANT_SCALE = (1.0, 64.0 / 53.599998, 1.0)


def upgrade_tyrant(geometry, animation_data):
    bones = geometry["bones"]
    for bone in bones:
        bone["pivot"] = [v * s for v, s in zip(bone["pivot"], TYRANT_SCALE)]
        for cube in bone.get("cubes", []):
            for field in ("origin", "size", "pivot"):
                if field in cube:
                    cube[field] = [v * s for v, s in zip(cube[field], TYRANT_SCALE)]
    lookup = {bone["name"]: bone for bone in bones}
    skin = lookup["part_head"]["cubes"][0]["uv"]
    light = lookup["part_belt_buckle"]["cubes"][0]["uv"]
    dark = lookup["part_mouth_line"]["cubes"][0]["uv"]
    for source, name, parent in (
        ("part_coat_chest", "mutant_chest", "chest"),
        ("part_upper_sleeve_-1", "mutant_upper_r", "upper_arm_r"),
        ("part_upper_sleeve_1", "mutant_upper_l", "upper_arm_l"),
        ("part_fore_sleeve_-1", "mutant_forearm_r", "forearm_r"),
        ("part_fore_sleeve_1", "mutant_forearm_l", "forearm_l"),
    ):
        part = copy.deepcopy(lookup[source])
        part.update(name=name, parent=parent)
        for index, cube in enumerate(part["cubes"]):
            cube.update(name=f"{name}_{index}", uv=copy.deepcopy(skin))
        bones.append(part)

    def cube(name, origin, size, uv):
        return {"name": name, "origin": origin, "size": size, "uv": copy.deepcopy(uv)}

    bones.append({"name": "mutant_shoulder", "parent": "chest", "pivot": [-12.8, 52, -5], "cubes": [
        cube("shoulder_outer", [-16.5, 46, -8], [11, 9, 8], skin),
        cube("shoulder_upper", [-14.5, 45, -7], [10, 11, 8], skin),
        cube("shoulder_root", [-12.5, 43, -6], [8, 9, 8], skin),
    ]})
    # The eye protrudes from connected shoulder tissue; its gameplay center stays fixed.
    bones.append({"name": "tyrant_eye", "parent": "chest", "pivot": [-12.8, 52, -8.8], "cubes": [
        cube("tyrant_eye_sclera", [-16.8, 49, -11.2], [8, 6, 4.8], skin),
        cube("tyrant_eye_sclera_top", [-15.8, 55, -11.2], [6, 1, 4.8], skin),
        cube("tyrant_eye_sclera_bottom", [-15.8, 48, -11.2], [6, 1, 4.8], skin),
        cube("tyrant_eye_iris", [-15.2, 49.5, -11.24], [4.8, 5, 0.04], light),
        cube("tyrant_eye_pupil", [-13.8, 50, -11.28], [2, 4, 0.04], dark),
    ]})
    for side, sign in (("r", -1), ("l", 1)):
        anchor = lookup["hand_" + side]["pivot"]
        x, y, z = anchor
        blades = [cube("blade_" + side + "_ridge", [x - 2, y - 10, z - 3], [4, 20, 5], skin)]
        for index in range(4):
            width = 4.5 - index
            blades.append(cube(f"blade_{side}_edge_{index}",
                               [x + sign * 3 - width / 2, y - 4 - index * 4, z - 7 - index * 1.5],
                               [width, 6, 5], skin))
        bones.append({"name": "blade_" + side, "parent": "hand_" + side, "pivot": anchor[:], "cubes": blades})
    geometry["description"]["visible_bounds_height"] = 7
    geometry["description"]["visible_bounds_offset"] = [0, 2, 0]

    animations = animation_data["animations"]

    def keys(*values):
        return {str(time): vector for time, vector in values}

    def rotation(*values):
        return {"rotation": keys(*values)}

    def mirrored(clip):
        result = copy.deepcopy(clip)
        result["bones"] = {}
        for name, channels in clip["bones"].items():
            mirror = name[:-2] + ("_l" if name.endswith("_r") else "_r") if name.endswith(("_l", "_r")) else name
            result["bones"][mirror] = copy.deepcopy(channels)
            for channel, track in result["bones"][mirror].items():
                for time, value in track.items():
                    track[time] = [value[0], -value[1], -value[2]] if channel == "rotation" else [-value[0], value[1], value[2]] if channel == "position" else value
        return result

    animations["animation.tyrant.punch_left"] = mirrored(animations["animation.tyrant.punch"])
    animations["animation.tyrant.shove"]["bones"] = {
        "upper_arm_r": rotation((0, [0, 0, 0]), (.3, [-25, -55, 15]), (.5, [-60, 35, -10]), (.8, [-30, 55, -10]), (1.2, [0, 0, 0])),
        "forearm_r": rotation((0, [0, 0, 0]), (.3, [-45, -15, 0]), (.5, [-15, 15, 0]), (1.2, [0, 0, 0])),
        "torso": rotation((0, [0, 0, 0]), (.3, [0, 15, 0]), (.5, [0, -15, 0]), (1.2, [0, 0, 0])),
    }
    animations["animation.tyrant.shove_left"] = mirrored(animations["animation.tyrant.shove"])
    animations["animation.tyrant.slash"] = {"loop": False, "animation_length": 1.2, "bones": {
        "upper_arm_r": rotation((0, [0, 0, 0]), (.3, [40, 40, 10]), (.5, [-55, -35, 0]), (.75, [-35, -60, 0]), (1.2, [0, 0, 0])),
        "forearm_r": rotation((0, [0, 0, 0]), (.3, [0, 0, 0]), (.5, [20, 0, 0]), (.75, [10, 0, 0]), (1.2, [0, 0, 0])),
        "upper_arm_l": rotation((0, [0, 0, 0]), (.3, [-15, 10, -15]), (.5, [20, -10, -20]), (1.2, [0, 0, 0])),
    }}
    animations["animation.tyrant.slash_left"] = mirrored(animations["animation.tyrant.slash"])
    animations["animation.tyrant.throw"] = {"loop": False, "animation_length": 1.8, "bones": {
        "upper_arm_r": rotation((0, [0, 0, 0]), (.35, [-35, 0, 0]), (.8, [150, -10, 20]), (1.0, [-75, 0, -5]), (1.8, [0, 0, 0])),
        "forearm_r": rotation((0, [0, 0, 0]), (.8, [-60, 0, 0]), (1.0, [-5, 0, 0]), (1.8, [0, 0, 0])),
        "torso": rotation((0, [0, 0, 0]), (.8, [-12, 20, 0]), (1.0, [12, -15, 0]), (1.8, [0, 0, 0])),
    }}
    walk = animations["animation.tyrant.walk"]
    walk["animation_length"] = .9
    for channels in walk["bones"].values():
        for channel, track in channels.items():
            channels[channel] = {str(round(float(time) * .9 / 1.4, 6)): value for time, value in track.items()}
    # World displacement belongs to the server, not to a sliding render root.
    animations["animation.tyrant.charge"]["bones"]["root"]["position"] = keys((0, [0, 0, 0]), (1, [0, 0, 0]), (2, [0, 0, 0]))
