# 2026-10-05 接管验收记录（timeout_takeover）

本文件记录本轮接管验收（Devin, timeout_takeover）对既有美术交付的回源核验与功能性验收结果。
本轮只做低模挡板 + 三视图验收；未替换游戏运行时资源、未合并 main、未做 JAR/客户端接入或动画验收。

## 回源核验（不信口述）

- 仓库 `ZeroPointSix/resident-evil-forge-demo`，分支 `art/remodel-blender4-20261004`。
- 造型源提交 `98585964b9c1e96884b6b11ca8c5c9640b5a1cfb`；Blockbench/GEO 交付至 `d28b9bdd7abd56b8aadaf47fc7414212fd2eb181`；核验时分支头 `959edfb`。
- 草稿 PR #6 已于 2026-10-05 02:16 UTC 被并行流程合入 `test/runtime-acceptance`（本轮未执行任何合并）；`main` 仍为 `f9ed0894b3c663199bfa24d87e038a74430f1484`，未受影响。
- 实际存在并逐个核验的文件：
  - `art/previews/20261004/deliverables/`：`tyrant|g1_birkin|licker` 各 `_front/_side/_back/_three_quarter.png` 与 `_turnaround.png` 评审板，`lineup.png`、`lineup_review.png`、`review_overview.png`，`monster_blockouts.blend`（166 KB）、三份 `.obj`/`.mtl`，`model_stats.json`、`validation.json`、`interchange_validation.json`、`sandbox-render-evidence.log`。
  - `art/blockbench/20261004/`：三份 `.bbmodel` + `.geo.json` + `_palette.png`，`converted_lineup.png`，`blockbench_validation.json`、`geometry_validation.json`、`render_validation.json` 与复现脚本（`convert_blockouts.py`、`render_geo.py`、`compose_conversion.py`、`check_geometry.py`、`validate_blockbench.cjs`）、README。
- Slack 侧候选文件 `converted_lineup.png`、`re-forge-blockbench-20261004.zip` 与仓库内容一致（zip 为 `art/blockbench/20261004/` 快照加 README）。

## 逐张目视验收（19 张 PNG 全部看过）

| 验收项 | 结果 |
| --- | --- |
| Tyrant 正/侧/背 | 通过：帽檐、厚肩胸、收腰长外套、分离下摆、手套与靴子在三个视角一致可辨 |
| G1 Birkin 正/侧/背 | 通过：单侧明显偏大的变异臂（含肩部眼状体块、爪、棘刺），人形半身对比清晰 |
| Licker 正/侧/背 | 通过：低伏四足、分离支撑、带齿口部与分段长舌（侧面长舌拖地可见） |
| 同框比例图 | 通过：`lineup.png`/`lineup_review.png` 同场景 1:1 对象缩放、正交相机、统一地面，标高 3.35/2.94/1.16 m |
| 评审板/补充图 | `*_turnaround.png`（标注三视图+面数）、`*_three_quarter.png`、`review_overview.png` 均非空白、内容一致 |

与现有游戏模型对比的可见改进：G1 巨臂不再是红色平板（有体积、眼部、爪、棘）；Tyrant 有可读的体块结构而非僵硬外套；Licker 是带四肢和舌头的低伏生物而非贴地红团。

## 独立复核（不依赖交付方 JSON）

- OBJ 实数：tyrant 1152v/1124f、g1_birkin 992v/842f、licker 1416v/1270f —— 与 `model_stats.json` 一致。
- `.geo.json` 实数：format_version 1.12.0 cube-only；171/315/305 cubes → 1368/2520/2440 逻辑顶点 —— 与 README/报告一致。
- `interchange_validation.json`：blend 复开 + 三份 OBJ 回导通过；`blockbench_validation.json`：BBModel 往返一致、GEO 回导通过、全部 cube 实体、全 UV 有纹理、无 poly_mesh。

## 工具与格式结论

- 挡板渲染：Blender 4.3.2（沙箱）Cycles CPU 128 采样，无降噪；评审板合成 Pillow。
- 格式适配：Blockbench 4.12.6，Bedrock 1.12.0 cube-only GEO，面向 GeckoLib 4 方块加载路径（不含 poly_mesh/动画）。
- 能否进 Minecraft 1.20.1 Forge + GeckoLib：几何格式兼容 GeckoLib 4 的 cube 加载路径；仍缺动画骨骼绑定、纹理资源路径接入与客户端实测，不能宣称可直接替换游戏模型。

## 边界声明

- 本轮未合并 main；PR #6 的合入 `test/runtime-acceptance` 为并行流程行为，非本轮操作。
- 本轮未改动 `src/` 下任何游戏运行时资源或玩法代码；本文件仅新增于美术预览路径。
- 全部素材为按剪影原创的方块风格，未拷贝官方 Capcom 贴图/模型/三视图。
- 等用户看过预览后再决定是否进入模组接入阶段。
