# RE Forge 三怪物独立低模预览

本目录只用于外观评审。没有替换游戏中的模型、贴图或动画，没有合并 main。
基线为 `test/runtime-acceptance` 的 `deb10db8a08361041c07bd7a23abb1cf22812ba5`。

## 交付内容

- 每只正面、右侧、背面 PNG，来自同一个真实三维模型和相同正交尺度。
- 三张三视图评审板、三张补充三分之四视角图、一张总览。
- `lineup_review.png` 为同场景、同世界尺度的比例图，三只对象缩放均为 1。
- `monster_blockouts.blend` 保留模型分组、材质和摄影棚；三份 OBJ/MTL 可独立导入。
- `model_stats.json`、`interchange_validation.json`、`validation.json` 记录工具版本、真实面数、文件回导和校验值。

## 模型范围

| 模型 | 主要识别特征 | 多边形 | 三角面 | 本轮设计高度 |
| --- | --- | ---: | ---: | ---: |
| Tyrant | 帽檐、厚肩胸、收腰长外套、分离下摆 | 1124 | 2104 | 3.35 m |
| G1 Birkin | 单侧厚肩、明显偏大的前臂与手掌、肩部眼状体块 | 842 | 1812 | 2.94 m |
| Licker | 低伏四足、分离支撑、长分段舌头 | 1270 | 2596 | 1.16 m |

高度包含最高体块，不是官方身高设定。面数仅统计怪物本身，不包含相机、灯光和地面。
模型由原创几何脚本构建，未使用官方模型、贴图或三视图。当前是低模体块，不是最终贴图、绑定或动画成品。

## Blender 4 复现

沙箱使用 Blender 4.3.2、Cycles CPU、128 采样；该发行版无 OpenImageDenoise，因此关闭降噪。
补充 CI 使用官方 Blender 4.2.20 LTS 包、32 采样和降噪。最终工具版本以交付目录内的统计文件为准。
合成评审板使用 Pillow 和 Noto Sans CJK，未重画三维轮廓。

```bash
export BLENDER_DENOISE=0
export BLENDER_SAMPLES=128
export GITHUB_SHA=$(git rev-parse HEAD)
blender -b --python-exit-code 1 --python art/previews/20261004/build_blockouts.py -- --output /tmp/re-forge-output
blender -b /tmp/re-forge-output/monster_blockouts.blend --python-exit-code 1 --python art/previews/20261004/check_interchange.py
python3 art/previews/20261004/compose_review.py /tmp/re-forge-output
python3 art/previews/20261004/validate_preview.py /tmp/re-forge-output
```

## 验证范围

构建检查每个零件都是闭合网格并有实体厚度；渲染前检查所有可见顶点均在画面内。
保存后重新打开 Blend，并分别重新导入 OBJ，对比模型零件数和面数。
每张交付 PNG 检查尺寸、非空白和可读取性，另做实际图片视觉复核。
这不等于用户审美批准，也不等于 Minecraft 真实运行测试。

## Minecraft 1.20.1 Forge + GeckoLib

可以作为后续适配的造型基准，但不能直接把 `.blend` 或 `.obj` 放进资源包。
当前模型包含削角、楔形和不规则网格。GeckoLib 4 的默认模型烘焙路径按骨骼下的 cubes 构建几何，不能假定任意 Blender 网格都能直接转换。

用户确认造型后，下一轮需要在 Blockbench/GeckoLib 工程中重建为分段、旋转的长方体，设置骨骼层级和关节轴，制作原创 UV 贴图和动画，导出 `.geo.json`、`.animation.json` 与 PNG，再进入 Forge 1.20.1 实机验收。

依据：[GeckoLib 1.20.1 Forge 模型烘焙源码](https://github.com/bernie-g/geckolib/blob/1.20.1/Forge/src/main/java/software/bernie/geckolib/loading/object/BakedModelFactory.java)、[Blockbench 建模指南](https://github.com/bernie-g/geckolib/wiki/Making-Your-Models-%28Blockbench%29)、[GeckoLib 4 模型指南](https://github.com/bernie-g/geckolib/wiki/Geo-Models-%28Geckolib4%29)。

## 评审入口

- [独立 PR #6](https://github.com/ZeroPointSix/resident-evil-forge-demo/pull/6)，目标分支为 `test/runtime-acceptance`，不自动合并。
- [Notion 计划与评审页](https://app.notion.com/p/RE-Forge-3ef463aed7e681e0ae06f43e08f50dca)。
- [原始 Slack 交付线程](https://chatgpt-a1a4278.slack.com/archives/C0BDF94JZEE/p1791081675156759)。
