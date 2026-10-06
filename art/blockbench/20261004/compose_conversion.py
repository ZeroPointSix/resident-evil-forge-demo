"""Assemble review board from the final GEO render, not an old source PNG."""
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont

root = Path(sys.argv[1])
stats = json.loads((root/'blockbench_validation.json').read_text())
render = json.loads((root/'render_validation.json').read_text())
font = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'


def f(size):
    return ImageFont.truetype(font, size)


board = Image.new('RGB', (2400, 1380), '#eef2f2')
draw = ImageDraw.Draw(board)
draw.text((70, 35), 'RE FORGE / BLOCKBENCH', font=f(45), fill='#203d39')
draw.text((70, 103), '已批准低模的方块格式适配 · 从最终 .geo.json 实际渲染', font=f(28), fill='#506665')
board.paste(Image.open(root/'converted_lineup_raw.png').convert('RGB'), (0, 175))
for key, title, color in [('tyrant', 'TYRANT', '#1f6b57'),
                          ('g1_birkin', 'G1 BIRKIN', '#945043'), ('licker', 'LICKER', '#b84865')]:
    x = render['models'][key]['screen_center_x']
    s = stats['models'][key]
    draw.line((x-110, 1236, x+110, 1236), fill=color, width=5)
    label = f'{title}  |  {s["cubes"]} cubes'
    draw.text((x, 1260), label, font=f(31), fill='#203b38', anchor='mt')
    draw.text((x, 1310), f'{s["logical_vertices"]:,} 顶点 · 同尺度 1:1', font=f(24), fill='#506665', anchor='mt')
board.save(root/'converted_lineup.png')
print('CONVERSION_BOARD_OK', board.size)
