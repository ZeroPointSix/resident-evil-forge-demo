"""Typeset review PNGs from actual Blender renders; never redraw model geometry."""

import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(sys.argv[1])
STATS = json.loads((ROOT/"model_stats.json").read_text())
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
MODELS = [
    ("tyrant", "TYRANT", "长外套 / 收腰肩胸 / 分离下摆", (37, 100, 82)),
    ("g1_birkin", "G1 BIRKIN", "单侧巨臂 / 厚肩厚掌 / 偏置重心", (168, 99, 40)),
    ("licker", "LICKER", "低伏四足 / 分离支撑 / 分段长舌", (149, 64, 77)),
]


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def write(draw, xy, text, size=34, fill=(32, 44, 49), bold=False):
    draw.text(xy, text, font=font(size, bold), fill=fill)


def backdrop(source, size):
    bg = Image.open(ROOT/source).convert("RGB").getpixel((0, 0))
    return Image.new("RGB", size, bg)


for index, (key, title, subtitle, accent) in enumerate(MODELS, 1):
    canvas = backdrop(key+"_front.png", (3000, 1480))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((75, 64, 86, 175), fill=accent)
    write(draw, (115, 53), title, 70, bold=True)
    write(draw, (118, 148), "原创低模体块评审  /  "+subtitle, 30)
    write(draw, (2540, 79), "RE FORGE / 0"+str(index), 28, accent, True)
    for i, (view, label) in enumerate([("front", "正面"), ("side", "右侧"), ("back", "背面")]):
        image = Image.open(ROOT/(key+"_"+view+".png")).convert("RGB")
        image = image.resize((960, 960), Image.Resampling.LANCZOS)
        canvas.paste(image, (20+i*1000, 255))
        write(draw, (76+i*1000, 215), label, 34, accent, True)
    draw.line((75, 1270, 2925, 1270), fill=accent, width=3)
    model = STATS["models"][key]
    dims = model["dimensions_xyz_m"]
    write(draw, (75, 1300), f'{model["polygons"]:,} 多边形  /  {model["triangles"]:,} 三角面  /  高 {dims[2]:.2f} m', 34, bold=True)
    write(draw, (75, 1370), "同一模型、同一正交尺度；实体网格已检查。仅评审，不是游戏内截图，也不是可直接装包的 .geo.json。", 28)
    canvas.save(ROOT/(key+"_turnaround.png"), optimize=True)

overview = backdrop("tyrant_three_quarter.png", (3000, 1540))
draw = ImageDraw.Draw(overview)
write(draw, (78, 52), "RESIDENT EVIL FORGE", 70, bold=True)
write(draw, (82, 151), "三只原创低模体块 · 第一轮外观评审", 36)
for i, (key, title, subtitle, accent) in enumerate(MODELS):
    image = Image.open(ROOT/(key+"_three_quarter.png")).convert("RGB").resize((980, 980), Image.Resampling.LANCZOS)
    overview.paste(image, (10+i*1000, 260))
    draw.rectangle((75+i*1000, 1240, 150+i*1000, 1248), fill=accent)
    write(draw, (75+i*1000, 1283), title, 46, accent, True)
    write(draw, (75+i*1000, 1352), subtitle, 28)
write(draw, (75, 1460), "Blender 4 / Cycles 实际模型渲染  ·  本页分别取景，不用于比身高；同比例请看 lineup_review.png。", 28)
overview.save(ROOT/"review_overview.png", optimize=True)

lineup = Image.open(ROOT/"lineup.png").convert("RGB")
canvas = backdrop("lineup.png", (2400, 1350))
canvas.paste(lineup, (0, 160))
draw = ImageDraw.Draw(canvas)
write(draw, (60, 35), "同框比例 / SAME WORLD SCALE", 52, bold=True)
write(draw, (62, 106), "三只保持 1:1 对象缩放；正交相机，统一地面。米为本轮设计尺度，不是官方身高设定。", 26)
heights = [STATS["models"][key]["dimensions_xyz_m"][2] for key, *_ in MODELS]
for i, (key, title, subtitle, accent) in enumerate(MODELS):
    write(draw, (70+i*785, 1235), f"{title} / {heights[i]:.2f} m", 36, accent, True)
canvas.save(ROOT/"lineup_review.png", optimize=True)
