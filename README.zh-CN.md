# Resident Evil Forge Demo

Minecraft Java Edition 1.20.1 的非官方同人怪物 Demo。实现范围为舔食者、暴君和 G1 威廉·柏金，不包含感染、枪械、结构生成或剧情系统。

> 当前开发分支尚在集成与验收中。构建、游戏截图与可下载安装包应以最终验收记录为准，不能仅凭本说明判断已经可用。

## 安装目标

1. 安装 Minecraft Java Edition **1.20.1** 和 **Forge 47.2.0**，使用 **64 位 Java 17**。
2. 将最终构建的 `re_demo-0.1.0.jar` 与 **GeckoLib Forge 1.20.1 4.4.9** 放入同一实例的 `mods` 目录。不要混用 Fabric / NeoForge 或其他 Minecraft 版本。
3. 多人游戏时客户端与服务端都安装相同版本的本模组和 GeckoLib。首次测试使用新建世界或备份世界，难度设为普通。
4. 本项目不提供 Minecraft、Forge 或 GeckoLib 的许可证授权；各依赖按其官方渠道安装。

## 生成怪物

三种刷怪蛋位于创造模式的刷怪蛋物品栏，也支持以下命令：

```text
/summon re_demo:licker ~ ~ ~
/summon re_demo:tyrant ~ ~ ~
/summon re_demo:g1_birkin ~ ~ ~
/give @s re_demo:licker_spawn_egg
/give @s re_demo:tyrant_spawn_egg
/give @s re_demo:g1_birkin_spawn_egg
```

怪物不会自然生成。创造模式与旁观模式玩家不会成为主动攻击目标；战斗验证需要切换生存模式。

## 战斗机制

| 怪物 | 生命 / 护甲 | 主要机制 |
| --- | --- | --- |
| 舔食者 | 120 / 4 | 无视觉索敌；脚步、冲刺、落地、方块操作、受击和弹道撞击产生声源。先调查，重复声源进入追踪；安静后遗忘。支持爬墙、短时挂伏、爪击、飞扑和舌击。 |
| 暴君 | 400 / 12 | 长时间追击，拳击、推击和冲锋有前摇。生命降至 35% 时移速提高 25%、伤害提高 20%，攻击动画与判定同步加速。 |
| G1 柏金 | 480 / 8 | 独立肩眼命中区域。肩眼打开时，防御结算后的伤害为普通命中的 1.75 倍。砸地、横扫与抓取后投掷；30% 生命进入狂暴，恢复间隔缩短、眼部窗口延长。 |

暴君默认只会破坏 `re_demo:tyrant_breakable` 标签中的木门、玻璃和玻璃板，每次最多处理前方三格高的一列；不拆地下方块、石头或带方块实体的容器。`mobGriefing=false` 会禁止拆障。

## 配置

首次启动后生成 `config/re_demo-common.toml`：

- `tyrantBreakSoftBlocks`：是否允许暴君处理白名单软障碍，仍受 `mobGriefing` 限制。
- `damageScale`：三只怪物的输出伤害倍率，默认 1.0。
- `lickerSoundMemoryTicks`：舔食者的声音记忆时长，默认 120 tick，即 6 秒。

## 开发与测试

```sh
./gradlew build
./gradlew runGameTestServer
./gradlew runClient
./gradlew runServer
```

GameTest 使用真实 Forge 服务端实体与伤害逻辑，检查刷怪蛋、声音识别与遗忘、攻击前摇、阶段阈值、拆障约束、眼部倍率和存档重载。自动测试不替代模型三视图、攻击观感及真实客户端截图检查。

`tools/make_test_structure.py` 可重建版本库内的固定空测试结构。游戏测试使用默认配置运行；不要把开发测试世界当作日常存档。

## 资源与许可

模型和贴图采用原创方块化表达，不提取或分发 Capcom 原始游戏资源。动画资源位于 `assets/re_demo/animations`，几何模型位于 `assets/re_demo/geo`，Blockbench 源文件位于 `art`，证据位于 `docs/evidence`。

基础音效事件引用 Minecraft 原有声音，不复制或重新分发其音频文件。Resident Evil 和相关角色属于各自权利人；本项目不代表或隶属于 Capcom、Mojang 或 Microsoft。项目自有代码与原创资源许可见 `LICENSE`。
