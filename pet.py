# -*- coding: utf-8 -*-
"""
Claude Code 桌面宠物 + 占卜（合并版 manager + 像素渲染器）

一个进程、**全桌面只有一只宠物**，同时扮演两个角色：

【会话伙伴】无论开多少个 Claude Code 窗口都共用这一只，状态是所有会话的聚合：
  working : 任意会话正在干活 —— 敲键盘动画（橘色）
  done    : 任意会话刚结束 —— 变绿、跳动、冒泡弹出窗口名 + 提示音，保持 5 秒
  idle    : 全部空闲 —— 橘色安静待命；空闲满 60s 变出分身一起踢足球，有活立刻收场

【占卜师】点一下宠物即可占卜（不打断会话伙伴的职责，占卜结束后自动回到会话状态）：
  左键单击  -> 占卜菜单：今日运势 / 易经卦象 / 诗经摇签 / 抽一签(おみくじ) / 黄历宜忌
  左键拖拽  -> 移动位置
  右键      -> 设置 / 关于 / 退出
  · 易经：凝神起卦动画；诗经：宠物抖动模拟摇签筒。出结果弹一张运势卡。
  · 2 小时锁定：同一玩法 2h 内重复点击返回同一结果(“再抽一次”可强制重抽)。
  · 接通 claude 时由 `claude -p` 现场生成解读(易经/诗经≤20字)，库内文案为离线兜底。

状态来源：hook_status.py 由 Claude Code hooks 写入 ~/.claude/pet_status/<session>.json；
本进程每 500ms 轮询聚合。占卜数据/语料在同目录 divine_engine.py 与 data/。
单例：绑定本地端口，重复启动自动退出。
"""

import os
import sys
import json
import time
import math
import socket
import threading
import tkinter as tk

import divine_engine as eng
from health_link import read_health

try:
    import winsound          # Windows 自带，用于"完成"提示音
except ImportError:
    winsound = None

# 完成提示音：优先项目自定义音，其次系统 tada.wav，再不行合成提示音
_HERE = os.path.dirname(os.path.abspath(__file__))
CUSTOM_SOUND = os.path.join(_HERE, "sounds", "done.wav")
TADA_SOUND = os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                          "Media", "tada.wav")


def _chime():
    """合成一段上行小三和弦作为兜底完成音（C5-E5-G5-C6）。"""
    try:
        for f in (523, 659, 784, 1047):
            winsound.Beep(f, 120)
    except Exception:
        pass


def done_beep():
    """工作完成时播放完成提示音（非阻塞）。"""
    if winsound is None:
        return
    try:
        for snd in (CUSTOM_SOUND, TADA_SOUND):
            if os.path.exists(snd):
                winsound.PlaySound(snd,
                                   winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
        threading.Thread(target=_chime, daemon=True).start()
    except Exception:
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass


# ---------------------------------------------------------------- 配置
STATUS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "pet_status")
HEARTBEAT_FILE = os.path.join(STATUS_DIR, ".heartbeat")  # 渲染器存活心跳
PROJECTS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects")
SINGLETON_PORT = 50573          # 单例守卫端口（合并后唯一端口）
POLL_MS = 500                   # 状态轮询间隔
FRAME_MS = 90                   # 动画帧间隔 (~11fps)
DONE_HOLD_SEC = 5               # done(绿色+冒泡)展示多久后回到 idle/working
DONE_INFER_SEC = 12             # transcript 兜底：工作停止后绿色"完成"维持多久 -> idle
WORK_STALE_SEC = 30 * 60        # working 超过此时长无更新 -> 视为 idle
DEAD_SEC = 12 * 3600            # 状态文件超过此时长 -> 视为死会话
NO_SESSION_EXIT_SEC = 120       # 无任何会话超过此时长 -> 退出进程
TRANSCRIPT_WORK_SEC = 40        # transcript 在此秒内有更新 -> working
TRANSCRIPT_LIVE_SEC = 300       # transcript 超过此时长无更新 -> 该会话离线
IDLE_SOCCER_SEC = 60            # 持续空闲超过此时长 -> 踢足球

CEREMONY_MS = 1300              # 占卜动画最短仪式时长(避免库兜底秒回太突兀)
CLAUDE_MAX_MS = 32000           # 等 Claude 解读最长时间，超时只用本地内容

KEY = "#FF00FF"                 # 透明色键

# 调色板 (body 取自 Claude Code 官方图标 #D77959)
ORANGE      = "#D77959"
ORANGE_HI   = "#E89A7C"
ORANGE_DK   = "#B25C3E"
GREEN       = "#5BB06A"
GREEN_HI    = "#86CF93"
GREEN_DK    = "#3C8A4C"
PURPLE      = "#7C6BC4"          # 占卜凝神态
PURPLE_HI   = "#9E8FD8"
PURPLE_DK   = "#5A4A9E"
EYE_DARK    = "#141210"
EYE_WHITE   = "#FFFFFF"
KB_BODY     = "#3C4043"
KB_BODY_DK  = "#26282B"
KB_KEY      = "#7A8085"
SPARK_DONE  = "#FFD45E"
SPARK       = "#FFD45E"

W, H = 200, 220                 # 画布尺寸(常规)；加宽 W 以容纳占卜动画
SOCCER_W = 380                  # 踢足球时画布加宽
DONE_W = 340                    # 完成冒泡时画布加宽
CX = W // 2                     # 水平中心
CELL = 7                        # 像素块边长
BALL_WHITE = "#FFFFFF"
BALL_DARK  = "#23252A"


# ---------------------------------------------------------------- 像素绘图核心
def px(c, x, y, color, shade=None, cell=CELL):
    c.create_rectangle(x, y, x + cell, y + cell, fill=color, outline="")
    if shade:
        c.create_rectangle(x, y + cell - 2, x + cell, y + cell, fill=shade, outline="")
        c.create_rectangle(x + cell - 2, y, x + cell, y + cell, fill=shade, outline="")


