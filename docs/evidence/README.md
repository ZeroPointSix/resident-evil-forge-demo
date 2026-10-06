# 三只怪模型证据说明

本目录根下的三视图 PNG 和攻击 GIF 均为脚本直接读取本 PR 内的 GeckoLib `.geo.json`、`.animation.json` 与 PNG 贴图后进行的离线模型预览，**不是游戏截图**，也不代表 Forge 客户端内的最终光照、粒子或命中判定表现。每张 PNG 的元数据都写入源 geometry 与 texture 的 SHA-256；每个 GIF 的 comment 字段写入同类来源哈希和动画名，可用验证脚本核对。

真实 Minecraft 1.20.1 Forge 客户端的原生 F2 截图与攻击录像抽帧在 [client/](client/README.md)，不要把下面的离线预览当成实机验收。

## 预览索引

| 怪物 | 正面 | 侧面 | 背面 | 关键攻击动画 |
| --- | --- | --- | --- | --- |
| 舔食者 Licker | [正面](licker_front.png) | [侧面](licker_side.png) | [背面](licker_back.png) | [Tongue · 1.2s · 命中 0.55s](licker_tongue.gif) |
| 暴君 Tyrant | [正面](tyrant_front.png) | [侧面](tyrant_side.png) | [背面](tyrant_back.png) | [Punch · 1.6s · 命中 0.8s](tyrant_punch.gif) |
| G1 柏金 | [正面](g1_birkin_front.png) | [侧面](g1_birkin_side.png) | [背面](g1_birkin_back.png) | [Slam · 1.8s · 命中 0.9s](g1_birkin_slam.gif) |

## 契约与可读性

| 怪物 | 实体碰撞箱（格） | 视觉重点 | 阶段 / 弱点骨骼 |
| --- | --- | --- | --- |
| 舔食者 | 1.35 × 1.05 × 1.35 | 低伏四足、外露脑、无眼、巨型前爪、长舌 | `brain`、三级舌骨与左右独立爪骨 |
| 暴君 | 1.2 × 2.95 × 1.2 | 近三格高、宽肩、帽子、厚重长风衣 | `coat_intact` / `coat_torn`，供 35% HP 阶段显隐 |
| G1 柏金 | 1.5 × 2.9 × 1.5 | 强不对称巨右臂、肩眼焦点 | `eye_open` / `eye_closed`；`right_shoulder` 枢轴为局部 (-0.75, 2.15, 0) 格 |

三套贴图均为 256×256 原创像素贴图。舔食者使用肌纤维、脑回与湿润舌面纹理；暴君使用风衣织纹、缝线、皮革与金属扣；G1 使用撕裂布料、突变肌束和高对比肩眼虹膜。纹理不是来自任何商业游戏资源。

## 生成与验证

在仓库根目录运行：

```bash
python tools/generate_creature_assets.py
python tools/render_creature_evidence.py
python tools/validate_creature_assets.py
```

验证器检查以下内容：

- Geo 骨骼、方块数量、唯一命名、G1 右肩精确枢轴和阶段骨骼；
- 固定动画名称、长度、非空攻击 / 死亡轨道以及轨道到现有骨骼的绑定；
- 256×256 RGB/RGBA PNG 及颜色细节；
- `.bbmodel` JSON、outliner、元素、内嵌贴图和动画的一致性；
- 9 张 1024×1024 三视图与 3 个至少 20 帧、至少 10 个不同画面的攻击 GIF；
- 证据文件的来源哈希和“非游戏截图”披露。

机器可读结果见 [validation-report.json](validation-report.json)，完整哈希见 [checksums.sha256](checksums.sha256)。
