# Blockbench 源文件

本目录中的三份 `.bbmodel` 是由 `tools/generate_creature_assets.py` 从原创语义模型定义生成的可编辑源文件：

- `licker.bbmodel`
- `tyrant.bbmodel`
- `g1_birkin.bbmodel`

每份源文件都包含完整骨骼层级、方块元素、内嵌 256×256 PNG 贴图和全部动画轨道。项目格式为 Blockbench Bedrock Entity (`bedrock`)，采用逐面 UV。

资源为本项目原创方块化设计，没有提取或重新分发 Capcom 游戏模型、纹理或动画。运行时导出文件位于 `src/main/resources/assets/re_demo/`；`creature_manifest.json` 记录模型数量、碰撞箱契约、关键攻击时点和生成时文件哈希。
