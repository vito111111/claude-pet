# -*- coding: utf-8 -*-
"""
生成 README 演示 GIF：把宠物的 idle / working / done 三态循环渲染成 assets/demo.gif。

不依赖截屏（宠物真实窗口是色键透明置顶窗，GDI 抓不到）：直接复用 pet.py 的
像素精灵数据(BODY/KEYBOARD)与调色板，用 Pillow 离线重绘，保证与真实宠物一致。

用法:  python make_demo_gif.py
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont

import pet  # 复用精灵 / 调色板 / 布局常量（导入安全：main 在 __main__ 守卫下）

CELL = pet.CELL
W, H = pet.W, pet.H
CX = pet.CX
BODY, BODY_TOP, KEYBOARD = pet.BODY, pet.BODY_TOP, pet.KEYBOARD
BODY_W, BODY_H, LEG_COLS = pet.BODY_W, pet.BODY_H, pet.LEG_COLS
ORANGE, ORANGE_HI, ORANGE_DK = pet.ORANGE, pet.ORANGE_HI, pet.ORANGE_DK
GREEN, GREEN_HI, GREEN_DK = pet.GREEN, pet.GREEN_HI, pet.GREEN_DK
EYE_DARK, EYE_WHITE = pet.EYE_DARK, pet.EYE_WHITE
KB_BODY, KB_BODY_DK, KB_KEY = pet.KB_BODY, pet.KB_BODY_DK, pet.KB_KEY
SPARK_DONE = pet.SPARK_DONE

BG = "#1E1F22"          # 演示卡片背景（深色，README 深浅主题下都耐看）
GROUND = "#26282C"

FONTS = r"C:\Windows\Fonts"


def _font(name, size):
    for cand in (name,):
        try:
            return ImageFont.truetype(os.path.join(FONTS, cand), size)
        except OSError:
            pass
    return ImageFont.load_default()


F_CODE = _font("consolab.ttf", 15)     # 飘动代码符号
F_CN = _font("msyhbd.ttc", 14)         # "完成!"
F_Z = _font("seguisli.ttf", 16)        # "z"（Segoe UI Light Italic，回退默认）
F_LABEL = _font("msyh.ttc", 14)        # 顶部状态标签（雅黑：含中英文）


# ---------------- 像素绘制（移植自 pet.py 的 px / blit，用 PIL 重画） ----------------
def px(d, x, y, color, shade=None, cell=CELL):
    d.rectangle([x, y, x + cell, y + cell], fill=color)
    if shade:
        d.rectangle([x, y + cell - 2, x + cell, y + cell], fill=shade)
        d.rectangle([x + cell - 2, y, x + cell, y + cell], fill=shade)


def blit(d, sprite, ox, oy, palette, shadepal, cell=CELL):
    for j, row in enumerate(sprite):
        for i, ch in enumerate(row):
            if ch in " .":
                continue
            col = palette.get(ch)
            if col is None:
                continue
            px(d, ox + i * cell, oy + j * cell, col, shadepal.get(ch), cell)


def _origin(cx, cy):
    return cx - BODY_W // 2, cy - BODY_H // 2


def _draw_body(d, cx, cy, main, hi, dark, sprite=BODY):
    ox, oy = _origin(cx, cy)
    blit(d, sprite, ox, oy, {"O": main, "H": hi, "E": EYE_DARK}, {})
    return ox, oy


def _eye_centers(cx, cy):
    ox, oy = _origin(cx, cy)
    ey = oy + 3 * CELL
    return (ox + 4 * CELL + CELL // 2, ey), (ox + 11 * CELL + CELL // 2, ey)


def _legs(d, cx, cy, frame, main, hi, dark):
    ox, oy = _origin(cx, cy)
    legtop = oy + 8 * CELL
    for i, col in enumerate(LEG_COLS):
        lx = ox + col * CELL
        lifted = (i % 2 + frame) % 2
        foot_y = legtop + (10 if lifted else 20)
        d.rectangle([lx, legtop, lx + CELL - 1, foot_y], fill=main)
        px(d, lx - 1, foot_y - CELL, hi, main)
    return legtop


def _sparkle_eyes(d, cx, cy):
    for (ex, ey) in _eye_centers(cx, cy):
        d.rectangle([ex - 1, ey - 6, ex + 4, ey + 2], fill=EYE_WHITE)
        d.rectangle([ex, ey - 4, ex + 3, ey + 1], fill=EYE_DARK)


def _star(d, cx, cy, r, color):
    pts = []
    for k in range(8):
        rad = r if k % 2 == 0 else r * 0.42
        a = k * math.pi / 4 - math.pi / 2
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    d.polygon(pts, fill=color)


def _ctext(d, cx, cy, text, font, fill):
    """以 (cx,cy) 为中心画文字。"""
    l, t, r, b = d.textbbox((0, 0), text, font=font)
    d.text((cx - (r - l) / 2 - l, cy - (b - t) / 2 - t), text, font=font, fill=fill)


# ---------------- 三态整帧 ----------------
def draw_working(d, frame):
    bob = -2 if (frame // 2) % 2 == 0 else 0
    cy = 78 + bob
    legtop = _legs(d, CX, cy, frame, ORANGE, ORANGE_HI, ORANGE_DK)
    kb_w = len(KEYBOARD[0]) * CELL
    blit(d, KEYBOARD, CX - kb_w // 2, legtop + 18,
         {"B": KB_BODY, "k": KB_KEY}, {"B": KB_BODY_DK, "k": "#5A6065"})
    _draw_body(d, CX, cy, ORANGE, ORANGE_HI, ORANGE_DK, sprite=BODY_TOP)
    syms = ["</>", "{}", "*", ";"]
    s = syms[(frame // 4) % len(syms)]
    _ctext(d, CX + 60, cy - 22 - (frame % 8), s, F_CODE, ORANGE_DK)


def draw_done(d, frame):
    cx = CX
    pulse = abs(math.sin(frame * 0.18))
    cy = 92 - int(pulse * 8)
    _draw_body(d, cx, cy, GREEN, GREEN_HI, GREEN_DK)
    _sparkle_eyes(d, cx, cy)
    bx, by = cx + 44, cy - 30
    d.rectangle([bx - 11, by - 11, bx + 11, by + 11], fill="#FFFFFF", outline=GREEN_DK, width=2)
    for dx, dy in ((-5, 0), (-2, 3), (1, 0), (4, -3), (7, -6)):
        d.rectangle([bx + dx, by + dy, bx + dx + 4, by + dy + 4], fill=GREEN_DK)
    for i, (sx, sy) in enumerate(((-46, -20), (44, 18), (-42, 22))):
        if (frame // 3 + i) % 3 == 0:
            _star(d, cx + sx, cy + sy, 7, SPARK_DONE)
    _ctext(d, cx, cy + 52, "完成!", F_CN, GREEN_DK)


def draw_idle(d, frame):
    sway = int(math.sin(frame * 0.06) * 4)
    cx = CX + sway
    cy = 110
    _draw_body(d, cx, cy, ORANGE, ORANGE_HI, ORANGE_DK)
    if (frame % 60) < 30:
        _ctext(d, cx + 46, cy - 22 - (frame % 30) // 3, "z", F_Z, ORANGE_DK)


LABELS = {"idle": "idle  ·  空闲待命", "working": "working  ·  正在干活",
          "done": "done  ·  完成提醒"}
DRAW = {"idle": draw_idle, "working": draw_working, "done": draw_done}


def render_frame(state, frame):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 18, W, H], fill=GROUND)          # 一点地面感
    d.text((10, 8), LABELS[state], font=F_LABEL, fill="#9AA0A6")
    DRAW[state](d, frame)
    return img


def main():
    seq = [("idle", 30), ("working", 34), ("done", 26)]
    frames = []
    for state, n in seq:
        for f in range(n):
            frames.append(render_frame(state, f))
    out_dir = os.path.join(pet._HERE, "assets")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "demo.gif")
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=90, loop=0, optimize=True, disposal=2)
    print("wrote", out, "(%d frames, %d bytes)" % (len(frames), os.path.getsize(out)))


if __name__ == "__main__":
    main()
