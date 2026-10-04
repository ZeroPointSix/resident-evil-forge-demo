# Approved remodel: runtime rig and attack map

This integration uses the art approved at `d28b9bdd7abd56b8aadaf47fc7414212fd2eb181`.
The original files under `art/blockbench/20261004` are unchanged. Runtime facing
is normalized by a 180-degree Y turn; every original cube and palette texel is
preserved. Art-specific wrapper bones supply articulation without remodeling.

## Editable and installed assets

- `art/{tyrant,g1_birkin,licker}.bbmodel`: editable runtime rigs and animations.
- `src/main/resources/assets/re_demo/geo/*.geo.json`: installed geometry.
- `src/main/resources/assets/re_demo/animations/*.animation.json`: installed clips.
- `src/main/resources/assets/re_demo/textures/entity/*.png`: approved palettes.
- `tools/integrate_approved_models.py`: deterministic approved-art integration.
- `art/runtime_remodel_manifest.json`: source and runtime geometry checksums.

## Attack-to-bone contract

Times below are animation seconds at normal speed. Existing gameplay timing,
damage, cooldowns and speed attributes are unchanged. Tyrant rage retains its
existing synchronized animation/gameplay acceleration.

| Creature / action | Visible bones | Contact time / server tick |
| --- | --- | --- |
| Tyrant punch | `torso`, `upper_arm_r`, `forearm_r`, `hand_r` | 0.80 s / 16 |
| Tyrant shove | both `upper_arm_*`, `torso` | 0.50 s / 10 |
| Tyrant charge | forward-leaning `torso`, alternating `thigh_*` | charge begins 1.00 s / 20 |
| Tyrant break | `upper_arm_r`, `forearm_r`, `torso` | 0.70 s / 14 |
| G1 slam | `right_upper_arm`, `right_forearm` | 0.90 s / 18 |
| G1 sweep | `right_upper_arm`, `right_forearm` crossing in front | 1.00 s / 20 |
| G1 grab / throw | `right_upper_arm`, `right_forearm`, `right_hand` | 0.75 s / 15; release 1.50 s / 30 |
| Licker claw | `chest`, `upper_arm_l`, `forearm_l`, `claw_l` | 0.45 s / 9 |
| Licker tongue | `jaw`, `tongue_base`, `tongue_mid`, `tongue_tip` | 0.55 s / 11 |
| Licker crawl | alternating `upper_arm_*`, `thigh_*`, root bob | looping movement state |

G1's shoulder eye has a matching multipart hit area. While exposed, eye ancestors
are held in the gameplay pose; slam, sweep and grab use arm descendants so the
attack does not disappear or snap when the eye opens. Tyrant coat state hides
descendants as well as the wrapper. Licker's tongue attaches to the head rather
than the moving jaw, preserving its forward extension above the floor.

## Reproduce validation

```sh
python tools/integrate_approved_models.py
python -m unittest discover -s tests -v
./gradlew build runGameTestServer
python tools/qa/validate_assets.py --root . --jar build/libs/re_demo-0.1.1.jar
```

The independent tests check source hashes, transformed cube vertices, original
palettes, bone references, editor/runtime keyframe agreement, eye position,
forward strike coordinates, overhead-to-downward slam, front-crossing sweep,
and tongue clearance. These are necessary checks, not visual acceptance alone.

The `Controlled Real Client Evidence` workflow installs the built JAR in both
an actual Forge client and server with GeckoLib 4.4.9, captures native F2 PNGs
and screen recordings, and verifies damage from normal mob AI against a
stationary high-health target. Camera-only night vision makes surfaces readable.
It does not substitute a model viewer, manually trigger animations, or fabricate
target damage. The report records installed JAR SHA-256 and source revision.

These controlled scenes do not constitute a complete survival playtest. They
do not establish full animation polish for every phase, hanging pose, terrain,
multiplayer latency, or all combat combinations. Review the actual recordings
and retain the workflow report alongside the installable artifact.

## Install

Use Minecraft Java 1.20.1, Forge 47.2.0, Java 17 and GeckoLib Forge 4.4.9.
Place `re_demo-0.1.1.jar` and GeckoLib in the instance's `mods` directory and
remove the older `re_demo` JAR. Client and server need matching versions.
Test in a new or backed-up world. Spawn IDs are `re_demo:tyrant`,
`re_demo:g1_birkin` and `re_demo:licker`; combat targets must not be creative or
spectator players. See `README.zh-CN.md` for installation and summon commands.
