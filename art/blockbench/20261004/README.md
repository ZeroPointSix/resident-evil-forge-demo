# RE Forge：已批准低模的 Blockbench / GeckoLib 适配

本目录仅供美术评审与后续绑定使用，未替换游戏资源，未修改玩法，未合并 main。
源造型为同分支提交 `98585964b9c1e96884b6b11ca8c5c9640b5a1cfb` 的
`art/previews/20261004/deliverables/monster_blockouts.blend`。
保留原始部件、比例、站姿与原创配色，不包含 Capcom 官方模型或贴图。

## 文件

| 模型 | Blockbench 源文件 | GeckoLib 几何 | 纹理 |
| --- | --- | --- | --- |
| Tyrant | tyrant.bbmodel | tyrant.geo.json | tyrant_palette.png |
| G1 Birkin | g1_birkin.bbmodel | g1_birkin.geo.json | g1_birkin_palette.png |
| Licker | licker.bbmodel | licker.geo.json | licker_palette.png |

`converted_lineup.png` 是从本目录最终 GEO 文件重新构建的同尺度实渲染图，
不是沿用 Blender 原模型预览，也不是图像生成的示意图。
源文件中嵌入了色板纹理；GEO 导入时使用旁边对应的 palette PNG。

## 数量与改动

| 模型 | 原始 Blender 顶点 | 方块 | 方块角点合计 | 四边面 | 三角面 | 骨骼/分组 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tyrant | 1152 | 171 | 1368 | 1026 | 2052 | 51 |
| G1 Birkin | 992 | 315 | 2520 | 1890 | 3780 | 44 |
| Licker | 1416 | 305 | 2440 | 1830 | 3660 | 60 |

顶点口径为每个独立方块 8 个角点，未焊接共享位置。
按面法线/UV 拆点的渲染顶点为每个方块 24 个，分别 4104、7560、7320。
内部相接面保留，后续可按动画分组优化。

GeckoLib 4 常规模型加载器支持实体方块，不直接支持 Blender 任意网格。
因此原倒角变为硬边方块，原渐缩八边截面变为多个实体阶梯截面；
这属于格式适配，不是等拓扑无损转换。原帽檐与长外套、单侧巨臂及肩眼、
四足低身与分段长舌均保留。每个原始部件都有同名分组，便于继续编辑。

16 模型单位对应 1 Blender 米。坐标从 Blender 的 (x,y,z) 映射到
Blockbench 的 (x,z,-y)，GEO 的 X 镜像与欧拉角约定由官方 Blockbench 导出器处理。

## 工具和验证

工具均运行于本单 Daytona 沙箱：Blender 4.3.2、Blockbench 4.12.6、
Chromium、Playwright 1.55.1。无需购买服务。

1. 从已批准的 Blend 实际读取网格和部件局部变换，生成 cuboid 结构。
2. 在真实 Blockbench 中建组、加载原创色板并导出 BBModel 和 GEO。
3. 重新打开 BBModel，检查方块和嵌入纹理数，并要求再导出的 GEO 一致。
4. 重新导入 GEO，逐角点比较位置，检查实体尺寸、纹理、骨骼名称和父子关系。
5. Blender 独立解析最终 GEO；逐角点对照 Blockbench，再渲染同框图。

原始部件边界偏差阈值 0.12 米，跨工具角点偏差阈值 0.002 模型单位。
实际数值、工具版本、文件 SHA256 见 `blockbench_validation.json`、
`render_validation.json` 与 `geometry_validation.json`。

## Minecraft 1.20.1 Forge + GeckoLib

几何采用 `format_version: 1.12.0` 的 cube-only GEO；未使用
`poly_mesh`、贴图网格、新版显示变换或旋转 UV。
它面向 GeckoLib 4 的方块加载路径。BBModel 使用原生 Bedrock 编辑格式，
可直接在标准 Blockbench 打开；后续需要 GeckoLib 动画工具时，可安装官方插件后
通过“转换项目”切换为 GeckoLib Animated Model。

此轮只有静态美术文件，不代表已通过游戏运行时验收。
分组保留原部件，枢轴是编辑起点，并非最终战斗动画绑定。
下一阶段需用户批准后再做动画层级、最终枢轴、攻击/移动动画、材质和
Forge 客户端检查。GEO 本身不携带 Minecraft 纹理资源路径，未来接入时需由
GeoModel 指定对应 palette PNG，不能只复制 JSON。

参考：[GeckoLib 建模流程](https://github.com/bernie-g/geckolib/wiki/Making-Your-Models-%28Blockbench%29)、
[GeckoLib 4 Geo 模型](https://github.com/bernie-g/geckolib/wiki/Geo-Models-%28Geckolib4%29)、
[Blockbench 4.12.6 Bedrock 导出器](https://github.com/JannisX11/blockbench/blob/v4.12.6/js/io/formats/bedrock.js)。

## 复现

保留 `convert_blockouts.py`、`validate_blockbench.cjs`、`render_geo.py`、
`compose_conversion.py` 和 `check_geometry.py`。
先从批准的 Blend 提取中间结构，再用官方 Blockbench 导出和回导，最后渲染。
中间 JSON 和浏览器临时文件不纳入最终交付。编辑器安装目录可通过
`BLOCKBENCH_ROOT`、`PLAYWRIGHT_MODULE` 指定。
