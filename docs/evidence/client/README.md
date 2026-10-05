# 真实客户端证据（安装版 JAR）

最新可内嵌实机图（捕获源 `580c39f`，新增正/侧/背三面、20 格无 HUD 三怪合影、runClient 三怪、逐场景静态图）：[580c39f/](580c39f/README.md)。更早的捕获源档案：[896df9f/](896df9f/README.md)。

本目录其余文件是更早的 **Minecraft 1.20.1 / Forge 47.2.0** 官方客户端对已安装 `re_demo-0.1.2.jar` 的原生画面，**不是** Blockbench / Three.js 离线预览。

来源 CI：[Controlled Real Client Evidence run 37257038076](https://github.com/ZeroPointSix/resident-evil-forge-demo/actions/runs/37257038076)（head `c7398661005b2ba63d6ccd172876074dd4d93384`，结论 success）。`report.json` 是该次流水线原件；`kind=controlled-real-client-scene`，`passed=true`，`origin=native Minecraft F2`。

安装版 JAR SHA-256（与 `tested-mod/re_demo-0.1.2.jar` 一致）：

`ad2a6a733b7400017fb21f1dccc9c1f7ecd68eb8c8cd6d7ed731cf281c874734`

同场还安装了 GeckoLib Forge 1.20.1-4.4.9。完整 MP4、专服/客户端日志和测试 JAR 仍在上述 artifact 中，本目录只固化可在 PR 里直接打开的 PNG。

## 原生 F2（建模可见）

| 画面 | 文件 | SHA-256 |
| --- | --- | --- |
| 三怪同场，Boss 血条 | [00-three-creatures.png](00-three-creatures.png) | `bd5247ee94e736ad1655e30c9a1d8792f77f1c16d975b42115f1c990cff7cfcf` |
| 舔食者近景 | [licker-model.png](licker-model.png) | `ad399c8c2051689a360dcc78d489bcd97a5271b42ae1e5a3307a8987a269f617` |
| 暴君近景（风衣/帽子） | [tyrant-model.png](tyrant-model.png) | `89bf9bfe991dc001f989c27ea9b42df56a6f14a89679d30a7e9b5a6e0d2f1203` |
| G1 近景（巨右臂/肩眼） | [g1_birkin-model.png](g1_birkin-model.png) | `837314800ffcb154a30d575ef0af9f123d58dc0e2b0e4078a23f3295296182a0` |

上述四张哈希与 `report.json` 的 `screenshots[]` 逐项一致。

## 攻击瞬间（从实机 MP4 抽帧）

攻击录像本身是 xvfb 下真实官方客户端 + 真实专服录制；抽帧只为能在 GitHub PR 里内嵌。抽帧不是 F2，时间点如下：

| 场景 | 源 clip | 抽帧 | 文件 |
| --- | --- | --- | --- |
| 舔食者近战 | `licker-attack.mp4` @ 3.0s | [stills/licker-attack.png](stills/licker-attack.png) | 铁傀儡目标 + 舔食者 |
| 舔食者舌击 | `licker-tongue.mp4` @ 3.2s | [stills/licker-tongue.png](stills/licker-tongue.png) | 目标已掉落物品 |
| 舔食者爬墙接近 | `licker-crawl.mp4` @ 4.5s | [stills/licker-crawl.png](stills/licker-crawl.png) | 远距接近 |
| 暴君拳击 | `tyrant-attack.mp4` @ 3.2s | [stills/tyrant-attack.png](stills/tyrant-attack.png) | 风衣攻击姿态 |
| 暴君冲锋 | `tyrant-charge.mp4` @ 4.0s | [stills/tyrant-charge.png](stills/tyrant-charge.png) | 冲锋距离 |
| G1 砸击 | `g1_birkin-attack.mp4` @ 5.0s | [stills/g1_birkin-attack.png](stills/g1_birkin-attack.png) | 傀儡掉落铁锭/虞美人 |
| 三怪同场战斗 | `creature-brawl.mp4` @ 18.0s | [stills/creature-brawl.png](stills/creature-brawl.png) | 三怪各自打静止高血量傀儡 |

服务端确认每只怪对未脚本伤害的目标造成 >5 HP（见 `report.json` confirmations `CE_*_55` 至 `_58`）。

## 刷怪蛋

本轮 F2 肖像与攻击场由受控流水线用 `/summon re_demo:{licker,tyrant,g1_birkin}` 布置，**画面里没有手持刷怪蛋**。三颗 `ForgeSpawnEggItem` 已打进 JAR（`assets/re_demo/models/item/*_spawn_egg.json`），并由 GameTest `spawnEggsCreateRealEntities` 调用真实 `egg.useOn` 生成对应实体。创造栏物品：舔食者刷怪蛋 / Tyrant Spawn Egg / G1 Birkin Spawn Egg。

## 边界

- `manual_playtest=false`，`full_gameplay_acceptance=false`：自动化、受控的安装版客户端/专服验收，不是完整人工生存试玩。
- 同场战斗目标是静止高血量铁傀儡，目标无脚本伤害，每只怪独立 AI 输出。
- G1 肩眼 1.75 倍窗口由 GameTest 精确断言，本目录没有逐帧捕捉开眼命中。
- 未合并 `main`。
