#!/usr/bin/env python3
"""Generate, render, and validate the original re_demo creature assets."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "src/main/resources/assets/re_demo"
GEO_DIR = ASSET_ROOT / "geo"
ANIMATION_DIR = ASSET_ROOT / "animations"
TEXTURE_DIR = ASSET_ROOT / "textures/entity"
ART_DIR = ROOT / "art"
EVIDENCE_DIR = ROOT / "docs/evidence"
TEXTURE_SIZE = 256
TILE_SIZE = 32


def stable_uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "re-demo-creature-assets/" + name))


def round_values(value: Any) -> Any:
    if isinstance(value, float):
        rounded = round(value, 4)
        return int(rounded) if rounded.is_integer() else rounded
    if isinstance(value, list):
        return [round_values(item) for item in value]
    if isinstance(value, dict):
        return {key: round_values(item) for key, item in value.items()}
    return value


@dataclass
class Cube:
    name: str
    origin: list[float]
    size: list[float]
    material: str
    rotation: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    pivot: list[float] | None = None
    inflate: float = 0.0
    mirror: bool = False


@dataclass
class Bone:
    name: str
    parent: str | None
    pivot: list[float]
    rotation: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    cubes: list[Cube] = field(default_factory=list)


@dataclass
class Model:
    creature_id: str
    display_name: str
    hitbox: tuple[float, float, float]
    visible_bounds: tuple[float, float, tuple[float, float, float]]
    materials: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], str]]
    accent: tuple[int, int, int]
    bones: dict[str, Bone]
    animations: dict[str, dict[str, Any]] = field(default_factory=dict)
    signature_attack: str = ""
    hit_time: float = 0.0
    hidden_bones: set[str] = field(default_factory=set)

    @property
    def cube_count(self) -> int:
        return sum(len(bone.cubes) for bone in self.bones.values())


def make_bones(specs: list[tuple[str, str | None, list[float], list[float] | None]]) -> dict[str, Bone]:
    bones: dict[str, Bone] = {}
    for name, parent, pivot, rotation in specs:
        bones[name] = Bone(name, parent, pivot, rotation or [0.0, 0.0, 0.0])
    return bones


def add_cube(
    bones: dict[str, Bone],
    bone_name: str,
    name: str,
    origin: list[float],
    size: list[float],
    material: str,
    rotation: list[float] | None = None,
    pivot: list[float] | None = None,
    inflate: float = 0.0,
    mirror: bool = False,
) -> None:
    bones[bone_name].cubes.append(
        Cube(
            name=name,
            origin=origin,
            size=size,
            material=material,
            rotation=rotation or [0.0, 0.0, 0.0],
            pivot=pivot,
            inflate=inflate,
            mirror=mirror,
        )
    )


LICKER_MATERIALS = {
    "flesh": ((142, 37, 48), (219, 79, 83), "muscle"),
    "dark_flesh": ((75, 22, 31), (145, 43, 54), "muscle"),
    "sinew": ((188, 88, 80), (245, 152, 126), "sinew"),
    "brain": ((205, 104, 126), (255, 179, 190), "brain"),
    "brain_dark": ((119, 51, 75), (197, 88, 115), "brain"),
    "bone": ((199, 180, 151), (246, 226, 190), "bone"),
    "claw": ((62, 56, 51), (168, 151, 126), "claw"),
    "tongue": ((161, 42, 82), (248, 102, 142), "tongue"),
    "mouth": ((42, 12, 20), (105, 27, 39), "mouth"),
    "vein": ((86, 45, 80), (144, 70, 127), "vein"),
}

TYRANT_MATERIALS = {
    "coat": ((51, 69, 73), (88, 111, 111), "cloth"),
    "coat_dark": ((28, 39, 42), (58, 76, 78), "cloth"),
    "coat_edge": ((87, 99, 92), (135, 143, 126), "cloth"),
    "leather": ((58, 46, 38), (113, 85, 60), "leather"),
    "skin": ((137, 126, 111), (199, 181, 156), "skin"),
    "scar": ((83, 59, 56), (157, 105, 94), "scar"),
    "muscle": ((107, 35, 41), (186, 70, 66), "muscle"),
    "metal": ((107, 117, 115), (198, 207, 198), "metal"),
    "boot": ((28, 28, 27), (71, 68, 61), "leather"),
    "hat": ((37, 45, 45), (75, 87, 84), "cloth"),
}

G1_MATERIALS = {
    "cloth": ((70, 71, 73), (121, 119, 113), "cloth"),
    "cloth_torn": ((45, 45, 45), (94, 87, 80), "cloth"),
    "skin": ((151, 123, 105), (217, 182, 149), "skin"),
    "mut_flesh": ((124, 39, 45), (213, 75, 72), "muscle"),
    "mut_dark": ((65, 20, 28), (129, 39, 51), "muscle"),
    "sinew": ((181, 84, 72), (239, 136, 105), "sinew"),
    "eye_white": ((205, 193, 166), (249, 239, 207), "eye"),
    "iris": ((173, 88, 43), (253, 167, 66), "iris"),
    "pupil": ((27, 14, 18), (67, 29, 28), "pupil"),
    "eye_lid": ((106, 35, 43), (184, 66, 68), "scar"),
    "scar": ((94, 49, 49), (181, 99, 82), "scar"),
    "bone": ((184, 163, 132), (237, 217, 175), "bone"),
    "trousers": ((40, 49, 54), (78, 88, 91), "cloth"),
    "boot": ((35, 31, 28), (82, 69, 55), "leather"),
}


def build_licker() -> Model:
    bones = make_bones(
        [
            ("root", None, [0, 0, 0], None),
            ("pelvis", "root", [0, 8, 5], None),
            ("spine", "pelvis", [0, 10, 3], [-8, 0, 0]),
            ("chest", "spine", [0, 11, 0], [-5, 0, 0]),
            ("neck", "chest", [0, 12, -4], [12, 0, 0]),
            ("head", "neck", [0, 12, -8], [8, 0, 0]),
            ("jaw", "head", [0, 9, -11], None),
            ("brain", "head", [0, 15, -8], None),
            ("tongue_base", "jaw", [0, 9, -13], None),
            ("tongue_mid", "tongue_base", [0, 8.5, -18], None),
            ("tongue_tip", "tongue_mid", [0, 8.2, -23], None),
            ("shoulder_l", "chest", [7, 12, -2], None),
            ("upper_arm_l", "shoulder_l", [8, 10, -3], [0, 0, -18]),
            ("forearm_l", "upper_arm_l", [9, 6, -6], [20, 0, -8]),
            ("claw_l", "forearm_l", [10, 2.5, -9], None),
            ("shoulder_r", "chest", [-7, 12, -2], None),
            ("upper_arm_r", "shoulder_r", [-8, 10, -3], [0, 0, 18]),
            ("forearm_r", "upper_arm_r", [-9, 6, -6], [20, 0, 8]),
            ("claw_r", "forearm_r", [-10, 2.5, -9], None),
            ("thigh_l", "pelvis", [5, 8, 6], [22, 0, -8]),
            ("shin_l", "thigh_l", [6, 4, 8], [-16, 0, 5]),
            ("foot_l", "shin_l", [6, 1.5, 5], None),
            ("thigh_r", "pelvis", [-5, 8, 6], [22, 0, 8]),
            ("shin_r", "thigh_r", [-6, 4, 8], [-16, 0, -5]),
            ("foot_r", "shin_r", [-6, 1.5, 5], None),
        ]
    )
    add_cube(bones, "pelvis", "pelvis_core", [-5, 6, 2], [10, 6, 8], "dark_flesh")
    add_cube(bones, "pelvis", "pelvis_muscle", [-4, 10, 1], [8, 3, 7], "flesh")
    add_cube(bones, "spine", "spine_column", [-2, 9, -2], [4, 4, 10], "sinew")
    for index, z in enumerate([5, 3, 1, -1, -3]):
        add_cube(bones, "spine", f"spine_ridge_{index}", [-1.5, 13, z], [3, 2, 2], "bone", [8, 0, 0])
    add_cube(bones, "chest", "rib_core", [-6, 8, -5], [12, 7, 9], "flesh")
    for side in (-1, 1):
        label = "l" if side > 0 else "r"
        add_cube(bones, "chest", f"rib_{label}_upper", [side * 2 - (0 if side > 0 else 4), 12, -5], [4, 2, 8], "bone", [0, 0, side * 8])
        add_cube(bones, "chest", f"rib_{label}_lower", [side * 3 - (0 if side > 0 else 5), 9, -4], [3, 2, 7], "sinew", [0, 0, side * 12])
    add_cube(bones, "neck", "neck_tendon", [-3, 10, -8], [6, 4, 6], "sinew")
    add_cube(bones, "head", "skull_base", [-5, 9, -13], [10, 6, 7], "dark_flesh")
    add_cube(bones, "head", "faceless_mask", [-4, 10, -14], [8, 3, 2], "flesh")
    add_cube(bones, "jaw", "jaw_upper", [-4, 8, -15], [8, 2, 5], "mouth")
    add_cube(bones, "jaw", "jaw_lower", [-4, 6.5, -14], [8, 2, 4], "bone", [-12, 0, 0], [0, 9, -12])
    add_cube(bones, "brain", "brain_left", [0, 14, -12], [5, 4, 7], "brain", [0, 0, -4])
    add_cube(bones, "brain", "brain_right", [-5, 14, -12], [5, 4, 7], "brain_dark", [0, 0, 4])
    add_cube(bones, "brain", "brain_crown", [-3, 17, -10], [6, 2, 5], "brain")
    add_cube(bones, "tongue_base", "tongue_root", [-1.5, 7.5, -19], [3, 2, 8], "tongue")
    add_cube(bones, "tongue_mid", "tongue_length", [-1, 7.2, -25], [2, 1.5, 7], "tongue")
    add_cube(bones, "tongue_tip", "tongue_hook", [-1.5, 6.8, -28], [3, 2, 4], "tongue", [-15, 0, 0])
    for side in (-1, 1):
        suffix = "l" if side > 0 else "r"
        shoulder_x = 5 if side > 0 else -9
        upper_x = 6 if side > 0 else -10
        fore_x = 7 if side > 0 else -11
        claw_x = 7.5 if side > 0 else -11.5
        add_cube(bones, f"shoulder_{suffix}", f"shoulder_mass_{suffix}", [shoulder_x, 9, -5], [4, 5, 6], "flesh")
        add_cube(bones, f"upper_arm_{suffix}", f"upper_arm_{suffix}", [upper_x, 6, -6], [4, 6, 4], "dark_flesh")
        add_cube(bones, f"forearm_{suffix}", f"forearm_{suffix}", [fore_x, 2.5, -9], [4, 6, 5], "flesh")
        add_cube(bones, f"claw_{suffix}", f"palm_{suffix}", [claw_x, 1, -12], [4, 3, 5], "dark_flesh")
        for claw_index in range(3):
            base_x = (8 + claw_index * 1.2) if side > 0 else (-9.2 - claw_index * 1.2)
            add_cube(
                bones,
                f"claw_{suffix}",
                f"talon_{suffix}_{claw_index}",
                [base_x, -0.4, -15 - claw_index * 0.5],
                [1.1, 2, 5],
                "claw",
                [-28 + claw_index * 7, 0, side * (8 - claw_index * 4)],
                [side * 10, 1.5, -12],
            )
        thigh_x = 3 if side > 0 else -7
        shin_x = 4 if side > 0 else -8
        foot_x = 3.5 if side > 0 else -7.5
        add_cube(bones, f"thigh_{suffix}", f"rear_thigh_{suffix}", [thigh_x, 5, 4], [4, 6, 6], "dark_flesh")
        add_cube(bones, f"shin_{suffix}", f"rear_shin_{suffix}", [shin_x, 1, 6], [4, 6, 4], "sinew")
        add_cube(bones, f"foot_{suffix}", f"rear_foot_{suffix}", [foot_x, 0, 1], [4, 2, 8], "flesh")
        for toe_index in range(2):
            toe_x = (4 + toe_index * 1.8) if side > 0 else (-5.8 - toe_index * 1.8)
            add_cube(bones, f"foot_{suffix}", f"toe_{suffix}_{toe_index}", [toe_x, -0.2, -2], [1.2, 1.5, 4], "claw", [-10, 0, side * 4])
    return Model(
        "licker",
        "LICKER",
        (1.35, 1.05, 1.35),
        (2.2, 1.35, (0, 0.62, -0.3)),
        LICKER_MATERIALS,
        (218, 72, 84),
        bones,
        signature_attack="tongue",
        hit_time=0.55,
    )


def build_tyrant() -> Model:
    bones = make_bones(
        [
            ("root", None, [0, 0, 0], None),
            ("pelvis", "root", [0, 27, 0], None),
            ("torso", "pelvis", [0, 34, 0], None),
            ("chest", "torso", [0, 39, 0], None),
            ("neck", "chest", [0, 42, 0], None),
            ("head", "neck", [0, 44, 0], None),
            ("hat", "head", [0, 47, 0], None),
            ("coat_intact", "torso", [0, 33, 0], None),
            ("coat_torn", "torso", [0, 36, 0], None),
            ("shoulder_l", "chest", [8, 39, 0], None),
            ("upper_arm_l", "shoulder_l", [8, 34, 0], [0, 0, -4]),
            ("forearm_l", "upper_arm_l", [8, 26, 0], None),
            ("hand_l", "forearm_l", [8, 20, -1], None),
            ("shoulder_r", "chest", [-8, 39, 0], None),
            ("upper_arm_r", "shoulder_r", [-8, 34, 0], [0, 0, 4]),
            ("forearm_r", "upper_arm_r", [-8, 26, 0], None),
            ("hand_r", "forearm_r", [-8, 20, -1], None),
            ("thigh_l", "pelvis", [4.5, 27, 0], None),
            ("shin_l", "thigh_l", [4.5, 14, 0], None),
            ("foot_l", "shin_l", [4.5, 3, -1], None),
            ("thigh_r", "pelvis", [-4.5, 27, 0], None),
            ("shin_r", "thigh_r", [-4.5, 14, 0], None),
            ("foot_r", "shin_r", [-4.5, 3, -1], None),
        ]
    )
    add_cube(bones, "pelvis", "hip_frame", [-6, 25, -4], [12, 7, 8], "coat_dark")
    add_cube(bones, "pelvis", "belt", [-6.5, 29, -4.5], [13, 2, 9], "leather")
    add_cube(bones, "pelvis", "belt_buckle", [-1.5, 29.2, -5], [3, 2, 1], "metal")
    add_cube(bones, "torso", "torso_core", [-7, 31, -4], [14, 11, 8], "coat")
    add_cube(bones, "chest", "broad_chest", [-9, 36, -4.5], [18, 7, 9], "coat")
    add_cube(bones, "neck", "neck_block", [-2.5, 40.5, -2.5], [5, 4, 5], "skin")
    add_cube(bones, "head", "head_block", [-3.5, 42, -3.5], [7, 6, 7], "skin")
    add_cube(bones, "head", "brow_shadow", [-3.7, 44, -4], [7.4, 2, 1], "scar")
    add_cube(bones, "head", "jaw_block", [-3, 41.5, -4], [6, 2.5, 6], "skin")
    add_cube(bones, "hat", "hat_crown", [-4.2, 46.5, -3.8], [8.4, 3, 7.6], "hat")
    add_cube(bones, "hat", "hat_brim", [-7.5, 46, -6], [15, 1, 12], "hat")
    add_cube(bones, "coat_intact", "coat_upper", [-7.5, 30, -5], [15, 11, 10], "coat")
    add_cube(bones, "coat_intact", "coat_lower_back", [-7, 15, 1], [14, 16, 4], "coat_dark")
    add_cube(bones, "coat_intact", "coat_tail_l", [0.5, 14, -4], [6.5, 17, 6], "coat", [0, 0, -2], [0, 30, 0])
    add_cube(bones, "coat_intact", "coat_tail_r", [-7, 14, -4], [6.5, 17, 6], "coat", [0, 0, 2], [0, 30, 0])
    add_cube(bones, "coat_intact", "lapel_l", [1, 34, -5.5], [5, 7, 1], "coat_edge", [0, 0, -12], [0, 39, -5])
    add_cube(bones, "coat_intact", "lapel_r", [-6, 34, -5.5], [5, 7, 1], "coat_edge", [0, 0, 12], [0, 39, -5])
    add_cube(bones, "coat_intact", "collar_l", [2, 39.5, -4.8], [5, 3, 2], "coat_edge", [0, 0, -18], [0, 40, 0])
    add_cube(bones, "coat_intact", "collar_r", [-7, 39.5, -4.8], [5, 3, 2], "coat_edge", [0, 0, 18], [0, 40, 0])
    for index, y in enumerate([36, 32, 28]):
        add_cube(bones, "coat_intact", f"coat_button_{index}", [-0.7, y, -5.7], [1.4, 1.4, 0.8], "metal")
    add_cube(bones, "coat_torn", "exposed_chest", [-7, 32, -4.5], [14, 10, 6], "muscle")
    add_cube(bones, "coat_torn", "torn_panel_l", [0, 18, -4], [7, 16, 4], "coat", [0, 0, -8], [0, 32, 0])
    add_cube(bones, "coat_torn", "torn_panel_r", [-7, 20, -4], [6, 14, 4], "coat_dark", [0, 0, 10], [0, 32, 0])
    add_cube(bones, "coat_torn", "exposed_rib_l", [1, 36, -5], [5, 2, 2], "scar", [0, 0, -8])
    add_cube(bones, "coat_torn", "exposed_rib_r", [-6, 33, -5], [5, 2, 2], "muscle", [0, 0, 12])
    add_cube(bones, "coat_torn", "torn_collar", [-5, 39, -5], [10, 2, 2], "coat_edge", [0, 0, 5])
    for side in (-1, 1):
        suffix = "l" if side > 0 else "r"
        shoulder_x = 5 if side > 0 else -10
        arm_x = 5.5 if side > 0 else -9.5
        add_cube(bones, f"shoulder_{suffix}", f"shoulder_{suffix}", [shoulder_x, 35.5, -4], [5, 7, 8], "coat")
        add_cube(bones, f"upper_arm_{suffix}", f"upper_arm_{suffix}", [arm_x, 28, -3.5], [4, 9, 7], "coat_dark")
        add_cube(bones, f"forearm_{suffix}", f"forearm_{suffix}", [arm_x, 20, -3.5], [4, 9, 7], "coat")
        add_cube(bones, f"hand_{suffix}", f"glove_{suffix}", [arm_x - 0.5, 17, -4], [5, 5, 8], "leather")
        add_cube(bones, f"hand_{suffix}", f"knuckles_{suffix}", [arm_x - 0.7, 16, -5], [5.4, 2, 3], "skin")
        thigh_x = 0.5 if side > 0 else -5.5
        shin_x = 1 if side > 0 else -5
        foot_x = 0.5 if side > 0 else -5.5
        add_cube(bones, f"thigh_{suffix}", f"thigh_{suffix}", [thigh_x, 15, -3.5], [5, 13, 7], "coat_dark")
        add_cube(bones, f"shin_{suffix}", f"shin_{suffix}", [shin_x, 3.5, -3], [4, 13, 6], "coat")
        add_cube(bones, f"foot_{suffix}", f"boot_{suffix}", [foot_x, 0, -6], [5, 5, 10], "boot")
        add_cube(bones, f"foot_{suffix}", f"boot_cap_{suffix}", [foot_x - 0.3, 0, -7], [5.6, 3, 3], "metal")
    return Model(
        "tyrant",
        "TYRANT",
        (1.2, 2.95, 1.2),
        (1.8, 3.2, (0, 1.48, 0)),
        TYRANT_MATERIALS,
        (102, 173, 163),
        bones,
        signature_attack="punch",
        hit_time=0.8,
        hidden_bones={"coat_torn"},
    )


def build_g1() -> Model:
    bones = make_bones(
        [
            ("root", None, [0, 0, 0], None),
            ("pelvis", "root", [0, 25, 0], None),
            ("torso", "pelvis", [0, 34, 0], [0, 0, 4]),
            ("chest", "torso", [0, 38, 0], None),
            ("neck", "chest", [1, 41, 0], None),
            ("head", "neck", [1, 44, 0], [0, 0, 5]),
            ("right_shoulder", "chest", [-12, 34.4, 0], [0, 0, 12]),
            ("right_upper_arm", "right_shoulder", [-11, 29, 0], [0, 0, 20]),
            ("right_forearm", "right_upper_arm", [-9, 18, -1], [0, 0, -8]),
            ("right_hand", "right_forearm", [-9, 8, -2], None),
            ("eye_open", "right_shoulder", [-12, 34.4, 0], None),
            ("eye_closed", "right_shoulder", [-12, 34.4, 0], None),
            ("left_shoulder", "chest", [7, 38, 0], None),
            ("left_upper_arm", "left_shoulder", [7, 32, 0], [0, 0, -6]),
            ("left_forearm", "left_upper_arm", [7, 24, 0], None),
            ("left_hand", "left_forearm", [7, 18, -1], None),
            ("thigh_l", "pelvis", [4, 25, 0], None),
            ("shin_l", "thigh_l", [4, 13, 0], None),
            ("foot_l", "shin_l", [4, 3, -1], None),
            ("thigh_r", "pelvis", [-4, 25, 0], [0, 0, 4]),
            ("shin_r", "thigh_r", [-4, 13, 0], [0, 0, -3]),
            ("foot_r", "shin_r", [-4, 3, -1], None),
        ]
    )
    add_cube(bones, "pelvis", "pelvis", [-6, 22, -4], [12, 7, 8], "trousers")
    add_cube(bones, "pelvis", "torn_belt", [-6.5, 26, -4.5], [13, 2, 9], "cloth_torn")
    add_cube(bones, "torso", "human_torso", [-6, 29, -4], [12, 13, 8], "cloth")
    add_cube(bones, "torso", "mutated_flank", [-9, 29, -3.5], [5, 12, 7], "mut_flesh", [0, 0, 8], [-4, 36, 0])
    add_cube(bones, "chest", "chest_mass", [-8, 34, -4.5], [16, 8, 9], "skin")
    add_cube(bones, "chest", "chest_tear", [-8.5, 35, -5], [7, 6, 2], "mut_dark", [0, 0, 8])
    add_cube(bones, "neck", "neck", [-1.5, 39.5, -2.5], [5, 5, 5], "skin")
    add_cube(bones, "head", "head", [-2.5, 41, -3.5], [7, 6, 7], "skin")
    add_cube(bones, "head", "hair", [-3, 46, -3], [7, 2, 6], "cloth_torn")
    add_cube(bones, "head", "jaw", [-2.2, 40.5, -4], [6.5, 2.5, 6], "scar")
    add_cube(bones, "right_shoulder", "shoulder_tumor", [-15, 29, -6], [12, 13, 12], "mut_flesh", [0, 0, 8], [-12, 34.4, 0])
    add_cube(bones, "right_shoulder", "shoulder_sinew", [-13, 31, -7], [8, 9, 4], "sinew", [0, 0, 10], [-12, 34.4, 0])
    add_cube(bones, "right_shoulder", "shoulder_bone", [-12, 38, -3], [5, 6, 6], "bone", [0, 0, 22], [-12, 34.4, 0])
    add_cube(bones, "right_upper_arm", "giant_upper_arm", [-15, 18, -6], [11, 15, 12], "mut_dark")
    add_cube(bones, "right_upper_arm", "giant_bicep", [-17, 22, -5], [8, 10, 10], "mut_flesh", [0, 0, 10], [-11, 29, 0])
    add_cube(bones, "right_upper_arm", "arm_tendon", [-10, 17, -7], [5, 14, 4], "sinew", [0, 0, -6], [-11, 29, 0])
    add_cube(bones, "right_forearm", "giant_forearm", [-14, 7, -7], [10, 14, 13], "mut_flesh")
    add_cube(bones, "right_forearm", "forearm_plate", [-15, 10, -8], [7, 10, 4], "mut_dark", [0, 0, -5], [-9, 18, -1])
    add_cube(bones, "right_hand", "giant_palm", [-14, 2, -8], [10, 9, 14], "mut_dark")
    for finger_index in range(4):
        add_cube(
            bones,
            "right_hand",
            f"giant_finger_{finger_index}",
            [-13 + finger_index * 2.2, -2, -11 - (finger_index % 2)],
            [1.8, 7, 7],
            "bone" if finger_index in (0, 3) else "mut_flesh",
            [-18 + finger_index * 5, 0, -6 + finger_index * 4],
            [-9, 7, -2],
        )
    add_cube(bones, "eye_open", "eyeball", [-15, 31.5, -7], [7, 7, 7], "eye_white")
    add_cube(bones, "eye_open", "iris", [-13.5, 33, -8], [4, 4, 2], "iris")
    add_cube(bones, "eye_open", "pupil", [-12.5, 34, -8.7], [2, 2, 1], "pupil")
    add_cube(bones, "eye_open", "eye_glint", [-12, 35, -9], [1, 1, 0.6], "eye_white")
    add_cube(bones, "eye_closed", "closed_lid", [-15, 33, -7.5], [7, 3, 2], "eye_lid", [0, 0, 4], [-12, 34.4, 0])
    add_cube(bones, "eye_closed", "closed_lid_scar", [-14, 34, -8], [5, 1, 1], "scar", [0, 0, -6], [-12, 34.4, 0])
    add_cube(bones, "left_shoulder", "left_shoulder", [4.5, 34, -3.5], [5, 8, 7], "cloth")
    add_cube(bones, "left_upper_arm", "left_upper_arm", [5, 27, -3], [4, 9, 6], "skin")
    add_cube(bones, "left_forearm", "left_forearm", [5, 19, -3], [4, 9, 6], "cloth_torn")
    add_cube(bones, "left_hand", "left_hand", [4.5, 15, -4], [5, 5, 8], "skin")
    for side in (-1, 1):
        suffix = "l" if side > 0 else "r"
        thigh_x = 1 if side > 0 else -6
        shin_x = 1.5 if side > 0 else -5.5
        foot_x = 1 if side > 0 else -6
        add_cube(bones, f"thigh_{suffix}", f"thigh_{suffix}", [thigh_x, 13, -3.5], [5, 13, 7], "trousers")
        add_cube(bones, f"shin_{suffix}", f"shin_{suffix}", [shin_x, 3, -3], [4, 12, 6], "cloth_torn")
        add_cube(bones, f"foot_{suffix}", f"boot_{suffix}", [foot_x, 0, -6], [5, 5, 10], "boot")
        add_cube(bones, f"foot_{suffix}", f"boot_torn_{suffix}", [foot_x - 0.3, 3, -3.5], [5.6, 3, 7], "mut_flesh" if side < 0 else "cloth")
    return Model(
        "g1_birkin",
        "G1 BIRKIN",
        (1.5, 2.9, 1.5),
        (2.4, 3.15, (-0.18, 1.45, 0)),
        G1_MATERIALS,
        (229, 137, 55),
        bones,
        signature_attack="slam",
        hit_time=0.9,
        hidden_bones={"eye_closed"},
    )


def keyframes(*entries: tuple[float, list[float]]) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for time_value, vector in entries:
        key = f"{time_value:.3f}".rstrip("0").rstrip(".")
        result[key] = vector
    return result


def animation(length: float, loop: bool, bones: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "loop": loop,
        "animation_length": length,
        "bones": bones,
    }


def attach_licker_animations(model: Model) -> None:
    prefix = "animation.licker."
    model.animations = {
        prefix + "idle": animation(
            2.0,
            True,
            {
                "chest": {"rotation": keyframes((0, [-5, 0, 0]), (1, [-1, 0, 0]), (2, [-5, 0, 0]))},
                "brain": {"position": keyframes((0, [0, 0, 0]), (1, [0, 0.45, 0]), (2, [0, 0, 0]))},
                "tongue_tip": {"rotation": keyframes((0, [0, -8, 0]), (1, [0, 10, 0]), (2, [0, -8, 0]))},
            },
        ),
        prefix + "walk": animation(
            1.0,
            True,
            {
                "upper_arm_l": {"rotation": keyframes((0, [24, 0, -18]), (0.5, [-28, 0, -18]), (1, [24, 0, -18]))},
                "upper_arm_r": {"rotation": keyframes((0, [-28, 0, 18]), (0.5, [24, 0, 18]), (1, [-28, 0, 18]))},
                "thigh_l": {"rotation": keyframes((0, [-22, 0, -8]), (0.5, [28, 0, -8]), (1, [-22, 0, -8]))},
                "thigh_r": {"rotation": keyframes((0, [28, 0, 8]), (0.5, [-22, 0, 8]), (1, [28, 0, 8]))},
                "root": {"position": keyframes((0, [0, 0, 0]), (0.25, [0, 0.8, 0]), (0.5, [0, 0, 0]), (0.75, [0, 0.8, 0]), (1, [0, 0, 0]))},
            },
        ),
        prefix + "hurt": animation(
            0.6,
            False,
            {
                "root": {"position": keyframes((0, [0, 0, 0]), (0.18, [0, 0, 2]), (0.6, [0, 0, 0]))},
                "chest": {"rotation": keyframes((0, [0, 0, 0]), (0.18, [-24, 0, 13]), (0.6, [0, 0, 0]))},
                "head": {"rotation": keyframes((0, [0, 0, 0]), (0.18, [18, -12, 0]), (0.6, [0, 0, 0]))},
            },
        ),
        prefix + "death": animation(
            2.4,
            False,
            {
                "root": {
                    "position": keyframes((0, [0, 0, 0]), (0.8, [0, -1, 1]), (2.4, [0, -5, 3])),
                    "rotation": keyframes((0, [0, 0, 0]), (1.2, [14, 0, 42]), (2.4, [7, 0, 88])),
                },
                "jaw": {"rotation": keyframes((0, [0, 0, 0]), (0.7, [35, 0, 0]), (2.4, [18, 0, 0]))},
                "claw_l": {"rotation": keyframes((0, [0, 0, 0]), (1.1, [0, 0, -42]), (2.4, [0, 0, -18]))},
                "claw_r": {"rotation": keyframes((0, [0, 0, 0]), (1.1, [0, 0, 42]), (2.4, [0, 0, 18]))},
            },
        ),
        prefix + "claw": animation(
            1.0,
            False,
            {
                "chest": {"rotation": keyframes((0, [0, 0, 0]), (0.25, [8, -10, 0]), (0.45, [-12, 14, 0]), (1, [0, 0, 0]))},
                "upper_arm_l": {"rotation": keyframes((0, [0, 0, 0]), (0.25, [-65, -10, 12]), (0.45, [55, 15, -24]), (1, [0, 0, 0]))},
                "forearm_l": {"rotation": keyframes((0, [0, 0, 0]), (0.25, [-35, 0, 0]), (0.45, [48, 0, -12]), (1, [0, 0, 0]))},
                "claw_l": {"rotation": keyframes((0, [0, 0, 0]), (0.25, [0, 0, 26]), (0.45, [0, 0, -36]), (1, [0, 0, 0]))},
            },
        ),
        prefix + "leap": animation(
            1.4,
            False,
            {
                "root": {
                    "position": keyframes((0, [0, 0, 0]), (0.45, [0, -2, 1]), (0.6, [0, 5, -4]), (0.95, [0, 8, -12]), (1.4, [0, 0, -17])),
                    "rotation": keyframes((0, [0, 0, 0]), (0.6, [-18, 0, 0]), (1.0, [12, 0, 0]), (1.4, [0, 0, 0])),
                },
                "thigh_l": {"rotation": keyframes((0, [0, 0, 0]), (0.45, [48, 0, 0]), (0.7, [-38, 0, 0]), (1.4, [0, 0, 0]))},
                "thigh_r": {"rotation": keyframes((0, [0, 0, 0]), (0.45, [48, 0, 0]), (0.7, [-38, 0, 0]), (1.4, [0, 0, 0]))},
                "upper_arm_l": {"rotation": keyframes((0, [0, 0, 0]), (0.6, [-50, 0, -20]), (1.0, [35, 0, 0]), (1.4, [0, 0, 0]))},
                "upper_arm_r": {"rotation": keyframes((0, [0, 0, 0]), (0.6, [-50, 0, 20]), (1.0, [35, 0, 0]), (1.4, [0, 0, 0]))},
            },
        ),
        prefix + "tongue": animation(
            1.2,
            False,
            {
                "jaw": {"rotation": keyframes((0, [0, 0, 0]), (0.25, [28, 0, 0]), (0.85, [30, 0, 0]), (1.2, [0, 0, 0]))},
                "tongue_base": {
                    "position": keyframes((0, [0, 0, 0]), (0.3, [0, 0, -2]), (0.55, [0, 0, -8]), (0.85, [0, 0, -6]), (1.2, [0, 0, 0])),
                    "scale": keyframes((0, [1, 1, 0.65]), (0.55, [1, 1, 1.7]), (1.2, [1, 1, 0.65])),
                },
                "tongue_mid": {"rotation": keyframes((0, [0, 0, 0]), (0.55, [-4, 7, 0]), (0.85, [7, -10, 0]), (1.2, [0, 0, 0]))},
                "tongue_tip": {"rotation": keyframes((0, [0, 0, 0]), (0.55, [-16, -8, 0]), (0.85, [22, 12, 0]), (1.2, [0, 0, 0]))},
            },
        ),
        prefix + "ambush": animation(
            1.4,
            False,
            {
                "root": {
                    "position": keyframes((0, [0, 12, 2]), (0.35, [0, 11, 2]), (0.8, [0, 2, -5]), (1.4, [0, 0, -8])),
                    "rotation": keyframes((0, [160, 0, 0]), (0.35, [175, 0, 0]), (0.8, [35, 0, 0]), (1.4, [0, 0, 0])),
                },
                "claw_l": {"rotation": keyframes((0, [0, 0, -40]), (0.8, [30, 0, 15]), (1.4, [0, 0, 0]))},
                "claw_r": {"rotation": keyframes((0, [0, 0, 40]), (0.8, [30, 0, -15]), (1.4, [0, 0, 0]))},
            },
        ),
    }


def attach_tyrant_animations(model: Model) -> None:
    prefix = "animation.tyrant."
    model.animations = {
        prefix + "idle": animation(
            2.5,
            True,
            {
                "chest": {"rotation": keyframes((0, [0, 0, 0]), (1.25, [-2, 0, 0]), (2.5, [0, 0, 0]))},
                "head": {"rotation": keyframes((0, [0, -3, 0]), (1.25, [0, 3, 0]), (2.5, [0, -3, 0]))},
                "coat_intact": {"position": keyframes((0, [0, 0, 0]), (1.25, [0, 0.25, 0]), (2.5, [0, 0, 0]))},
            },
        ),
        prefix + "walk": animation(
            1.4,
            True,
            {
                "thigh_l": {"rotation": keyframes((0, [24, 0, 0]), (0.7, [-24, 0, 0]), (1.4, [24, 0, 0]))},
                "thigh_r": {"rotation": keyframes((0, [-24, 0, 0]), (0.7, [24, 0, 0]), (1.4, [-24, 0, 0]))},
                "upper_arm_l": {"rotation": keyframes((0, [-14, 0, 0]), (0.7, [14, 0, 0]), (1.4, [-14, 0, 0]))},
                "upper_arm_r": {"rotation": keyframes((0, [14, 0, 0]), (0.7, [-14, 0, 0]), (1.4, [14, 0, 0]))},
                "root": {"position": keyframes((0, [0, 0, 0]), (0.35, [0, 0.35, 0]), (0.7, [0, 0, 0]), (1.05, [0, 0.35, 0]), (1.4, [0, 0, 0]))},
            },
        ),
        prefix + "hurt": animation(
            0.7,
            False,
            {
                "torso": {"rotation": keyframes((0, [0, 0, 0]), (0.2, [-8, 0, -8]), (0.7, [0, 0, 0]))},
                "head": {"rotation": keyframes((0, [0, 0, 0]), (0.2, [8, 10, 0]), (0.7, [0, 0, 0]))},
                "root": {"position": keyframes((0, [0, 0, 0]), (0.2, [0, 0, 1]), (0.7, [0, 0, 0]))},
            },
        ),
        prefix + "death": animation(
            3.0,
            False,
            {
                "root": {
                    "position": keyframes((0, [0, 0, 0]), (1.4, [0, -3, 0]), (3, [0, -20, 4])),
                    "rotation": keyframes((0, [0, 0, 0]), (1.4, [8, 0, -16]), (3, [78, 0, -12])),
                },
                "head": {"rotation": keyframes((0, [0, 0, 0]), (1.2, [18, -10, 0]), (3, [28, -10, 0]))},
                "upper_arm_l": {"rotation": keyframes((0, [0, 0, 0]), (2.0, [20, 0, -35]), (3, [32, 0, -55]))},
                "upper_arm_r": {"rotation": keyframes((0, [0, 0, 0]), (2.0, [20, 0, 35]), (3, [32, 0, 55]))},
            },
        ),
        prefix + "punch": animation(
            1.6,
            False,
            {
                "torso": {"rotation": keyframes((0, [0, 0, 0]), (0.5, [0, 20, 0]), (0.8, [0, -22, 0]), (1.6, [0, 0, 0]))},
                "upper_arm_r": {"rotation": keyframes((0, [0, 0, 0]), (0.5, [-72, 0, 24]), (0.8, [66, 0, -8]), (1.2, [26, 0, 8]), (1.6, [0, 0, 0]))},
                "forearm_r": {"rotation": keyframes((0, [0, 0, 0]), (0.5, [-58, 0, 0]), (0.8, [42, 0, 0]), (1.6, [0, 0, 0]))},
                "hand_r": {"rotation": keyframes((0, [0, 0, 0]), (0.8, [0, -12, 0]), (1.6, [0, 0, 0]))},
                "root": {"position": keyframes((0, [0, 0, 0]), (0.5, [0, 0, 0]), (0.8, [0, 0, -3]), (1.6, [0, 0, 0]))},
            },
        ),
        prefix + "shove": animation(
            1.2,
            False,
            {
                "upper_arm_l": {"rotation": keyframes((0, [0, 0, 0]), (0.3, [-36, -25, -12]), (0.5, [48, 18, 10]), (1.2, [0, 0, 0]))},
                "upper_arm_r": {"rotation": keyframes((0, [0, 0, 0]), (0.3, [-36, 25, 12]), (0.5, [48, -18, -10]), (1.2, [0, 0, 0]))},
                "torso": {"rotation": keyframes((0, [0, 0, 0]), (0.3, [-8, 0, 0]), (0.5, [14, 0, 0]), (1.2, [0, 0, 0]))},
            },
        ),
        prefix + "charge": animation(
            2.0,
            False,
            {
                "root": {"position": keyframes((0, [0, 0, 0]), (0.8, [0, 0, 1]), (1, [0, 0, -2]), (1.55, [0, 0, -15]), (2, [0, 0, -20]))},
                "torso": {"rotation": keyframes((0, [0, 0, 0]), (1, [-18, 0, 0]), (1.55, [-28, 0, 0]), (2, [0, 0, 0]))},
                "thigh_l": {"rotation": keyframes((1, [35, 0, 0]), (1.28, [-35, 0, 0]), (1.55, [35, 0, 0]), (2, [0, 0, 0]))},
                "thigh_r": {"rotation": keyframes((1, [-35, 0, 0]), (1.28, [35, 0, 0]), (1.55, [-35, 0, 0]), (2, [0, 0, 0]))},
            },
        ),
        prefix + "break": animation(
            1.4,
            False,
            {
                "upper_arm_r": {"rotation": keyframes((0, [0, 0, 0]), (0.45, [-115, 0, 12]), (0.7, [62, 0, 0]), (1.4, [0, 0, 0]))},
                "forearm_r": {"rotation": keyframes((0, [0, 0, 0]), (0.45, [-70, 0, 0]), (0.7, [55, 0, 0]), (1.4, [0, 0, 0]))},
                "torso": {"rotation": keyframes((0, [0, 0, 0]), (0.45, [-8, 0, 0]), (0.7, [22, 0, 0]), (1.4, [0, 0, 0]))},
            },
        ),
        prefix + "rage": animation(
            2.0,
            False,
            {
                "root": {"position": keyframes((0, [0, 0, 0]), (0.3, [0.3, 0, 0]), (0.6, [-0.3, 0, 0]), (0.9, [0.3, 0, 0]), (1.2, [-0.3, 0, 0]), (2, [0, 0, 0]))},
                "head": {"rotation": keyframes((0, [0, 0, 0]), (0.8, [-18, 0, 0]), (1.2, [14, 0, 0]), (2, [0, 0, 0]))},
                "upper_arm_l": {"rotation": keyframes((0, [0, 0, 0]), (0.7, [-25, 0, -28]), (1.4, [12, 0, -45]), (2, [0, 0, 0]))},
                "upper_arm_r": {"rotation": keyframes((0, [0, 0, 0]), (0.7, [-25, 0, 28]), (1.4, [12, 0, 45]), (2, [0, 0, 0]))},
            },
        ),
    }


def attach_g1_animations(model: Model) -> None:
    prefix = "animation.g1_birkin."
    model.animations = {
        prefix + "idle": animation(
            2.2,
            True,
            {
                "torso": {"rotation": keyframes((0, [0, 0, 4]), (1.1, [-3, 0, 6]), (2.2, [0, 0, 4]))},
                "right_shoulder": {"rotation": keyframes((0, [0, 0, 12]), (1.1, [0, 0, 16]), (2.2, [0, 0, 12]))},
                "eye_open": {"scale": keyframes((0, [1, 1, 1]), (1.05, [1.04, 1.04, 1.04]), (2.2, [1, 1, 1]))},
            },
        ),
        prefix + "walk": animation(
            1.3,
            True,
            {
                "thigh_l": {"rotation": keyframes((0, [23, 0, 0]), (0.65, [-23, 0, 0]), (1.3, [23, 0, 0]))},
                "thigh_r": {"rotation": keyframes((0, [-18, 0, 0]), (0.65, [18, 0, 0]), (1.3, [-18, 0, 0]))},
                "left_upper_arm": {"rotation": keyframes((0, [-18, 0, 0]), (0.65, [18, 0, 0]), (1.3, [-18, 0, 0]))},
                "right_upper_arm": {"rotation": keyframes((0, [7, 0, 20]), (0.65, [-8, 0, 16]), (1.3, [7, 0, 20]))},
                "root": {"position": keyframes((0, [0, 0, 0]), (0.325, [0, 0.4, 0]), (0.65, [0, 0, 0]), (0.975, [0, 0.4, 0]), (1.3, [0, 0, 0]))},
            },
        ),
        prefix + "hurt": animation(
            0.65,
            False,
            {
                "torso": {"rotation": keyframes((0, [0, 0, 0]), (0.18, [-10, 6, -11]), (0.65, [0, 0, 0]))},
                "right_shoulder": {"rotation": keyframes((0, [0, 0, 0]), (0.18, [0, 0, -12]), (0.65, [0, 0, 0]))},
                "head": {"rotation": keyframes((0, [0, 0, 0]), (0.18, [12, -8, 0]), (0.65, [0, 0, 0]))},
            },
        ),
        prefix + "death": animation(
            3.2,
            False,
            {
                "root": {
                    "position": keyframes((0, [0, 0, 0]), (1.4, [0, -2, 0]), (3.2, [0, -18, 4])),
                    "rotation": keyframes((0, [0, 0, 0]), (1.4, [12, 0, 18]), (3.2, [82, 0, 24])),
                },
                "right_shoulder": {"rotation": keyframes((0, [0, 0, 0]), (1.2, [0, 0, -28]), (3.2, [0, 0, -52]))},
                "right_forearm": {"rotation": keyframes((0, [0, 0, 0]), (1.4, [0, 0, 38]), (3.2, [0, 0, 56]))},
                "head": {"rotation": keyframes((0, [0, 0, 0]), (1.1, [22, 10, 0]), (3.2, [35, 14, 0]))},
            },
        ),
        prefix + "slam": animation(
            1.8,
            False,
            {
                "right_shoulder": {"rotation": keyframes((0, [0, 0, 0]), (0.55, [-15, 0, -72]), (0.9, [24, 0, 42]), (1.8, [0, 0, 0]))},
                "right_upper_arm": {"rotation": keyframes((0, [0, 0, 0]), (0.55, [-40, 0, -36]), (0.9, [58, 0, 15]), (1.8, [0, 0, 0]))},
                "right_forearm": {"rotation": keyframes((0, [0, 0, 0]), (0.55, [-55, 0, 0]), (0.9, [62, 0, 0]), (1.8, [0, 0, 0]))},
                "torso": {"rotation": keyframes((0, [0, 0, 0]), (0.55, [-18, 0, -8]), (0.9, [34, 0, 14]), (1.8, [0, 0, 0]))},
                "root": {"position": keyframes((0, [0, 0, 0]), (0.55, [0, 1, 1]), (0.9, [0, -2, -2]), (1.8, [0, 0, 0]))},
            },
        ),
        prefix + "sweep": animation(
            2.0,
            False,
            {
                "root": {"rotation": keyframes((0, [0, -12, 0]), (0.65, [0, 32, 0]), (1, [0, -58, 0]), (1.45, [0, -80, 0]), (2, [0, 0, 0]))},
                "right_shoulder": {"rotation": keyframes((0, [0, 0, 0]), (0.65, [0, 0, -32]), (1, [0, 0, 54]), (2, [0, 0, 0]))},
                "right_upper_arm": {"rotation": keyframes((0, [0, 0, 0]), (0.65, [0, -30, -22]), (1, [0, 65, 24]), (2, [0, 0, 0]))},
                "right_forearm": {"rotation": keyframes((0, [0, 0, 0]), (1, [0, 35, 18]), (2, [0, 0, 0]))},
            },
        ),
        prefix + "grab": animation(
            2.0,
            False,
            {
                "right_shoulder": {"rotation": keyframes((0, [0, 0, 0]), (0.45, [-20, -18, -35]), (0.75, [42, 22, 18]), (1.3, [-18, 0, -12]), (2, [0, 0, 0]))},
                "right_forearm": {"rotation": keyframes((0, [0, 0, 0]), (0.45, [-45, 0, 0]), (0.75, [58, 0, 0]), (1.3, [-32, 0, 0]), (2, [0, 0, 0]))},
                "right_hand": {"scale": keyframes((0, [1, 1, 1]), (0.75, [1.1, 1.1, 1.1]), (1.3, [0.88, 0.88, 0.88]), (2, [1, 1, 1]))},
                "torso": {"rotation": keyframes((0, [0, 0, 0]), (0.75, [0, -18, 0]), (1.3, [0, 22, 0]), (2, [0, 0, 0]))},
            },
        ),
        prefix + "rage": animation(
            2.0,
            False,
            {
                "torso": {"rotation": keyframes((0, [0, 0, 0]), (0.6, [-18, 0, 0]), (1.1, [16, 0, 0]), (2, [0, 0, 0]))},
                "right_shoulder": {"rotation": keyframes((0, [0, 0, 0]), (0.6, [0, 0, -28]), (1.1, [0, 0, 32]), (2, [0, 0, 0]))},
                "eye_open": {"scale": keyframes((0, [0.65, 0.65, 0.65]), (0.75, [1.22, 1.22, 1.22]), (1.4, [1.08, 1.08, 1.08]), (2, [1, 1, 1]))},
                "head": {"rotation": keyframes((0, [0, 0, 0]), (0.75, [-22, 10, 0]), (1.4, [18, -10, 0]), (2, [0, 0, 0]))},
            },
        ),
    }


def attach_animations(models: dict[str, Model]) -> None:
    attach_licker_animations(models["licker"])
    attach_tyrant_animations(models["tyrant"])
    attach_g1_animations(models["g1_birkin"])


def get_models() -> dict[str, Model]:
    models = {
        "licker": build_licker(),
        "tyrant": build_tyrant(),
        "g1_birkin": build_g1(),
    }
    attach_animations(models)
    return models


def ensure_directories() -> None:
    for path in (GEO_DIR, ANIMATION_DIR, TEXTURE_DIR, ART_DIR, EVIDENCE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def material_uv(model: Model, material: str) -> tuple[int, int]:
    index = list(model.materials).index(material)
    return (index % 8) * TILE_SIZE + 2, (index // 8) * TILE_SIZE + 2


def deterministic_noise(name: str, x: int, y: int) -> int:
    digest = hashlib.sha256(f"{name}:{x}:{y}".encode("utf-8")).digest()
    return digest[0]


def blend(color_a: tuple[int, int, int], color_b: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(int(a + (b - a) * factor) for a, b in zip(color_a, color_b))


def paint_material_tile(
    draw: ImageDraw.ImageDraw,
    material_name: str,
    tile_x: int,
    tile_y: int,
    base: tuple[int, int, int],
    accent: tuple[int, int, int],
    pattern: str,
) -> None:
    x0, y0 = tile_x, tile_y
    draw.rectangle((x0, y0, x0 + 31, y0 + 31), fill=blend(base, (12, 14, 17), 0.25))
    draw.rectangle((x0 + 2, y0 + 2, x0 + 29, y0 + 29), fill=base)
    for py in range(y0 + 3, y0 + 29):
        for px in range(x0 + 3, x0 + 29):
            noise = deterministic_noise(material_name, px, py)
            if noise > 238:
                draw.point((px, py), fill=blend(base, accent, 0.28))
            elif noise < 10:
                draw.point((px, py), fill=blend(base, (0, 0, 0), 0.22))
    if pattern == "muscle":
        for offset in range(-24, 40, 7):
            draw.line((x0 + offset, y0 + 28, x0 + offset + 24, y0 + 4), fill=accent, width=2)
            draw.line((x0 + offset + 2, y0 + 28, x0 + offset + 26, y0 + 4), fill=blend(base, (20, 10, 13), 0.35), width=1)
    elif pattern == "brain":
        for row in range(3):
            points = []
            for step in range(7):
                points.append((x0 + 4 + step * 4, y0 + 7 + row * 8 + (2 if step % 2 else 0)))
            draw.line(points, fill=accent, width=3)
            draw.line([(px, py + 2) for px, py in points], fill=blend(base, (35, 12, 25), 0.45), width=1)
    elif pattern == "sinew":
        for offset in range(4, 29, 4):
            draw.line((x0 + offset, y0 + 3, x0 + max(3, offset - 8), y0 + 29), fill=blend(base, accent, 0.6), width=1)
    elif pattern == "cloth":
        for offset in range(4, 30, 6):
            draw.line((x0 + offset, y0 + 2, x0 + offset, y0 + 29), fill=blend(base, accent, 0.2), width=1)
            draw.line((x0 + 2, y0 + offset, x0 + 29, y0 + offset), fill=blend(base, (0, 0, 0), 0.16), width=1)
        draw.line((x0 + 4, y0 + 5, x0 + 27, y0 + 5), fill=accent, width=1)
    elif pattern == "leather":
        for offset in range(5, 28, 7):
            draw.arc((x0 + offset - 4, y0 + offset - 5, x0 + offset + 8, y0 + offset + 5), 180, 355, fill=accent, width=1)
    elif pattern == "metal":
        draw.rectangle((x0 + 4, y0 + 4, x0 + 27, y0 + 27), outline=accent, width=2)
        draw.line((x0 + 6, y0 + 25, x0 + 25, y0 + 6), fill=blend(accent, (255, 255, 255), 0.5), width=2)
        for px, py in ((6, 6), (25, 6), (6, 25), (25, 25)):
            draw.ellipse((x0 + px - 1, y0 + py - 1, x0 + px + 1, y0 + py + 1), fill=(43, 47, 47))
    elif pattern == "eye":
        draw.ellipse((x0 + 3, y0 + 5, x0 + 28, y0 + 26), fill=accent, outline=blend(base, (50, 22, 24), 0.4), width=2)
        draw.arc((x0 + 5, y0 + 7, x0 + 26, y0 + 24), 205, 330, fill=(255, 255, 255), width=2)
    elif pattern == "iris":
        center = (x0 + 16, y0 + 16)
        for radius in range(13, 2, -2):
            factor = radius / 13
            color = blend(accent, base, factor * 0.6)
            draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline=color, width=2)
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            draw.line((center[0], center[1], center[0] + math.cos(rad) * 13, center[1] + math.sin(rad) * 13), fill=accent, width=1)
    elif pattern == "pupil":
        draw.ellipse((x0 + 5, y0 + 3, x0 + 26, y0 + 28), fill=base, outline=accent, width=2)
        draw.ellipse((x0 + 12, y0 + 4, x0 + 19, y0 + 27), fill=(4, 4, 5))
    elif pattern == "bone":
        draw.line((x0 + 5, y0 + 25, x0 + 26, y0 + 6), fill=accent, width=4)
        draw.line((x0 + 7, y0 + 27, x0 + 28, y0 + 8), fill=blend(base, (76, 59, 44), 0.25), width=1)
    elif pattern == "scar":
        draw.line((x0 + 4, y0 + 25, x0 + 27, y0 + 6), fill=accent, width=3)
        for index in range(6):
            px = x0 + 7 + index * 3
            py = y0 + 23 - index * 3
            draw.line((px - 3, py - 2, px + 3, py + 2), fill=blend(base, (235, 187, 149), 0.5), width=1)
    elif pattern == "tongue":
        draw.line((x0 + 16, y0 + 3, x0 + 16, y0 + 29), fill=accent, width=3)
        for offset in range(6, 29, 5):
            draw.line((x0 + 5, y0 + offset, x0 + 27, y0 + offset - 2), fill=blend(base, accent, 0.45), width=1)
    elif pattern in ("vein", "mouth"):
        points = [(x0 + 3, y0 + 25), (x0 + 9, y0 + 17), (x0 + 14, y0 + 21), (x0 + 20, y0 + 10), (x0 + 28, y0 + 5)]
        draw.line(points, fill=accent, width=2)
    elif pattern == "claw":
        draw.polygon([(x0 + 5, y0 + 27), (x0 + 12, y0 + 5), (x0 + 27, y0 + 3), (x0 + 14, y0 + 11)], fill=accent)
        draw.line((x0 + 7, y0 + 25, x0 + 25, y0 + 5), fill=blend(accent, (255, 255, 255), 0.4), width=1)
    elif pattern == "skin":
        draw.line((x0 + 4, y0 + 24, x0 + 12, y0 + 21, x0 + 18, y0 + 24, x0 + 28, y0 + 18), fill=accent, width=1)
        draw.line((x0 + 7, y0 + 8, x0 + 17, y0 + 10, x0 + 24, y0 + 6), fill=blend(base, accent, 0.4), width=1)
    draw.rectangle((x0 + 1, y0 + 1, x0 + 30, y0 + 30), outline=blend(accent, (255, 255, 255), 0.22), width=1)


def generate_texture(model: Model) -> Path:
    image = Image.new("RGBA", (TEXTURE_SIZE, TEXTURE_SIZE), (17, 19, 22, 255))
    draw = ImageDraw.Draw(image)
    for index, (name, (base, accent, pattern)) in enumerate(model.materials.items()):
        tile_x = (index % 8) * TILE_SIZE
        tile_y = (index // 8) * TILE_SIZE
        paint_material_tile(draw, f"{model.creature_id}:{name}", tile_x, tile_y, base, accent, pattern)
    for grid in range(0, TEXTURE_SIZE, TILE_SIZE):
        draw.line((grid, 0, grid, TEXTURE_SIZE), fill=(31, 34, 38, 255), width=1)
        draw.line((0, grid, TEXTURE_SIZE, grid), fill=(31, 34, 38, 255), width=1)
    info = PngImagePlugin.PngInfo()
    info.add_text("Title", f"Original {model.display_name} pixel texture")
    info.add_text("Copyright", "Original work for re_demo; no extracted game assets")
    info.add_text("License", "Repository license")
    output = TEXTURE_DIR / f"{model.creature_id}.png"
    image.save(output, pnginfo=info, optimize=True)
    return output


def face_uv(model: Model, cube: Cube) -> dict[str, dict[str, list[float]]]:
    u, v = material_uv(model, cube.material)
    sx, sy, sz = cube.size
    return {
        "north": {"uv": [u, v], "uv_size": [sx, sy]},
        "south": {"uv": [u, v], "uv_size": [sx, sy]},
        "east": {"uv": [u, v], "uv_size": [sz, sy]},
        "west": {"uv": [u, v], "uv_size": [sz, sy]},
        "up": {"uv": [u, v], "uv_size": [sx, sz]},
        "down": {"uv": [u, v], "uv_size": [sx, sz]},
    }


def cube_to_geo(model: Model, cube: Cube) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": cube.name,
        "origin": cube.origin,
        "size": cube.size,
        "uv": face_uv(model, cube),
    }
    if any(cube.rotation):
        result["rotation"] = cube.rotation
        result["pivot"] = cube.pivot or [cube.origin[index] + cube.size[index] / 2 for index in range(3)]
    if cube.inflate:
        result["inflate"] = cube.inflate
    if cube.mirror:
        result["mirror"] = True
    return round_values(result)


def generate_geo(model: Model) -> Path:
    bones_json = []
    for bone in model.bones.values():
        entry: dict[str, Any] = {"name": bone.name, "pivot": bone.pivot}
        if bone.parent:
            entry["parent"] = bone.parent
        if any(bone.rotation):
            entry["rotation"] = bone.rotation
        if bone.cubes:
            entry["cubes"] = [cube_to_geo(model, cube) for cube in bone.cubes]
        bones_json.append(round_values(entry))
    bounds_width, bounds_height, bounds_offset = model.visible_bounds
    payload = {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": f"geometry.re_demo.{model.creature_id}",
                    "texture_width": TEXTURE_SIZE,
                    "texture_height": TEXTURE_SIZE,
                    "visible_bounds_width": bounds_width,
                    "visible_bounds_height": bounds_height,
                    "visible_bounds_offset": list(bounds_offset),
                },
                "bones": bones_json,
            }
        ],
    }
    output = GEO_DIR / f"{model.creature_id}.geo.json"
    output.write_text(json.dumps(round_values(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def generate_animation(model: Model) -> Path:
    payload = {
        "format_version": "1.8.0",
        "animations": round_values(model.animations),
    }
    output = ANIMATION_DIR / f"{model.creature_id}.animation.json"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def blockbench_faces(model: Model, cube: Cube) -> dict[str, dict[str, Any]]:
    faces: dict[str, dict[str, Any]] = {}
    for face_name, mapping in face_uv(model, cube).items():
        u, v = mapping["uv"]
        width, height = mapping["uv_size"]
        faces[face_name] = {"uv": [u, v, u + width, v + height], "texture": 0}
    return round_values(faces)


def build_blockbench_animation(model: Model, animation_name: str, data: dict[str, Any]) -> dict[str, Any]:
    animators: dict[str, Any] = {}
    for bone_name, tracks in data["bones"].items():
        keyframes_json = []
        for channel in ("rotation", "position", "scale"):
            for time_key, vector in tracks.get(channel, {}).items():
                keyframes_json.append(
                    {
                        "channel": channel,
                        "data_points": [{"x": vector[0], "y": vector[1], "z": vector[2]}],
                        "uuid": stable_uuid(f"{model.creature_id}:{animation_name}:{bone_name}:{channel}:{time_key}"),
                        "time": float(time_key),
                        "color": -1,
                        "interpolation": "linear",
                    }
                )
        animators[stable_uuid(f"{model.creature_id}:bone:{bone_name}")] = {
            "name": bone_name,
            "type": "bone",
            "keyframes": sorted(keyframes_json, key=lambda item: (item["time"], item["channel"])),
        }
    return {
        "uuid": stable_uuid(f"{model.creature_id}:animation:{animation_name}"),
        "name": animation_name,
        "loop": "loop" if data.get("loop") else "once",
        "override": False,
        "length": data["animation_length"],
        "snapping": 20,
        "selected": False,
        "anim_time_update": "",
        "blend_weight": "",
        "start_delay": "",
        "loop_delay": "",
        "animators": animators,
    }


def generate_bbmodel(model: Model, texture_path: Path) -> Path:
    element_ids: dict[tuple[str, str], str] = {}
    elements = []
    for bone_name, bone in model.bones.items():
        for cube in bone.cubes:
            cube_uuid = stable_uuid(f"{model.creature_id}:cube:{bone_name}:{cube.name}")
            element_ids[(bone_name, cube.name)] = cube_uuid
            origin = cube.pivot or [cube.origin[index] + cube.size[index] / 2 for index in range(3)]
            elements.append(
                {
                    "name": cube.name,
                    "box_uv": False,
                    "rescale": False,
                    "locked": False,
                    "light_emission": 0,
                    "render_order": "default",
                    "allow_mirror_modeling": True,
                    "from": cube.origin,
                    "to": [cube.origin[index] + cube.size[index] for index in range(3)],
                    "autouv": 0,
                    "color": list(model.materials).index(cube.material) % 8,
                    "origin": origin,
                    "rotation": cube.rotation,
                    "faces": blockbench_faces(model, cube),
                    "type": "cube",
                    "uuid": cube_uuid,
                }
            )

    children_map: dict[str | None, list[str]] = {}
    for bone in model.bones.values():
        children_map.setdefault(bone.parent, []).append(bone.name)

    def outliner_node(bone_name: str) -> dict[str, Any]:
        bone = model.bones[bone_name]
        children: list[Any] = [element_ids[(bone_name, cube.name)] for cube in bone.cubes]
        children.extend(outliner_node(child_name) for child_name in children_map.get(bone_name, []))
        return {
            "name": bone.name,
            "origin": bone.pivot,
            "rotation": bone.rotation,
            "bedrock_binding": "",
            "color": list(model.bones).index(bone.name) % 8,
            "uuid": stable_uuid(f"{model.creature_id}:bone:{bone.name}"),
            "export": True,
            "isOpen": True,
            "locked": False,
            "visibility": bone.name not in model.hidden_bones,
            "autouv": 0,
            "children": children,
        }

    texture_bytes = texture_path.read_bytes()
    texture_data = base64.b64encode(texture_bytes).decode("ascii")
    bbmodel = {
        "meta": {
            "format_version": "4.10",
            "model_format": "bedrock",
            "box_uv": False,
        },
        "name": model.creature_id,
        "model_identifier": f"geometry.re_demo.{model.creature_id}",
        "visible_box": [
            model.visible_bounds[0],
            model.visible_bounds[1],
            model.visible_bounds[2][1],
        ],
        "variable_placeholders": "",
        "variable_placeholder_buttons": [],
        "timeline_setups": [],
        "unhandled_root_fields": {},
        "resolution": {"width": TEXTURE_SIZE, "height": TEXTURE_SIZE},
        "elements": round_values(elements),
        "outliner": [outliner_node(name) for name in children_map.get(None, [])],
        "textures": [
            {
                "path": f"../src/main/resources/assets/re_demo/textures/entity/{model.creature_id}.png",
                "name": f"{model.creature_id}.png",
                "folder": "entity",
                "namespace": "re_demo",
                "id": "0",
                "particle": False,
                "render_mode": "default",
                "render_sides": "auto",
                "frame_time": 1,
                "frame_order_type": "loop",
                "frame_order": "",
                "frame_interpolate": False,
                "visible": True,
                "internal": True,
                "saved": True,
                "uuid": stable_uuid(f"{model.creature_id}:texture"),
                "source": "data:image/png;base64," + texture_data,
            }
        ],
        "animations": [
            build_blockbench_animation(model, name, data)
            for name, data in model.animations.items()
        ],
        "animation_variable_placeholders": "",
        "display": {},
        "backgrounds": {},
    }
    output = ART_DIR / f"{model.creature_id}.bbmodel"
    output.write_text(json.dumps(round_values(bbmodel), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_all() -> dict[str, Any]:
    ensure_directories()
    models = get_models()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "modid": "re_demo",
        "minecraft": "1.20.1",
        "geckolib": "4.4.9",
        "originality": "Original block-built assets; no extracted Capcom model or texture data.",
        "creatures": {},
    }
    for model in models.values():
        texture_path = generate_texture(model)
        geo_path = generate_geo(model)
        animation_path = generate_animation(model)
        bbmodel_path = generate_bbmodel(model, texture_path)
        manifest["creatures"][model.creature_id] = {
            "display_name": model.display_name,
            "hitbox_blocks": list(model.hitbox),
            "bones": len(model.bones),
            "cubes": model.cube_count,
            "texture_pixels": [TEXTURE_SIZE, TEXTURE_SIZE],
            "signature_attack": model.signature_attack,
            "hit_time_seconds": model.hit_time,
            "files": {
                str(path.relative_to(ROOT)): file_sha256(path)
                for path in (geo_path, animation_path, texture_path, bbmodel_path)
            },
        }
    output = ART_DIR / "creature_manifest.json"
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def load_resource_model(spec: Model) -> Model:
    geo_path = GEO_DIR / f"{spec.creature_id}.geo.json"
    animation_path = ANIMATION_DIR / f"{spec.creature_id}.animation.json"
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    animation_data = json.loads(animation_path.read_text(encoding="utf-8"))
    geometry = geo["minecraft:geometry"][0]
    material_names = list(spec.materials)
    bones: dict[str, Bone] = {}
    for bone_json in geometry["bones"]:
        bone = Bone(
            name=bone_json["name"],
            parent=bone_json.get("parent"),
            pivot=[float(value) for value in bone_json.get("pivot", [0, 0, 0])],
            rotation=[float(value) for value in bone_json.get("rotation", [0, 0, 0])],
        )
        for cube_json in bone_json.get("cubes", []):
            north_uv = cube_json["uv"]["north"]["uv"]
            tile_index = max(0, int((north_uv[1] - 2) // TILE_SIZE) * 8 + int((north_uv[0] - 2) // TILE_SIZE))
            material = material_names[min(tile_index, len(material_names) - 1)]
            bone.cubes.append(
                Cube(
                    name=cube_json.get("name", "cube"),
                    origin=[float(value) for value in cube_json["origin"]],
                    size=[float(value) for value in cube_json["size"]],
                    material=material,
                    rotation=[float(value) for value in cube_json.get("rotation", [0, 0, 0])],
                    pivot=[float(value) for value in cube_json.get("pivot", [])] or None,
                    inflate=float(cube_json.get("inflate", 0)),
                    mirror=bool(cube_json.get("mirror", False)),
                )
            )
        bones[bone.name] = bone
    return Model(
        creature_id=spec.creature_id,
        display_name=spec.display_name,
        hitbox=spec.hitbox,
        visible_bounds=spec.visible_bounds,
        materials=spec.materials,
        accent=spec.accent,
        bones=bones,
        animations=animation_data["animations"],
        signature_attack=spec.signature_attack,
        hit_time=spec.hit_time,
        hidden_bones=set(spec.hidden_bones),
    )


def translation_matrix(vector: list[float] | tuple[float, float, float]) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = np.array(vector, dtype=float)
    return matrix


def scale_matrix(vector: list[float]) -> np.ndarray:
    matrix = np.eye(4)
    matrix[0, 0], matrix[1, 1], matrix[2, 2] = vector
    return matrix


def rotation_matrix(rotation: list[float] | tuple[float, float, float]) -> np.ndarray:
    rx, ry, rz = [math.radians(value) for value in rotation]
    matrix_x = np.array(
        [[1, 0, 0, 0], [0, math.cos(rx), -math.sin(rx), 0], [0, math.sin(rx), math.cos(rx), 0], [0, 0, 0, 1]],
        dtype=float,
    )
    matrix_y = np.array(
        [[math.cos(ry), 0, math.sin(ry), 0], [0, 1, 0, 0], [-math.sin(ry), 0, math.cos(ry), 0], [0, 0, 0, 1]],
        dtype=float,
    )
    matrix_z = np.array(
        [[math.cos(rz), -math.sin(rz), 0, 0], [math.sin(rz), math.cos(rz), 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        dtype=float,
    )
    return matrix_z @ matrix_y @ matrix_x


def around_pivot_matrix(
    pivot: list[float],
    rotation: list[float],
    position: list[float] | None = None,
    scale: list[float] | None = None,
) -> np.ndarray:
    position = position or [0, 0, 0]
    scale = scale or [1, 1, 1]
    return (
        translation_matrix([pivot[index] + position[index] for index in range(3)])
        @ rotation_matrix(rotation)
        @ scale_matrix(scale)
        @ translation_matrix([-value for value in pivot])
    )


def sample_track(track: dict[str, list[float]] | list[float] | None, time_value: float, default: list[float]) -> list[float]:
    if track is None:
        return list(default)
    if isinstance(track, list):
        return [float(value) for value in track]
    points = sorted((float(key), [float(value) for value in vector]) for key, vector in track.items())
    if not points:
        return list(default)
    if time_value <= points[0][0]:
        return points[0][1]
    if time_value >= points[-1][0]:
        return points[-1][1]
    for (left_time, left), (right_time, right) in zip(points, points[1:]):
        if left_time <= time_value <= right_time:
            factor = (time_value - left_time) / max(0.0001, right_time - left_time)
            return [left[index] + (right[index] - left[index]) * factor for index in range(3)]
    return points[-1][1]


def animation_pose(model: Model, animation_name: str | None, time_value: float) -> dict[str, dict[str, list[float]]]:
    animation_data = model.animations.get(animation_name, {}) if animation_name else {}
    tracks = animation_data.get("bones", {})
    pose: dict[str, dict[str, list[float]]] = {}
    for bone_name, bone in model.bones.items():
        bone_tracks = tracks.get(bone_name, {})
        animated_rotation = sample_track(bone_tracks.get("rotation"), time_value, [0, 0, 0])
        pose[bone_name] = {
            "rotation": [bone.rotation[index] + animated_rotation[index] for index in range(3)],
            "position": sample_track(bone_tracks.get("position"), time_value, [0, 0, 0]),
            "scale": sample_track(bone_tracks.get("scale"), time_value, [1, 1, 1]),
        }
    return pose


def bone_is_hidden(model: Model, bone_name: str) -> bool:
    current: str | None = bone_name
    while current:
        if current in model.hidden_bones:
            return True
        current = model.bones[current].parent
    return False


def cube_vertices(model: Model, bone_name: str, cube: Cube, pose: dict[str, dict[str, list[float]]]) -> np.ndarray:
    inflate = cube.inflate
    x0, y0, z0 = [cube.origin[index] - inflate for index in range(3)]
    x1, y1, z1 = [cube.origin[index] + cube.size[index] + inflate for index in range(3)]
    vertices = np.array(
        [
            [x0, y0, z0, 1],
            [x1, y0, z0, 1],
            [x1, y1, z0, 1],
            [x0, y1, z0, 1],
            [x0, y0, z1, 1],
            [x1, y0, z1, 1],
            [x1, y1, z1, 1],
            [x0, y1, z1, 1],
        ],
        dtype=float,
    )
    if any(cube.rotation):
        cube_pivot = cube.pivot or [cube.origin[index] + cube.size[index] / 2 for index in range(3)]
        vertices = (around_pivot_matrix(cube_pivot, cube.rotation) @ vertices.T).T
    lineage: list[str] = []
    current: str | None = bone_name
    while current:
        lineage.append(current)
        current = model.bones[current].parent
    for current in lineage:
        state = pose[current]
        matrix = around_pivot_matrix(
            model.bones[current].pivot,
            state["rotation"],
            state["position"],
            state["scale"],
        )
        vertices = (matrix @ vertices.T).T
    return vertices[:, :3]


FACE_VERTICES = {
    "north": [0, 3, 2, 1],
    "south": [4, 5, 6, 7],
    "west": [0, 4, 7, 3],
    "east": [1, 2, 6, 5],
    "up": [3, 7, 6, 2],
    "down": [0, 1, 5, 4],
}

FACE_LIGHT = {
    "north": 1.00,
    "south": 0.74,
    "west": 0.82,
    "east": 0.94,
    "up": 1.12,
    "down": 0.58,
}


def camera_matrix(yaw: float, pitch: float) -> np.ndarray:
    return rotation_matrix([pitch, yaw, 0])[:3, :3]


def collect_faces(
    model: Model,
    animation_name: str | None,
    time_value: float,
    yaw: float,
    pitch: float,
) -> tuple[list[dict[str, Any]], tuple[float, float, float, float]]:
    pose = animation_pose(model, animation_name, time_value)
    camera = camera_matrix(yaw, pitch)
    faces: list[dict[str, Any]] = []
    all_points: list[np.ndarray] = []
    for bone_name, bone in model.bones.items():
        if bone_is_hidden(model, bone_name):
            continue
        for cube in bone.cubes:
            world = cube_vertices(model, bone_name, cube, pose)
            camera_vertices = (camera @ world.T).T
            all_points.extend(camera_vertices)
            uv_data = face_uv(model, cube)
            for face_name, indices in FACE_VERTICES.items():
                points = camera_vertices[indices]
                normal = np.cross(points[1] - points[0], points[2] - points[0])
                if normal[2] >= -0.001:
                    continue
                uv = uv_data[face_name]
                faces.append(
                    {
                        "points": points,
                        "depth": float(np.mean(points[:, 2])),
                        "uv": (uv["uv"][0], uv["uv"][1], uv["uv_size"][0], uv["uv_size"][1]),
                        "light": FACE_LIGHT[face_name],
                        "face": face_name,
                    }
                )
    if not all_points:
        raise ValueError(f"No visible geometry for {model.creature_id}")
    array = np.array(all_points)
    bounds = (
        float(array[:, 0].min()),
        float(array[:, 0].max()),
        float(array[:, 1].min()),
        float(array[:, 1].max()),
    )
    return faces, bounds


def bilinear_point(quad: list[tuple[float, float]], u: float, v: float) -> tuple[float, float]:
    top_x = quad[0][0] * (1 - u) + quad[1][0] * u
    top_y = quad[0][1] * (1 - u) + quad[1][1] * u
    bottom_x = quad[3][0] * (1 - u) + quad[2][0] * u
    bottom_y = quad[3][1] * (1 - u) + quad[2][1] * u
    return top_x * (1 - v) + bottom_x * v, top_y * (1 - v) + bottom_y * v


def shade_color(color: tuple[int, int, int, int], factor: float) -> tuple[int, int, int, int]:
    return (
        max(0, min(255, int(color[0] * factor))),
        max(0, min(255, int(color[1] * factor))),
        max(0, min(255, int(color[2] * factor))),
        color[3],
    )


def draw_textured_quad(
    draw: ImageDraw.ImageDraw,
    texture: Image.Image,
    quad: list[tuple[float, float]],
    uv_rect: tuple[float, float, float, float],
    light: float,
    subdivisions: int = 5,
) -> None:
    tex_u, tex_v, tex_w, tex_h = uv_rect
    for row in range(subdivisions):
        for column in range(subdivisions):
            u0, u1 = column / subdivisions, (column + 1) / subdivisions
            v0, v1 = row / subdivisions, (row + 1) / subdivisions
            cell = [
                bilinear_point(quad, u0, v0),
                bilinear_point(quad, u1, v0),
                bilinear_point(quad, u1, v1),
                bilinear_point(quad, u0, v1),
            ]
            sample_x = int((tex_u + (u0 + u1) * 0.5 * tex_w)) % texture.width
            sample_y = int((tex_v + (v0 + v1) * 0.5 * tex_h)) % texture.height
            color = texture.getpixel((sample_x, sample_y))
            draw.polygon(cell, fill=shade_color(color, light))
    draw.line(quad + [quad[0]], fill=(25, 23, 25, 180), width=1, joint="curve")


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def merge_bounds(bounds_list: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(item[0] for item in bounds_list),
        max(item[1] for item in bounds_list),
        min(item[2] for item in bounds_list),
        max(item[3] for item in bounds_list),
    )


def render_frame(
    model: Model,
    texture: Image.Image,
    animation_name: str | None,
    time_value: float,
    yaw: float,
    pitch: float,
    size: tuple[int, int],
    view_label: str,
    fixed_bounds: tuple[float, float, float, float] | None = None,
) -> Image.Image:
    width, height = size
    image = Image.new("RGBA", size, (22, 26, 30, 255))
    draw = ImageDraw.Draw(image, "RGBA")
    for y in range(height):
        factor = y / max(1, height - 1)
        color = (
            int(26 + 18 * factor),
            int(31 + 19 * factor),
            int(35 + 20 * factor),
            255,
        )
        draw.line((0, y, width, y), fill=color)
    grid_color = (103, 112, 117, 35)
    for x in range(-width, width * 2, 48):
        draw.line((x, height - 95, width // 2 + (x - width // 2) * 0.18, height // 2), fill=grid_color, width=1)
    for y in range(height - 95, height // 2, -34):
        draw.line((0, y, width, y), fill=grid_color, width=1)
    draw.ellipse((width * 0.23, height * 0.79, width * 0.77, height * 0.92), fill=(0, 0, 0, 75))

    faces, current_bounds = collect_faces(model, animation_name, time_value, yaw, pitch)
    bounds = fixed_bounds or current_bounds
    min_x, max_x, min_y, max_y = bounds
    model_width = max(0.001, max_x - min_x)
    model_height = max(0.001, max_y - min_y)
    top_margin = 145 if width >= 900 else 115
    bottom_margin = 118 if width >= 900 else 100
    side_margin = 90 if width >= 900 else 65
    scale = min((width - side_margin * 2) / model_width, (height - top_margin - bottom_margin) / model_height)
    center_x = width / 2 - ((min_x + max_x) / 2) * scale
    center_y = top_margin + (max_y * scale)

    faces.sort(key=lambda item: item["depth"], reverse=True)
    for face in faces:
        quad = [(center_x + point[0] * scale, center_y - point[1] * scale) for point in face["points"]]
        draw_textured_quad(draw, texture, quad, face["uv"], face["light"])

    accent = (*model.accent, 255)
    draw.rectangle((0, 0, width, 10), fill=accent)
    draw.text((42, 28), model.display_name, font=font(38 if width >= 900 else 28, True), fill=(239, 242, 240, 255))
    draw.text((44, 78), f"VIEW: {view_label}", font=font(18 if width >= 900 else 14, True), fill=accent)
    draw.text(
        (width - (310 if width >= 900 else 245), 34),
        "MODEL PREVIEW / NOT GAMEPLAY",
        font=font(16 if width >= 900 else 12, True),
        fill=(240, 194, 81, 255),
    )
    draw.text(
        (width - (310 if width >= 900 else 245), 62),
        "Rendered from GEO + PNG resources",
        font=font(13 if width >= 900 else 10),
        fill=(190, 198, 199, 255),
    )
    hitbox = " x ".join(f"{value:g}" for value in model.hitbox)
    footer = f"re_demo | {model.cube_count} cubes | {len(model.bones)} bones | hitbox {hitbox} blocks"
    draw.rectangle((0, height - 74, width, height), fill=(12, 15, 18, 222))
    draw.text((42, height - 51), footer, font=font(15 if width >= 900 else 11), fill=(210, 216, 215, 255))
    if animation_name:
        duration = model.animations[animation_name]["animation_length"]
        progress = min(1.0, time_value / max(0.001, duration))
        draw.rectangle((42, height - 20, width - 42, height - 13), fill=(66, 72, 75, 255))
        draw.rectangle((42, height - 20, 42 + (width - 84) * progress, height - 13), fill=accent)
        draw.text((42, 105), animation_name, font=font(13 if width >= 900 else 10), fill=(187, 196, 196, 255))
        if abs(time_value - model.hit_time) <= max(0.055, duration / 36):
            hit_text = f"HIT FRAME {model.hit_time:.2f}s"
            box_width = 220 if width >= 900 else 165
            draw.rectangle((width - box_width - 42, 92, width - 42, 128), fill=(149, 34, 40, 230))
            draw.text((width - box_width - 30, 101), hit_text, font=font(14 if width >= 900 else 10, True), fill=(255, 245, 231, 255))
    return image


def png_metadata(model: Model) -> PngImagePlugin.PngInfo:
    geo_path = GEO_DIR / f"{model.creature_id}.geo.json"
    texture_path = TEXTURE_DIR / f"{model.creature_id}.png"
    info = PngImagePlugin.PngInfo()
    info.add_text("preview_notice", "OFFLINE MODEL PREVIEW - NOT GAMEPLAY")
    info.add_text("source_geo_sha256", file_sha256(geo_path))
    info.add_text("source_texture_sha256", file_sha256(texture_path))
    info.add_text("generator", "tools/render_creature_evidence.py")
    return info


def render_model_evidence(model: Model) -> list[Path]:
    texture_path = TEXTURE_DIR / f"{model.creature_id}.png"
    texture = Image.open(texture_path).convert("RGBA")
    outputs: list[Path] = []
    views = {
        "front": (0.0, -8.0, "FRONT"),
        "side": (-90.0, -8.0, "SIDE"),
        "back": (180.0, -8.0, "BACK"),
    }
    for file_label, (yaw, pitch, view_label) in views.items():
        image = render_frame(model, texture, None, 0.0, yaw, pitch, (1024, 1024), view_label)
        output = EVIDENCE_DIR / f"{model.creature_id}_{file_label}.png"
        image.convert("RGB").save(output, pnginfo=png_metadata(model), optimize=True)
        outputs.append(output)

    animation_name = f"animation.{model.creature_id}.{model.signature_attack}"
    duration = float(model.animations[animation_name]["animation_length"])
    frame_count = max(24, int(math.ceil(duration * 18)) + 1)
    times = [duration * index / (frame_count - 1) for index in range(frame_count)]
    yaw, pitch = -35.0, -10.0
    all_bounds = [collect_faces(model, animation_name, time_value, yaw, pitch)[1] for time_value in times]
    fixed_bounds = merge_bounds(all_bounds)
    frames = [
        render_frame(
            model,
            texture,
            animation_name,
            time_value,
            yaw,
            pitch,
            (384, 384),
            "ATTACK 3/4",
            fixed_bounds=fixed_bounds,
        ).convert("RGB").quantize(colors=48, method=Image.Quantize.MEDIANCUT)
        for time_value in times
    ]
    output = EVIDENCE_DIR / f"{model.creature_id}_{model.signature_attack}.gif"
    comment = (
        f"OFFLINE MODEL PREVIEW - NOT GAMEPLAY; "
        f"geo={file_sha256(GEO_DIR / f'{model.creature_id}.geo.json')}; "
        f"texture={file_sha256(texture_path)}; "
        f"animation={animation_name}"
    ).encode("ascii")
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=max(40, int(duration * 1000 / frame_count)),
        loop=0,
        optimize=True,
        disposal=2,
        comment=comment,
    )
    outputs.append(output)
    return outputs


def render_all() -> dict[str, list[str]]:
    ensure_directories()
    specs = get_models()
    outputs: dict[str, list[str]] = {}
    for creature_id, spec in specs.items():
        model = load_resource_model(spec)
        paths = render_model_evidence(model)
        outputs[creature_id] = [str(path.relative_to(ROOT)) for path in paths]
    return outputs


EXPECTED_ANIMATIONS = {
    "licker": {
        "idle": 2.0,
        "walk": 1.0,
        "hurt": 0.6,
        "death": 2.4,
        "claw": 1.0,
        "leap": 1.4,
        "tongue": 1.2,
        "ambush": 1.4,
    },
    "tyrant": {
        "idle": 2.5,
        "walk": 1.4,
        "hurt": 0.7,
        "death": 3.0,
        "punch": 1.6,
        "shove": 1.2,
        "charge": 2.0,
        "break": 1.4,
        "rage": 2.0,
    },
    "g1_birkin": {
        "idle": 2.2,
        "walk": 1.3,
        "hurt": 0.65,
        "death": 3.2,
        "slam": 1.8,
        "sweep": 2.0,
        "grab": 2.0,
        "rage": 2.0,
    },
}

REQUIRED_HIT_TIMES = {
    "licker": {"claw": 0.45, "leap": 0.6, "tongue": 0.55},
    "tyrant": {"punch": 0.8, "shove": 0.5, "charge": 1.0, "break": 0.7},
    "g1_birkin": {"slam": 0.9, "sweep": 1.0, "grab": 0.75},
}


def count_keyframes(animation_data: dict[str, Any]) -> int:
    count = 0
    for tracks in animation_data.get("bones", {}).values():
        for channel in ("rotation", "position", "scale"):
            track = tracks.get(channel)
            if isinstance(track, dict):
                count += len(track)
            elif isinstance(track, list):
                count += 1
    return count


def walk_outliner(nodes: list[Any]) -> tuple[set[str], int]:
    names: set[str] = set()
    cube_references = 0
    for node in nodes:
        if isinstance(node, str):
            cube_references += 1
            continue
        if isinstance(node, dict):
            names.add(str(node.get("name")))
            child_names, child_cubes = walk_outliner(node.get("children", []))
            names.update(child_names)
            cube_references += child_cubes
    return names, cube_references


def relative_files_for_checksums() -> list[Path]:
    paths: list[Path] = []
    patterns = [
        "src/main/resources/assets/re_demo/geo/*.geo.json",
        "src/main/resources/assets/re_demo/animations/*.animation.json",
        "src/main/resources/assets/re_demo/textures/entity/*.png",
        "art/*.bbmodel",
        "art/creature_manifest.json",
        "docs/evidence/*_front.png",
        "docs/evidence/*_side.png",
        "docs/evidence/*_back.png",
        "docs/evidence/*.gif",
        "docs/evidence/README.md",
        "tools/*creature*.py",
    ]
    for pattern in patterns:
        paths.extend(ROOT.glob(pattern))
    return sorted({path for path in paths if path.is_file()}, key=lambda path: str(path.relative_to(ROOT)))


def validate_all() -> dict[str, Any]:
    ensure_directories()
    errors: list[str] = []
    checks: list[str] = []
    manifest_path = ART_DIR / "creature_manifest.json"
    if not manifest_path.exists():
        errors.append("Missing art/creature_manifest.json")
        manifest: dict[str, Any] = {"creatures": {}}
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        checks.append("Generation manifest parses as JSON")

    specs = get_models()
    for creature_id, spec in specs.items():
        geo_path = GEO_DIR / f"{creature_id}.geo.json"
        animation_path = ANIMATION_DIR / f"{creature_id}.animation.json"
        texture_path = TEXTURE_DIR / f"{creature_id}.png"
        bbmodel_path = ART_DIR / f"{creature_id}.bbmodel"
        required_paths = [geo_path, animation_path, texture_path, bbmodel_path]
        for path in required_paths:
            if not path.exists():
                errors.append(f"Missing {path.relative_to(ROOT)}")
        if any(not path.exists() for path in required_paths):
            continue

        try:
            geo = json.loads(geo_path.read_text(encoding="utf-8"))
            geometry = geo["minecraft:geometry"][0]
            description = geometry["description"]
            bones = geometry["bones"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            errors.append(f"{geo_path.name}: invalid GeckoLib geometry: {exc}")
            continue
        bone_names = {bone["name"] for bone in bones}
        cube_count = sum(len(bone.get("cubes", [])) for bone in bones)
        if description.get("identifier") != f"geometry.re_demo.{creature_id}":
            errors.append(f"{creature_id}: wrong geometry identifier")
        if cube_count < 20:
            errors.append(f"{creature_id}: only {cube_count} cubes, expected at least 20")
        if len(bones) < 20:
            errors.append(f"{creature_id}: only {len(bones)} bones, expected at least 20")
        cube_names = [cube.get("name") for bone in bones for cube in bone.get("cubes", [])]
        if len(cube_names) != len(set(cube_names)):
            errors.append(f"{creature_id}: duplicate cube names")
        checks.append(f"{creature_id}: geometry {len(bones)} bones / {cube_count} cubes")

        if creature_id == "tyrant" and not {"coat_intact", "coat_torn"}.issubset(bone_names):
            errors.append("tyrant: missing coat_intact/coat_torn phase bones")
        if creature_id == "g1_birkin":
            if not {"eye_open", "eye_closed", "right_shoulder"}.issubset(bone_names):
                errors.append("g1_birkin: missing eye or right shoulder bones")
            shoulder = next((bone for bone in bones if bone["name"] == "right_shoulder"), None)
            if shoulder and any(abs(float(actual) - expected) > 0.001 for actual, expected in zip(shoulder["pivot"], [-12, 34.4, 0])):
                errors.append(f"g1_birkin: right_shoulder pivot is {shoulder['pivot']}, expected [-12, 34.4, 0]")

        try:
            animations_json = json.loads(animation_path.read_text(encoding="utf-8"))
            animations = animations_json["animations"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            errors.append(f"{animation_path.name}: invalid animation JSON: {exc}")
            continue
        expected = EXPECTED_ANIMATIONS[creature_id]
        expected_names = {f"animation.{creature_id}.{suffix}" for suffix in expected}
        missing_animations = sorted(expected_names - set(animations))
        extra_animations = sorted(set(animations) - expected_names)
        if missing_animations:
            errors.append(f"{creature_id}: missing animations {missing_animations}")
        if extra_animations:
            errors.append(f"{creature_id}: unexpected animations {extra_animations}")
        for suffix, expected_length in expected.items():
            name = f"animation.{creature_id}.{suffix}"
            if name not in animations:
                continue
            animation_data = animations[name]
            actual_length = float(animation_data.get("animation_length", -1))
            if abs(actual_length - expected_length) > 0.001:
                errors.append(f"{name}: length {actual_length}, expected {expected_length}")
            unknown_bones = set(animation_data.get("bones", {})) - bone_names
            if unknown_bones:
                errors.append(f"{name}: tracks reference unknown bones {sorted(unknown_bones)}")
            if suffix == "death" or suffix in REQUIRED_HIT_TIMES.get(creature_id, {}):
                if count_keyframes(animation_data) < 4:
                    errors.append(f"{name}: attack/death track is effectively empty")
        checks.append(f"{creature_id}: {len(animations)} named animations bind to existing bones")

        with Image.open(texture_path) as texture:
            if texture.size != (TEXTURE_SIZE, TEXTURE_SIZE):
                errors.append(f"{creature_id}: texture is {texture.size}, expected {(TEXTURE_SIZE, TEXTURE_SIZE)}")
            if texture.mode not in ("RGB", "RGBA"):
                errors.append(f"{creature_id}: texture mode {texture.mode} is not RGB/RGBA")
            colors = texture.convert("RGB").getcolors(maxcolors=TEXTURE_SIZE * TEXTURE_SIZE)
            if colors is None or len(colors) < 24:
                errors.append(f"{creature_id}: texture lacks recognizable color/detail variation")
        checks.append(f"{creature_id}: texture is {TEXTURE_SIZE}x{TEXTURE_SIZE} with pixel detail")

        try:
            bbmodel = json.loads(bbmodel_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{creature_id}: bbmodel JSON invalid: {exc}")
            continue
        if bbmodel.get("meta", {}).get("model_format") != "bedrock":
            errors.append(f"{creature_id}: bbmodel model_format is not bedrock")
        if len(bbmodel.get("elements", [])) != cube_count:
            errors.append(f"{creature_id}: bbmodel element count does not match geometry")
        outliner_names, outliner_cubes = walk_outliner(bbmodel.get("outliner", []))
        if outliner_names != bone_names:
            errors.append(f"{creature_id}: bbmodel outliner bones do not match geometry")
        if outliner_cubes != cube_count:
            errors.append(f"{creature_id}: bbmodel outliner cube references do not match geometry")
        embedded = bbmodel.get("textures", [{}])[0].get("source", "")
        if not embedded.startswith("data:image/png;base64,"):
            errors.append(f"{creature_id}: bbmodel has no embedded PNG texture")
        else:
            try:
                embedded_bytes = base64.b64decode(embedded.split(",", 1)[1], validate=True)
                if embedded_bytes != texture_path.read_bytes():
                    errors.append(f"{creature_id}: bbmodel embedded texture differs from runtime texture")
            except (ValueError, base64.binascii.Error) as exc:
                errors.append(f"{creature_id}: bbmodel embedded texture invalid: {exc}")
        if {item.get("name") for item in bbmodel.get("animations", [])} != set(animations):
            errors.append(f"{creature_id}: bbmodel animation names do not match GeckoLib animation file")
        checks.append(f"{creature_id}: bbmodel structural openability checks passed")

        preview_hashes: set[str] = set()
        geo_hash = file_sha256(geo_path)
        texture_hash = file_sha256(texture_path)
        for view in ("front", "side", "back"):
            preview_path = EVIDENCE_DIR / f"{creature_id}_{view}.png"
            if not preview_path.exists():
                errors.append(f"Missing {preview_path.relative_to(ROOT)}")
                continue
            with Image.open(preview_path) as preview:
                if preview.size != (1024, 1024):
                    errors.append(f"{preview_path.name}: expected 1024x1024")
                if preview.info.get("preview_notice") != "OFFLINE MODEL PREVIEW - NOT GAMEPLAY":
                    errors.append(f"{preview_path.name}: missing preview disclosure metadata")
                if preview.info.get("source_geo_sha256") != geo_hash:
                    errors.append(f"{preview_path.name}: source geometry hash is stale")
                if preview.info.get("source_texture_sha256") != texture_hash:
                    errors.append(f"{preview_path.name}: source texture hash is stale")
                preview_hashes.add(hashlib.sha256(preview.convert("RGB").resize((64, 64)).tobytes()).hexdigest())
        if len(preview_hashes) != 3:
            errors.append(f"{creature_id}: front/side/back previews are not three distinct renders")

        gif_path = EVIDENCE_DIR / f"{creature_id}_{spec.signature_attack}.gif"
        if not gif_path.exists():
            errors.append(f"Missing {gif_path.relative_to(ROOT)}")
        else:
            frame_hashes: set[str] = set()
            with Image.open(gif_path) as gif:
                frame_total = getattr(gif, "n_frames", 1)
                if frame_total < 20:
                    errors.append(f"{gif_path.name}: only {frame_total} frames")
                for frame_index in range(frame_total):
                    gif.seek(frame_index)
                    frame_hashes.add(hashlib.sha256(gif.convert("RGB").resize((48, 48)).tobytes()).hexdigest())
                comment = gif.info.get("comment", b"")
                if isinstance(comment, str):
                    comment = comment.encode("utf-8")
                if b"NOT GAMEPLAY" not in comment or geo_hash.encode("ascii") not in comment:
                    errors.append(f"{gif_path.name}: source/disclosure comment missing or stale")
            if len(frame_hashes) < 10:
                errors.append(f"{gif_path.name}: animation has only {len(frame_hashes)} visually distinct frames")
        checks.append(f"{creature_id}: three orthographic previews and one animated attack preview checked")

        manifest_entry = manifest.get("creatures", {}).get(creature_id, {})
        if manifest_entry.get("cubes") != cube_count or manifest_entry.get("bones") != len(bones):
            errors.append(f"{creature_id}: generation manifest counts are stale")

    readme_path = EVIDENCE_DIR / "README.md"
    if not readme_path.exists():
        errors.append("Missing docs/evidence/README.md")
    elif "非游戏截图" not in readme_path.read_text(encoding="utf-8"):
        errors.append("Evidence README does not disclose that previews are not gameplay screenshots")
    else:
        checks.append("Chinese evidence notes disclose offline preview status")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "summary": {
            "creatures": len(specs),
            "errors": len(errors),
            "checks": len(checks),
        },
        "checks": checks,
        "errors": errors,
        "contract": {
            "hit_timings_seconds": REQUIRED_HIT_TIMES,
            "phase_bones": {
                "tyrant": ["coat_intact", "coat_torn"],
                "g1_birkin": ["eye_open", "eye_closed"],
            },
            "g1_right_shoulder_blocks": [-0.75, 2.15, 0],
        },
    }
    report_path = EVIDENCE_DIR / "validation-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    checksum_lines = [
        f"{file_sha256(path)}  {path.relative_to(ROOT)}"
        for path in relative_files_for_checksums()
        if path.name != "checksums.sha256"
    ]
    (EVIDENCE_DIR / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return report