def blit(c, sprite, ox, oy, palette, shadepal, cell=CELL):
    for j, row in enumerate(sprite):
        for i, ch in enumerate(row):
            if ch in " .":
                continue
            col = palette.get(ch)
            if col is None:
                continue
            px(c, ox + i * cell, oy + j * cell, col, shadepal.get(ch), cell)


# Claude Code 官方图标小人 (16x10)：O=身体 E=眼睛
BODY = [
    "..OOOOOOOOOOOO..",
    "..OOOOOOOOOOOO..",
    "..OOEOOOOOOEOO..",
    "..OOEOOOOOOEOO..",
    "OOOOOOOOOOOOOOOO",
    "OOOOOOOOOOOOOOOO",
    "..OOOOOOOOOOOO..",
    "..OOOOOOOOOOOO..",
    "...O.O....O.O...",
    "...O.O....O.O...",
]
BODY_TOP = BODY[:8]
BODY_W = len(BODY[0]) * CELL     # 112
BODY_H = len(BODY) * CELL        # 70
LEG_COLS = (3, 5, 10, 12)

KEYBOARD = [
    "BBBBBBBBBBBBBBB",
    "BkBkBkBkBkBkBkB",
    "BBBBBBBBBBBBBBB",
    "BkkBkkkkkkBkkBB",
    "BBBBBBBBBBBBBBB",
]


def _origin(cx, cy):
    return cx - BODY_W // 2, cy - BODY_H // 2


def _draw_body(c, cx, cy, main, hi, dark, sprite=BODY):
    ox, oy = _origin(cx, cy)
    pal = {"O": main, "H": hi, "E": EYE_DARK}
    blit(c, sprite, ox, oy, pal, {})
    return ox, oy


def _eye_centers(cx, cy):
    ox, oy = _origin(cx, cy)
    ey = oy + 3 * CELL
    return (ox + 4 * CELL + CELL // 2, ey), (ox + 11 * CELL + CELL // 2, ey)


def _closed_eyes(c, cx, cy):
    """占卜凝神：把眼睛画成闭合横线。"""
    for (ex, ey) in _eye_centers(cx, cy):
        c.create_rectangle(ex - 4, ey, ex + 4, ey + 2, fill=EYE_DARK, outline="")


def _legs(c, cx, cy, frame, main, hi, dark):
    ox, oy = _origin(cx, cy)
    legtop = oy + 8 * CELL
    for i, col in enumerate(LEG_COLS):
        lx = ox + col * CELL
        lifted = (i % 2 + frame) % 2
        foot_y = legtop + (10 if lifted else 20)
        c.create_rectangle(lx, legtop, lx + CELL - 1, foot_y, fill=main, outline="")
        px(c, lx - 1, foot_y - CELL, hi, main)
    return legtop


def _sparkle_eyes(c, cx, cy):
    for (ex, ey) in _eye_centers(cx, cy):
        c.create_rectangle(ex - 1, ey - 6, ex + 4, ey + 2, fill=EYE_WHITE, outline="")
        c.create_rectangle(ex, ey - 4, ex + 3, ey + 1, fill=EYE_DARK, outline="")


# ------------------------------------------------ 会话状态：working / done / idle
def draw_working(c, frame):
    bob = -2 if (frame // 2) % 2 == 0 else 0
    cy = 78 + bob
    legtop = _legs(c, CX, cy, frame, ORANGE, ORANGE_HI, ORANGE_DK)
    kb_w = len(KEYBOARD[0]) * CELL
    blit(c, KEYBOARD, CX - kb_w // 2, legtop + 18,
         {"B": KB_BODY, "k": KB_KEY}, {"B": KB_BODY_DK, "k": "#5A6065"})
    _draw_body(c, CX, cy, ORANGE, ORANGE_HI, ORANGE_DK, sprite=BODY_TOP)
    syms = ["</>", "{}", "*", ";"]
    s = syms[(frame // 4) % len(syms)]
    c.create_text(CX + 60, cy - 22 - (frame % 8), text=s, fill=ORANGE_DK,
                  font=("Consolas", 11, "bold"))


def draw_done(c, frame, cx=CX):
    pulse = abs(math.sin(frame * 0.18))
    cy = 92 - int(pulse * 8)
    _draw_body(c, cx, cy, GREEN, GREEN_HI, GREEN_DK)
    _sparkle_eyes(c, cx, cy)
    bx, by = cx + 44, cy - 30
    c.create_rectangle(bx - 11, by - 11, bx + 11, by + 11,
                       fill="#FFFFFF", outline=GREEN_DK, width=2)
    for dx, dy in ((-5, 0), (-2, 3), (1, 0), (4, -3), (7, -6)):
        c.create_rectangle(bx + dx, by + dy, bx + dx + 4, by + dy + 4,
                           fill=GREEN_DK, outline="")
    for i, (sx, sy) in enumerate(((-46, -20), (44, 18), (-42, 22))):
        if (frame // 3 + i) % 3 == 0:
            c.create_text(cx + sx, cy + sy, text="✦", fill=SPARK_DONE,
                          font=("Segoe UI", 12, "bold"))
    c.create_text(cx, cy + 52, text="完成!", fill=GREEN_DK,
                  font=("Microsoft YaHei", 10, "bold"))


def draw_idle(c, frame):
    sway = int(math.sin(frame * 0.06) * 4)
    cx = CX + sway
    cy = 110
    _draw_body(c, cx, cy, ORANGE, ORANGE_HI, ORANGE_DK)
    # 偶尔头顶冒个小星，暗示「点我占卜」
    if (frame % 90) < 44:
        a = 9 + ((frame // 6) % 3)
        c.create_text(cx + 50, cy - 30 - (frame % 44) // 4, text="✦",
                      fill=SPARK, font=("Segoe UI", a, "bold"))
    elif (frame % 90) < 64:
        c.create_text(cx + 46, cy - 22 - (frame % 20) // 3, text="z",
                      fill=ORANGE_DK, font=("Segoe UI", 9 + ((frame // 6) % 3), "italic"))


# ------------------------------------------------ 占卜态：凝神 / 摇签
def draw_divining(c, frame):
    """凝神占卜(易经/运势/黄历/抽签)：火花变魔法紫、闭眼、周身✦绕行。"""
    bob = int(math.sin(frame * 0.25) * 3)
    cx, cy = CX, 100 + bob
    _draw_body(c, cx, cy, PURPLE, PURPLE_HI, PURPLE_DK)
    _closed_eyes(c, cx, cy)
    for k in range(5):
        a = frame * 0.22 + k * 2 * math.pi / 5
        sx = cx + int(math.cos(a) * 58)
        sy = cy + int(math.sin(a) * 34)
        size = 8 + (k % 3)
        c.create_text(sx, sy, text="✦", fill=SPARK if k % 2 else PURPLE_HI,
                      font=("Segoe UI", size, "bold"))
    dots = "." * (1 + (frame // 4) % 3)
    c.create_text(cx, cy + 58, text="占卜中" + dots, fill=PURPLE_DK,
                  font=("Microsoft YaHei", 11, "bold"))


def draw_shaking(c, frame):
    """诗经摇签：宠物左右抖动模拟摇签筒，竹签在筒中跳动。"""
    jitter = int(math.sin(frame * 0.9) * 7)         # 快速左右抖
    tilt = int(math.sin(frame * 0.9) * 2)
    cx, cy = CX + jitter, 98 + tilt
    _draw_body(c, cx, cy, ORANGE, ORANGE_HI, ORANGE_DK)
    _closed_eyes(c, cx, cy)
    # 头顶的签筒：深色竹筒 + 几根跳动的签
    tube_x, tube_y, tw = cx - 16, cy - 64, 32
    for i in range(5):
        sx = tube_x + 4 + i * 5
        sh = 18 + int(abs(math.sin(frame * 0.8 + i)) * 10)
        c.create_rectangle(sx, tube_y - sh, sx + 3, tube_y, fill="#C9A24B", outline="")
        c.create_rectangle(sx, tube_y - sh, sx + 3, tube_y - sh + 3, fill="#E63E3E", outline="")
    c.create_rectangle(tube_x, tube_y, tube_x + tw, tube_y + 26, fill="#7A5A33", outline="#553D22", width=2)
    c.create_rectangle(tube_x, tube_y, tube_x + tw, tube_y + 5, fill="#553D22", outline="")
    dots = "." * (1 + (frame // 4) % 3)
    c.create_text(cx - jitter, cy + 58, text="摇签中" + dots, fill="#7A5A33",
                  font=("Microsoft YaHei", 11, "bold"))


DRAWERS = {"working": draw_working, "done": draw_done, "idle": draw_idle}


# ------------------------------------------------ idle 满 60s：本体 + 分身踢足球
SOC_CY = 112
SOC_GROUND = SOC_CY + 52
SOC_BALL_R = 9
SOC_PERIOD = 26


def _soccer_player(c, cx, facing, kick):
    lean = facing * 3 if kick else 0
    pcx = cx + lean
    _draw_body(c, pcx, SOC_CY, ORANGE, ORANGE_HI, ORANGE_DK, sprite=BODY_TOP)
    ox, oy = _origin(pcx, SOC_CY)
    legtop = oy + 8 * CELL
    for i, col in enumerate(LEG_COLS):
        lx = ox + col * CELL
        front = (i >= 2) if facing > 0 else (i < 2)
        if kick and front:
            kx = lx + facing * 12
            c.create_rectangle(min(lx, kx), legtop, max(lx, kx) + CELL - 1,
                               legtop + CELL - 1, fill=ORANGE, outline="")
            px(c, kx, legtop, ORANGE_HI, ORANGE)
        else:
            foot = legtop + (12 if i % 2 else 18)
            c.create_rectangle(lx, legtop, lx + CELL - 1, foot, fill=ORANGE, outline="")
            px(c, lx - 1, foot - CELL, ORANGE_HI, ORANGE)


def _soccer_ball(c, bx, by, frame):
    bx, by, r = int(bx), int(by), SOC_BALL_R
    c.create_oval(bx - r, by - r, bx + r, by + r, fill=BALL_WHITE, outline=BALL_DARK, width=2)
    rot = frame * 0.45
    for k in range(5):
        a = rot + k * 2 * math.pi / 5
        sx = bx + int(math.cos(a) * 4)
        sy = by + int(math.sin(a) * 4)
        c.create_rectangle(sx - 2, sy - 2, sx + 2, sy + 2, fill=BALL_DARK, outline="")


def draw_soccer(c, frame):
    lcx, rcx = 96, SOCCER_W - 96
    lkx, rkx = lcx + 46, rcx - 46
    phase = frame % (2 * SOC_PERIOD)
    if phase < SOC_PERIOD:
        t = phase / SOC_PERIOD
        bx = lkx + (rkx - lkx) * t
        left_kick, right_kick = t < 0.15, t > 0.85
    else:
        t = (phase - SOC_PERIOD) / SOC_PERIOD
        bx = rkx - (rkx - lkx) * t
        right_kick, left_kick = t < 0.15, t > 0.85
    by = SOC_GROUND - int(math.sin(t * math.pi) * 72)
    _soccer_player(c, lcx, +1, left_kick)
    _soccer_player(c, rcx, -1, right_kick)
    _soccer_ball(c, bx, by, frame)
    if frame < 20:
        c.create_text(rcx, SOC_CY - 56, text="分身!", fill=ORANGE_DK,
                      font=("Microsoft YaHei", 9, "bold"))


# ------------------------------------------------ 健康关怀：不健康因素 -> 造型/颜色
# 严重度调色板(warn 琥珀 / alert 警示红)
HEALTH_PAL = {
    "warn":  ("#E0A33A", "#F0C46A", "#B07E1E"),
    "alert": ("#E0533C", "#F08068", "#B23A24"),
}
# factor -> (头顶 emoji, 简短中文)
HEALTH_INFO = {
    "drowsy":         ("😴", "有点困了"),
    "high_stress":    ("💢", "放松一下"),
    "too_close":      ("⚠", "离远些"),
    "need_move":      ("🚶", "该起身啦"),
    "slouch":         ("🪑", "坐直一点"),
    "high_shoulder":  ("⚖", "两肩拉平"),
    "need_eye_break": ("👀", "远眺一下"),
    "dry_eye":        ("💧", "多眨眨眼"),
    "dark_env":       ("💡", "光线偏暗"),
}
HEALTH_PRIORITY = ["drowsy", "high_stress", "too_close", "need_move",
                   "slouch", "high_shoulder", "need_eye_break", "dry_eye", "dark_env"]


def draw_health(c, frame, factors, severity):
    """有不健康因素时的宠物形态：整体变色 + 头顶因素提示 + 轻微体态变化。"""
    main, hi, dk = HEALTH_PAL.get(severity, HEALTH_PAL["warn"])
    primary = next((f for f in HEALTH_PRIORITY if f in factors),
                   factors[0] if factors else "need_move")
    emoji, cap = HEALTH_INFO.get(primary, ("⚠", "注意一下"))
    bob = int(math.sin(frame * 0.10) * 3)
    droop = 8 if primary in ("slouch", "drowsy") else 0   # 累/塌 -> 整体下沉
    cx, cy = CX, 112 + droop + bob
    _draw_body(c, cx, cy, main, hi, dk)
    if primary == "drowsy":
        _closed_eyes(c, cx, cy)                            # 困 -> 半眯眼
    # alert 抖动惊叹
    if severity == "alert" and (frame // 3) % 2 == 0:
        c.create_text(cx + 52, cy - 34, text="!", fill=dk,
                      font=("Segoe UI", 16, "bold"))
    c.create_text(cx, cy - 60, text=emoji, font=("Segoe UI Emoji", 20))
    c.create_text(cx, cy + 52, text=cap, fill=dk,
                  font=("Microsoft YaHei", 10, "bold"))


# ---------------------------------------------------------------- 结果卡
CARD_BG = "#FBF6EC"
CARD_INK = "#3A2E26"
CARD_SUB = "#8A7A6A"
CARD_LINE = "#E3D6C2"
HEADER_BY_MODE = {
    "iching": "#6E7BA8",
    "shijing": "#5F8A6A",
}


class ResultCard:
    """一张占卜结果卡(独立 Toplevel)。claude 解读到达后可原地补显示。"""

    _open = []

    def __init__(self, root, result, on_redraw):
        for old in list(ResultCard._open):
            old.close()
        ResultCard._open.append(self)
        self.root = root
        self.result = result
        self.on_redraw = on_redraw
        self.claude_widget = None

        self.win = tk.Toplevel(root)
        self.win.title("占卜")
        self.win.configure(bg=CARD_BG)
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        try:
            self.win.attributes("-toolwindow", True)
        except tk.TclError:
            pass
        self._build()
        self._place()
        self.win.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        r = self.result
        accent = HEADER_BY_MODE.get(r.get("mode"), "#C98A4B")
        PADX = 22
        head = tk.Frame(self.win, bg=accent)
        head.pack(fill="x")
        tk.Label(head, text=f"{r.get('icon','🔮')}  {r.get('title','')}",
                 bg=accent, fg="white", font=("Microsoft YaHei", 15, "bold"),
                 anchor="w", padx=PADX).pack(fill="x", pady=(12, 0))
        tk.Label(head, text=r.get("subtitle", ""), bg=accent, fg="#FCEFD9",
                 font=("Microsoft YaHei", 9), anchor="w",
                 padx=PADX).pack(fill="x", pady=(0, 12))

        body = tk.Frame(self.win, bg=CARD_BG)
        body.pack(fill="both", padx=0, pady=(4, 0))
        for title, text in r.get("sections", []):
            if not text:
                continue
            tk.Label(body, text=title, bg=CARD_BG, fg=accent,
                     font=("Microsoft YaHei", 11, "bold"), anchor="w",
                     padx=PADX).pack(fill="x", pady=(8, 0))
            tk.Label(body, text=text, bg=CARD_BG, fg=CARD_INK,
                     font=("Microsoft YaHei", 10), anchor="w", justify="left",
                     wraplength=380, padx=PADX).pack(fill="x")

        lucky = r.get("lucky") or {}
        if lucky:
            chips = tk.Frame(body, bg=CARD_BG)
            chips.pack(fill="x", padx=PADX, pady=(12, 2))
            for k, v in lucky.items():
                tk.Label(chips, text=f" {k} {v} ", bg="#F0E6D2", fg=CARD_INK,
                         font=("Microsoft YaHei", 9), padx=6, pady=2,
                         bd=1, relief="solid").pack(side="left", padx=(0, 6))

        if r.get("footer"):
            tk.Label(body, text=r["footer"], bg=CARD_BG, fg=CARD_SUB,
                     font=("Microsoft YaHei", 9, "italic"), anchor="w",
                     justify="left", wraplength=380,
                     padx=PADX).pack(fill="x", pady=(10, 2))

        # Claude 解读区(占位)
        if eng.load_config().get("use_claude", True) and eng.claude_available():
            tk.Frame(body, bg=CARD_LINE, height=1).pack(fill="x", padx=PADX, pady=(10, 0))
            tk.Label(body, text="✨ Claude 解读", bg=CARD_BG, fg="#9A6BC0",
                     font=("Microsoft YaHei", 10, "bold"), anchor="w",
                     padx=PADX).pack(fill="x", pady=(6, 0))
            self.claude_widget = tk.Label(
                body, text=r.get("claude_reading") or "正在凝神解读…",
                bg=CARD_BG, fg=CARD_INK if r.get("claude_reading") else CARD_SUB,
                font=("Microsoft YaHei", 10), anchor="w", justify="left",
                wraplength=380, padx=PADX)
            self.claude_widget.pack(fill="x", pady=(0, 2))
        elif r.get("claude_reading"):
            self.set_claude_reading(r["claude_reading"])

        btns = tk.Frame(self.win, bg=CARD_BG)
        btns.pack(fill="x", padx=PADX, pady=(14, 16))
        tk.Button(btns, text="再抽一次", command=self._redraw,
                  font=("Microsoft YaHei", 10), bg="#EFE3CD", fg=CARD_INK,
                  activebackground="#E4D4B6", relief="flat", padx=14,
                  pady=4, cursor="hand2").pack(side="left")
        tk.Button(btns, text="收好 ✦", command=self.close,
                  font=("Microsoft YaHei", 10, "bold"), bg=accent, fg="white",
                  activebackground=accent, relief="flat", padx=18, pady=4,
                  cursor="hand2").pack(side="right")

    def _place(self):
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = sw - w - 40
        y = max(20, sh - h - 120)
        self.win.geometry(f"+{x}+{y}")

    def set_claude_reading(self, text):
        if self.claude_widget is not None and self.win.winfo_exists():
            self.claude_widget.config(text=text, fg=CARD_INK)

    def _redraw(self):
        mode = self.result.get("mode", "horoscope")
        self.close()
        self.on_redraw(mode, force=True)

    def close(self):
        if self in ResultCard._open:
            ResultCard._open.remove(self)
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------- 健康建议弹窗
class HealthCard:
    """健康建议气泡卡：贴着宠物弹出，10 秒自动消失。
    若该建议带体操(routine)，提供"好，开始"按钮触发居中健身引导。"""

    _open = []
    DISMISS_MS = 10000

    def __init__(self, root, event, pet_xy, on_exercise):
        for old in list(HealthCard._open):
            old.close()
        HealthCard._open.append(self)
        self.root = root
        self.event = event
        self.on_exercise = on_exercise
        self._timer = None

        accent = "#E0533C" if event.get("type") in ("drowsy", "high_stress") else "#E0A33A"
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=accent)
        outer = tk.Frame(self.win, bg=accent)
        outer.pack(fill="both", expand=True, padx=2, pady=2)
        inner = tk.Frame(outer, bg="#FFFDF5")
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text=f"🐾 {event.get('title', '健康提醒')}", bg="#FFFDF5",
                 fg=accent, font=("Microsoft YaHei", 12, "bold"),
                 anchor="w").pack(fill="x", padx=14, pady=(12, 2))
        tk.Label(inner, text=event.get("body", ""), bg="#FFFDF5", fg="#3A2E26",
                 font=("Microsoft YaHei", 10), wraplength=240, justify="left",
                 anchor="w").pack(fill="x", padx=14, pady=(0, 8))

        row = tk.Frame(inner, bg="#FFFDF5")
        row.pack(fill="x", padx=14, pady=(0, 12))
        if event.get("routine"):
            tk.Button(row, text="好，开始 ▶", command=self._start, relief="flat",
                      bg=accent, fg="white", bd=0, cursor="hand2",
                      font=("Microsoft YaHei", 10, "bold"),
                      padx=14, pady=4).pack(side="left")
            tk.Button(row, text="稍后", command=self.close, relief="flat",
                      bg="#EFE3CD", fg="#7A6A55", bd=0, cursor="hand2",
                      font=("Microsoft YaHei", 10), padx=12, pady=4).pack(side="left", padx=8)
        else:
            tk.Button(row, text="知道啦", command=self.close, relief="flat",
                      bg="#EFE3CD", fg="#7A6A55", bd=0, cursor="hand2",
                      font=("Microsoft YaHei", 10), padx=14, pady=4).pack(side="left")

        self._place(pet_xy)
        self._timer = self.win.after(self.DISMISS_MS, self.close)

    def _place(self, pet_xy):
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        px, py = pet_xy
        x = min(max(10, px - w + 40), sw - w - 10)        # 贴宠物左上方
        y = max(10, py - h - 8)
        if y < 10:
            y = min(sh - h - 10, py + 60)
        self.win.geometry(f"+{int(x)}+{int(y)}")

    def _start(self):
        routine = self.event.get("routine") or "full"
        cb = self.on_exercise
        self.close()
        if callable(cb):
            cb(routine)

    def close(self):
        if self in HealthCard._open:
            HealthCard._open.remove(self)
        if self._timer:
            try:
                self.win.after_cancel(self._timer)
            except tk.TclError:
                pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------- 宠物窗口
class Pet:
    """全桌面唯一的一只宠物：会话状态 + 占卜覆盖层。"""

    def __init__(self, root, state="idle"):
        self.root = root
        self.state = state          # 会话聚合状态：working/done/idle
        self.frame = 0              # 会话动画帧
        self.cw = W
        self.bubble = None

        # 占卜覆盖层
        self.divine_state = None    # None / "divining"(凝神) / "shaking"(摇签)
        self.divine_mode = None
        self.dframe = 0             # 占卜动画帧
        self._job = None            # {mode, started, result, claude_ready, card}
        self._lock = threading.Lock()

        # 健康关怀联动
        self.health_factors = []    # 当前不健康因素(驱动造型/颜色)
        self.health_severity = "ok"
        self._exercise = None       # 进行中的健身引导会话

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        self.win.configure(bg=KEY)

        self.canvas = tk.Canvas(self.win, width=W, height=H, bg=KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack()

        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = sw - (W + 6)
        y = sh - H - 56
        self.win.geometry(f"{W}x{H}+{max(0,x)}+{max(0,y)}")

        # 交互：点击 vs 拖拽
        self._press_xy = (0, 0)
        self._win_xy = (0, 0)
        self._moved = False
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Button-3>", self._menu)

    # -- 交互 --
    def _press(self, e):
        self._press_xy = (e.x_root, e.y_root)
        self._win_xy = (self.win.winfo_x(), self.win.winfo_y())
        self._moved = False

    def _move(self, e):
        dx = e.x_root - self._press_xy[0]
        dy = e.y_root - self._press_xy[1]
        if abs(dx) > 4 or abs(dy) > 4:
            self._moved = True
            self.win.geometry(f"+{self._win_xy[0] + dx}+{self._win_xy[1] + dy}")

    def _release(self, e):
        if not self._moved and self.divine_state is None:
            self._divine_menu(e.x_root, e.y_root)

    def _divine_menu(self, x, y):
        m = tk.Menu(self.win, tearoff=0)
        m.add_command(label="☯  易经卦象", command=lambda: self.start_divine("iching"))
        m.add_command(label="🎋  诗经摇签", command=lambda: self.start_divine("shijing"))
        m.add_separator()
        m.add_command(label="🤸  起来动一动", command=lambda: self.start_exercise("full"))
        m.add_command(label="🧘  颈肩放松操", command=lambda: self.start_exercise("neck_shoulder"))
        m.add_separator()
        m.add_command(label="⚙  设置", command=self.open_settings)
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def _menu(self, e):
        m = tk.Menu(self.win, tearoff=0)
        m.add_command(label="Claude 宠物 · 占卜", state="disabled")
        m.add_separator()
        m.add_command(label="设置", command=self.open_settings)
        m.add_command(label="关于", command=self._about)
        m.add_command(label="退出", command=lambda: os._exit(0))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _about(self):
        win = tk.Toplevel(self.root)
        win.title("关于")
        win.configure(bg=CARD_BG)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        tk.Label(win, text="Claude 桌宠 · 占卜 ✦", bg=CARD_BG, fg=CARD_INK,
                 font=("Microsoft YaHei", 14, "bold"), padx=24).pack(pady=(18, 4))
        tk.Label(win, text="陪你写代码：工作/完成/空闲三态\n点我占卜：易经卦象 · 诗经摇签\n健康关怀：联动桌前助手，疲劳/久坐/驼背时变色提醒\n建议弹窗(10s) + Ring Fit 风格体操引导\n本地语料库 + Claude 现解读(≤20字) · 2小时锁定",
                 bg=CARD_BG, fg=CARD_SUB, font=("Microsoft YaHei", 10),
                 justify="center", padx=24).pack(pady=(0, 16))
        tk.Button(win, text="好的", command=win.destroy, relief="flat",
                  bg="#EFE3CD", padx=20, pady=4).pack(pady=(0, 16))

    # -- 占卜流程 --
    def start_divine(self, mode, force=False):
        if self.divine_state is not None:
            return
        self.divine_state = "shaking" if mode == "shijing" else "divining"
        self.divine_mode = mode
        self.dframe = 0
        job = {"mode": mode, "started": time.time(),
               "result": None, "claude_ready": False, "card": None}
        with self._lock:
            self._job = job
        threading.Thread(target=self._worker, args=(job, force), daemon=True).start()

    def _worker(self, job, force):
        """后台线程：只算数据，绝不碰 tkinter。"""
        cfg = eng.load_config()
        try:
            result = eng.divine_local(job["mode"], cfg, force=force)
        except Exception:
            result = {"mode": job["mode"], "icon": "🔮", "title": "占卜",
                      "subtitle": "", "sections": [("提示", "语料读取失败，请稍后再试。")],
                      "lucky": {}, "footer": ""}
        with self._lock:
            job["result"] = result

        cached_reading = result.get("claude_reading")
        if cfg.get("use_claude", True) and eng.claude_available():
            if cached_reading:
                # 2h 锁定命中：复用已缓存解读，不再调用 claude(保证一致)
                pass
            else:
                text = eng.enhance_with_claude(result, cfg, timeout=CLAUDE_MAX_MS // 1000)
                if text:
                    with self._lock:
                        job["result"]["claude_reading"] = text
                    eng.cache_put_reading(job["mode"], cfg, text)
            # 诗经签：后台尝试让 claude 生成新签，丰富签库(节流，不阻塞本次结果)
            if job["mode"] == "shijing":
                try:
                    eng.maybe_grow_shijing(cfg)
                except Exception:
                    pass
        with self._lock:
            job["claude_ready"] = True

    def check_job(self):
        """主线程轮询占卜任务：决定何时弹卡 / 补解读 / 收尾。"""
        with self._lock:
            job = self._job
        if not job:
            return
        now = time.time()
        elapsed_ms = (now - job["started"]) * 1000
        ready = job["result"] is not None
        cfg = eng.load_config()
        has_reading = bool(job["result"] and job["result"].get("claude_reading"))
        claude_pending = (cfg.get("use_claude", True) and eng.claude_available()
                          and not job["claude_ready"] and not has_reading)

        if not ready or elapsed_ms < CEREMONY_MS:
            return

        if job["card"] is None:
            if claude_pending and elapsed_ms < CLAUDE_MAX_MS:
                return
            job["card"] = ResultCard(self.root, job["result"], self.start_divine)
            self.divine_state = None       # 回到会话状态动画
            self.divine_mode = None
            return

        if job["claude_ready"]:
            reading = job["result"].get("claude_reading")
            if reading and job["card"]:
                job["card"].set_claude_reading(reading)
            with self._lock:
                self._job = None

    # -- 设置面板 --
    def open_settings(self):
        cfg = eng.load_config()
        win = tk.Toplevel(self.root)
        win.title("Claude 桌宠 · 设置")
        win.configure(bg=CARD_BG)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        PAD = {"padx": 18, "pady": 4}

        use_claude = tk.BooleanVar(value=cfg.get("use_claude", True))
        open_gen = tk.BooleanVar(value=cfg.get("open_generate", True))
        reminder = tk.BooleanVar(value=cfg.get("daily_reminder", False))
        rtime = tk.StringVar(value=cfg.get("reminder_time", "09:00"))
        rmode = tk.StringVar(value=cfg.get("reminder_mode", "shijing"))

        def row(label):
            f = tk.Frame(win, bg=CARD_BG)
            f.pack(fill="x", **PAD)
            tk.Label(f, text=label, bg=CARD_BG, fg=CARD_INK, width=12,
                     anchor="w", font=("Microsoft YaHei", 10)).pack(side="left")
            return f

        tk.Label(win, text="占卜设置", bg=CARD_BG, fg=CARD_INK,
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=(16, 6))
        tk.Label(win, text="玩法：☯ 易经卦象 · 🎋 诗经摇签", bg=CARD_BG, fg=CARD_SUB,
                 font=("Microsoft YaHei", 9)).pack(pady=(0, 4))

        f = row("Claude 增强")
        tk.Checkbutton(f, text="现场生成解读(≤20字)", variable=use_claude, bg=CARD_BG,
                       font=("Microsoft YaHei", 10)).pack(side="left")
        f = row("开放生成")
        tk.Checkbutton(f, text="让 Claude 扩充诗经签库", variable=open_gen, bg=CARD_BG,
                       font=("Microsoft YaHei", 10)).pack(side="left")
        if not eng.claude_available():
            tk.Label(win, text="（未检测到 claude CLI，将仅用本地语料）",
                     bg=CARD_BG, fg=CARD_SUB,
                     font=("Microsoft YaHei", 8)).pack()
        f = row("每日提醒")
        tk.Checkbutton(f, text="每天", variable=reminder, bg=CARD_BG,
                       font=("Microsoft YaHei", 10)).pack(side="left")
        tk.Entry(f, textvariable=rtime, width=6,
                 font=("Microsoft YaHei", 10)).pack(side="left")
        for v, t in (("shijing", "弹诗经签"), ("iching", "弹易经卦")):
            tk.Radiobutton(f, text=t, variable=rmode, value=v, bg=CARD_BG,
                           font=("Microsoft YaHei", 9)).pack(side="left")

        def save():
            cfg.update({
                "use_claude": use_claude.get(),
                "open_generate": open_gen.get(),
                "daily_reminder": reminder.get(),
                "reminder_time": rtime.get().strip(),
                "reminder_mode": rmode.get(),
            })
            eng.save_config(cfg)
            win.destroy()

        tk.Button(win, text="保存", command=save, relief="flat", bg="#C98A4B",
                  fg="white", font=("Microsoft YaHei", 10, "bold"),
                  padx=28, pady=5, cursor="hand2").pack(pady=16)

    # -- 会话状态接口(供 Manager 下发) --
    def set_state(self, state):
        if state != self.state:
            self.state = state
            self.frame = 0

    def set_bubble(self, text):
        self.bubble = text or None

    # -- 健康关怀接口(供 Manager 下发) --
    def set_health(self, factors, severity):
        self.health_factors = list(factors or [])
        self.health_severity = severity or "ok"

    def win_xy(self):
        try:
            return self.win.winfo_x(), self.win.winfo_y()
        except tk.TclError:
            return 0, 0

    def start_exercise(self, routine="full"):
        """居中放大、引导做一套针对性体操(Ring Fit 风格)。"""
        if self._exercise is not None:
            return
        try:
            import linefit_player as exercise   # 线条人(真人骨架)优先
        except Exception:
            try:
                import exercise                 # 回退：旧版块状吉祥物
            except Exception:
                return

        def _done():
            self._exercise = None
        self._exercise = exercise.ExerciseSession(
            self.root, routine=routine or "full", on_done=_done)

    def _set_width(self, width):
        if width == self.cw:
            return
        old = self.cw
        self.cw = width
        try:
            y = self.win.winfo_y()
            x = max(0, self.win.winfo_x() + (old - width))
            self.canvas.config(width=width)
            self.win.geometry(f"{width}x{H}+{x}+{y}")
        except tk.TclError:
            pass

    def _draw_bubble(self, c, text, body_cx):
        tx, ty = 18, 40
        t = c.create_text(tx, ty, text=f"✓ {text} 完成", anchor="w",
                          fill="#2A2A2A", font=("Microsoft YaHei", 10, "bold"))
        x1, y1, x2, y2 = c.bbox(t)
        pad = 8
        c.create_rectangle(x1 - pad, y1 - pad, x2 + pad, y2 + pad,
                           fill="#FFFDF5", outline=GREEN_DK, width=2)
        bx = x2 + pad
        cyt = (y1 + y2) // 2
        c.create_polygon(bx, cyt - 6, bx, cyt + 6, bx + 12, cyt,
                         fill="#FFFDF5", outline=GREEN_DK, width=2)
        c.tag_raise(t)

    # -- 渲染 --
    def tick(self):
        c = self.canvas

        # 占卜覆盖层优先(凝神/摇签)
        if self.divine_state is not None:
            self.dframe += 1
            self._set_width(W)
            c.delete("all")
            if self.divine_state == "shaking":
                draw_shaking(c, self.dframe)
            else:
                draw_divining(c, self.dframe)
            return

        self.frame += 1
        if self.state == "done":
            wide = self.bubble is not None
            self._set_width(DONE_W if wide else W)
            c.delete("all")
            body_cx = (self.cw - 78) if wide else CX
            draw_done(c, self.frame, cx=body_cx)
            if wide:
                self._draw_bubble(c, self.bubble, body_cx)
            return

        # 健康关怀覆盖层：有不健康因素时变色变形(优先于 idle/working)
        if self.health_factors:
            self._set_width(W)
            c.delete("all")
            draw_health(c, self.frame, self.health_factors, self.health_severity)
            return

        soccer = (self.state == "idle"
                  and self.frame * FRAME_MS >= IDLE_SOCCER_SEC * 1000)
        self._set_width(SOCCER_W if soccer else W)
        c.delete("all")
        if soccer:
            draw_soccer(c, self.frame)
        else:
            DRAWERS.get(self.state, draw_idle)(c, self.frame)

    def destroy(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------- 管理器
class Manager:
    def __init__(self, root, resident=False):
        self.root = root
        self.resident = resident
        self.pet = Pet(root, "idle")
        self.last_session_seen = time.time()
        self.ended = set()
        self.work_seen = {}
        self.cwd_map = {}
        self.prev_states = {}
        self.last_done_at = 0.0
        self.last_done_name = None
        self._last_reminded = None
        self._last_health_event = None
        os.makedirs(STATUS_DIR, exist_ok=True)
        eng._ensure_user_dir()

    def _friendly_name(self, sid):
        cwd = self.cwd_map.get(sid)
        if cwd:
            name = os.path.basename(cwd.rstrip("\\/")) or cwd
            return name[:18]
        return sid[:8]

    @staticmethod
    def _remove_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def _read_json(self):
        out = {}
        now = time.time()
        try:
            files = os.listdir(STATUS_DIR)
        except OSError:
            return out
        for fn in files:
            if not fn.endswith(".json"):
                continue
            path = os.path.join(STATUS_DIR, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            sid = data.get("session_id") or fn[:-5]
            status = data.get("status", "idle")
            ts = float(data.get("ts", now))
            if data.get("cwd"):
                self.cwd_map[sid] = data["cwd"]
            if status == "end":
                self.ended.add(sid)
                if now - ts > TRANSCRIPT_LIVE_SEC:
                    self._remove_file(path)
                continue
            if now - ts > DEAD_SEC:
                self._remove_file(path)
                continue
            out[sid] = (status, ts)
        return out

    def _read_transcripts(self):
        out = {}
        now = time.time()
        try:
            projs = os.listdir(PROJECTS_DIR)
        except OSError:
            return out
        for proj in projs:
            if proj == "subagents":
                continue
            pdir = os.path.join(PROJECTS_DIR, proj)
            if not os.path.isdir(pdir):
                continue
            try:
                names = os.listdir(pdir)
            except OSError:
                continue
            for fn in names:
                if not fn.endswith(".jsonl"):
                    continue
                sid = fn[:-6]
                if sid in self.ended:
                    continue
                try:
                    age = now - os.path.getmtime(os.path.join(pdir, fn))
                except OSError:
                    continue
                if age > TRANSCRIPT_LIVE_SEC:
                    continue
                if sid not in out or age < out[sid]:
                    out[sid] = age
        return out

    def compute_states(self):
        now = time.time()
        json_map = self._read_json()
        tr_map = self._read_transcripts()
        out = {}
        for sid in (set(json_map) | set(tr_map)) - self.ended:
            js = json_map.get(sid)
            age = tr_map.get(sid)
            jstatus = js[0] if js else None
            if jstatus == "done" and now - js[1] < DONE_HOLD_SEC:
                self.work_seen.pop(sid, None)
                out[sid] = "done"
                continue
            if age is not None and age < TRANSCRIPT_WORK_SEC:
                self.work_seen[sid] = now
                out[sid] = "working"
                continue
            if sid in self.work_seen and now - self.work_seen[sid] < DONE_INFER_SEC:
                out[sid] = "done"
                continue
            self.work_seen.pop(sid, None)
            if age is None and js:
                st = jstatus
                if st == "working" and now - js[1] > WORK_STALE_SEC:
                    st = "idle"
                out[sid] = "idle" if st == "done" else st
            else:
                out[sid] = "idle"
        return out

    def poll(self):
        try:
            with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
                f.write(str(time.time()))
        except OSError:
            pass

        now = time.time()
        states = self.compute_states()

        for sid, st in states.items():
            if st == "done" and self.prev_states.get(sid) != "done":
                self.last_done_at = now
                self.last_done_name = self._friendly_name(sid)
                done_beep()
        self.prev_states = dict(states)

        if now - self.last_done_at < DONE_HOLD_SEC:
            self.pet.set_state("done")
            self.pet.set_bubble(self.last_done_name)
        elif any(v == "working" for v in states.values()):
            self.pet.set_state("working")
            self.pet.set_bubble(None)
        else:
            self.pet.set_state("idle")
            self.pet.set_bubble(None)

        # 健康关怀联动：读桌前健康助手状态 -> 造型/颜色 + 10s 建议弹窗
        health_active = self._poll_health(now)

        # 健康监控运行时也算"有活动"，宠物不因无 Claude 会话而退出
        if states or health_active:
            self.last_session_seen = now
        elif not self.resident and now - self.last_session_seen > NO_SESSION_EXIT_SEC:
            os._exit(0)

        # 每日提醒(可选)
        cfg = eng.load_config()
        if cfg.get("daily_reminder"):
            self._maybe_remind(cfg)

        self.root.after(POLL_MS, self.poll)

    def _poll_health(self, now):
        """读取健康助手状态：更新宠物造型/颜色，新建议则弹 10s 卡。
        返回 True 表示健康监控正在运行(用于 keep-alive)。"""
        h = read_health()
        if not h:
            self.pet.set_health([], "ok")
            return False
        self.pet.set_health(h.get("factors", []), h.get("severity", "ok"))
        ev = h.get("event")
        if ev and ev.get("id") != self._last_health_event:
            self._last_health_event = ev.get("id")
            # 占卜/健身进行中不打断
            if self.pet.divine_state is None and self.pet._exercise is None:
                try:
                    HealthCard(self.root, ev, self.pet.win_xy(),
                               self.pet.start_exercise)
                except tk.TclError:
                    pass
        return True

    def _maybe_remind(self, cfg):
        import datetime
        today = datetime.date.today().isoformat()
        if self._last_reminded == today:
            return
        try:
            hh, mm = (int(x) for x in cfg.get("reminder_time", "09:00").split(":"))
        except ValueError:
            hh, mm = 9, 0
        now = datetime.datetime.now()
        if (now.hour, now.minute) >= (hh, mm):
            self._last_reminded = today
            if self.pet.divine_state is None:
                self.pet.start_divine(cfg.get("reminder_mode", "shijing"))

    def animate(self):
        try:
            self.pet.tick()
            self.pet.check_job()
        except tk.TclError:
            pass
        self.root.after(FRAME_MS, self.animate)


# ---------------------------------------------------------------- 单例 & 入口
def acquire_singleton():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", SINGLETON_PORT))
        s.listen(1)
        return s
    except OSError:
        return None


def main():
    selftest = "--selftest" in sys.argv
    resident = "--resident" in sys.argv

    guard = acquire_singleton()
    if guard is None and not selftest:
        return

    root = tk.Tk()
    root.withdraw()
    mgr = Manager(root, resident=resident)

    if selftest:
        # 自检：会话三态轮播 + 触发一次占卜(本地库, 强制重抽)
        seq = [("working", None),
               ("done", "claude-pet"),
               ("idle", None)]

        def cycle(k=0):
            st, bubble = seq[k % len(seq)]
            mgr.pet.set_state(st)
            mgr.pet.set_bubble(bubble)
            if k < len(seq) - 1:
                root.after(1100, lambda: cycle(k + 1))
            else:
                root.after(600, lambda: mgr.pet.start_divine("shijing", force=True))
                root.after(9000, root.destroy)
        root.after(400, cycle)
        mgr.animate()
        root.mainloop()
        return

    mgr.animate()
    mgr.poll()
    root.mainloop()


if __name__ == "__main__":
    main()
