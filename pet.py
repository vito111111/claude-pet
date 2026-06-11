# -*- coding: utf-8 -*-
"""
Claude Code 桌面宠物 (manager + 像素渲染器)

一个进程、**全桌面只有一只宠物**：无论开多少个 Claude Code 窗口，都共用这一只。
宠物形象为 Claude Code 的方块像素"火花"小人，状态是所有会话的聚合：

  working : 任意一个会话正在干活 —— 操作键盘打字的动态（橘色像素）
  done    : 任意一个会话刚结束 —— 宠物变绿、轻轻跳动，并**冒泡弹出刚完成的窗口名**，
            播放完成提示音；保持 5 秒后回到 idle/working
  idle    : 所有会话都空闲 —— 橘色小人安静待命、轻轻摇摆
            空闲满 60s 会变出一个分身，本体与分身之间踢足球解闷；一有活立刻收场转 working

聚合规则：
  - 只要有任一会话从"干活"转为"结束"，立即变绿 + 冒泡 + 响铃，持续 5 秒；
  - 5 秒后：若仍有会话在干活 -> working，否则 -> idle。

状态来源：hook_status.py 由 Claude Code 的 hooks 写入 ~/.claude/pet_status/<session>.json
本进程每 500ms 轮询该目录，聚合所有会话状态来驱动这唯一一只宠物。
单例：绑定本地端口，重复启动会自动退出。
"""

import os
import sys
import json
import time
import math
import socket
import tkinter as tk

import threading

try:
    import winsound          # Windows 自带，用于"完成"提示音
except ImportError:
    winsound = None

# 完成提示音：优先项目自定义音 (QQ "咳咳")，其次系统 tada.wav，再不行合成提示音
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
HEARTBEAT_FILE = os.path.join(STATUS_DIR, ".heartbeat")  # 渲染器存活心跳(ensure_pet 据此判断僵死实例)
# 兜底信号源：Claude Code 每追加一条消息/工具结果都会更新会话 transcript 的 mtime。
# hook 不可用时(如会话启动早于 hook 配置、或当前环境根本不跑 settings.json 的 hook)，
# 直接据此推断 working/idle，使空闲/工作状态不再依赖 hook 是否触发。
PROJECTS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects")
SINGLETON_PORT = 50573          # 单例守卫端口
POLL_MS = 500                   # 状态轮询间隔
FRAME_MS = 90                   # 动画帧间隔 (~11fps，像素风慢一点更可爱)
DONE_HOLD_SEC = 5               # done(绿色+冒泡)展示多久后回到 idle/working
DONE_INFER_SEC = 12             # transcript 兜底：工作停止后绿色"完成"维持多久 -> idle
WORK_STALE_SEC = 30 * 60        # working 超过此时长无更新 -> 视为 idle(防卡死)
DEAD_SEC = 12 * 3600            # 状态文件超过此时长 -> 视为死会话
NO_SESSION_EXIT_SEC = 120       # 无任何会话超过此时长 -> 退出进程(随 Claude Code 关闭而退出)
TRANSCRIPT_WORK_SEC = 40        # transcript 在此秒内有更新 -> working(放宽以跨越模型思考间隙)
TRANSCRIPT_LIVE_SEC = 300       # transcript 超过此时长无更新 -> 该会话视为离线，不再显示宠物
IDLE_SOCCER_SEC = 60            # 持续空闲超过此时长 -> 宠物变出分身一起踢足球(有活就立刻收场)

KEY = "#FF00FF"                 # 透明色键 (窗口中此颜色将完全透明)

# 调色板 (body 取自 Claude Code 官方图标 #D77959)
ORANGE      = "#D77959"
ORANGE_HI   = "#E89A7C"
ORANGE_DK   = "#B25C3E"
GREEN       = "#5BB06A"
GREEN_HI    = "#86CF93"
GREEN_DK    = "#3C8A4C"
EYE_DARK    = "#141210"
EYE_WHITE   = "#FFFFFF"
PUPIL       = "#141210"
KB_BODY     = "#3C4043"
KB_BODY_DK  = "#26282B"
KB_KEY      = "#7A8085"
SPARK_DONE  = "#FFD45E"

W, H = 180, 220                 # 画布尺寸(常规单宠物)
SOCCER_W = 360                  # 踢足球时画布加宽，容纳本体+分身+足球
DONE_W = 320                    # 完成冒泡时画布加宽，左侧容纳"完成的窗口"气泡
CX = W // 2                     # 水平中心
CELL = 7                        # 像素块边长
BALL_WHITE = "#FFFFFF"
BALL_DARK  = "#23252A"


# ---------------------------------------------------------------- 像素绘图核心
def px(c, x, y, color, shade=None, cell=CELL):
    """画一个带斜角阴影的像素块（右下变暗，得到方块/体素质感）。"""
    c.create_rectangle(x, y, x + cell, y + cell, fill=color, outline="")
    if shade:
        c.create_rectangle(x, y + cell - 2, x + cell, y + cell,
                           fill=shade, outline="")
        c.create_rectangle(x + cell - 2, y, x + cell, y + cell,
                           fill=shade, outline="")


def blit(c, sprite, ox, oy, palette, shadepal, cell=CELL):
    """把字符串精灵图贴到画布；'.'/' ' 为透明。"""
    for j, row in enumerate(sprite):
        for i, ch in enumerate(row):
            if ch in " .":
                continue
            col = palette.get(ch)
            if col is None:
                continue
            px(c, ox + i * cell, oy + j * cell, col, shadepal.get(ch), cell)


# Claude Code 官方图标小人 (16x10)：扁圆身体 + 一对深色眼睛 + 腰间小凸起 + 4 条小腿
# O=身体 E=眼睛
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
# 不含腿的上半身 (working 时腿要单独做敲击动画)
BODY_TOP = BODY[:8]
BODY_W = len(BODY[0]) * CELL     # 112
BODY_H = len(BODY) * CELL        # 70
LEG_COLS = (3, 5, 10, 12)        # 4 条腿所在列

# 像素键盘 (15 宽)，B=外壳 k=键帽
KEYBOARD = [
    "BBBBBBBBBBBBBBB",
    "BkBkBkBkBkBkBkB",
    "BBBBBBBBBBBBBBB",
    "BkkBkkkkkkBkkBB",
    "BBBBBBBBBBBBBBB",
]


def _origin(cx, cy):
    """身体精灵左上角像素坐标。"""
    return cx - BODY_W // 2, cy - BODY_H // 2


def _draw_body(c, cx, cy, main, hi, dark, sprite=BODY):
    ox, oy = _origin(cx, cy)
    pal = {"O": main, "H": hi, "E": EYE_DARK}
    # 官方图标是纯平色块 -> 身体不加斜角阴影，保持扁平干净
    blit(c, sprite, ox, oy, pal, {})
    return ox, oy


def _eye_centers(cx, cy):
    """两只眼睛的中心像素坐标 (列 4 / 列 11，行 2-3)。"""
    ox, oy = _origin(cx, cy)
    ey = oy + 3 * CELL
    return (ox + 4 * CELL + CELL // 2, ey), (ox + 11 * CELL + CELL // 2, ey)


def _legs(c, cx, cy, frame, main, hi, dark):
    """working 时：4 条小腿交替敲击。"""
    ox, oy = _origin(cx, cy)
    legtop = oy + 8 * CELL                      # 身体底部
    for i, col in enumerate(LEG_COLS):
        lx = ox + col * CELL
        lifted = (i % 2 + frame) % 2            # 0/2 与 1/3 反相交替
        foot_y = legtop + (10 if lifted else 20)
        c.create_rectangle(lx, legtop, lx + CELL - 1, foot_y,
                           fill=main, outline="")
        px(c, lx - 1, foot_y - CELL, hi, main)  # 脚
    return legtop


def _sparkle_eyes(c, cx, cy):
    """done 时在眼睛上叠一点高光，显得开心有神。"""
    for (ex, ey) in _eye_centers(cx, cy):
        c.create_rectangle(ex - 1, ey - 6, ex + 4, ey + 2,
                           fill=EYE_WHITE, outline="")
        c.create_rectangle(ex, ey - 4, ex + 3, ey + 1,
                           fill=EYE_DARK, outline="")


# ------------------------------------------------ 三种状态各自的整帧绘制
def draw_working(c, frame):
    bob = -2 if (frame // 2) % 2 == 0 else 0
    cy = 78 + bob

    # 腿先画(敲击)，键盘其后，身体最后盖住腿根
    legtop = _legs(c, CX, cy, frame, ORANGE, ORANGE_HI, ORANGE_DK)

    kb_w = len(KEYBOARD[0]) * CELL
    blit(c, KEYBOARD, CX - kb_w // 2, legtop + 18,
         {"B": KB_BODY, "k": KB_KEY}, {"B": KB_BODY_DK, "k": "#5A6065"})

    _draw_body(c, CX, cy, ORANGE, ORANGE_HI, ORANGE_DK, sprite=BODY_TOP)

    # 飘动的代码符号
    syms = ["</>", "{}", "*", ";"]
    s = syms[(frame // 4) % len(syms)]
    c.create_text(CX + 60, cy - 22 - (frame % 8), text=s, fill=ORANGE_DK,
                  font=("Consolas", 11, "bold"))


def draw_done(c, frame, cx=CX):
    pulse = abs(math.sin(frame * 0.18))
    cy = 92 - int(pulse * 8)
    _draw_body(c, cx, cy, GREEN, GREEN_HI, GREEN_DK)
    _sparkle_eyes(c, cx, cy)

    # ✓ 像素对勾徽章
    bx, by = cx + 44, cy - 30
    c.create_rectangle(bx - 11, by - 11, bx + 11, by + 11,
                       fill="#FFFFFF", outline=GREEN_DK, width=2)
    for dx, dy in ((-5, 0), (-2, 3), (1, 0), (4, -3), (7, -6)):
        c.create_rectangle(bx + dx, by + dy, bx + dx + 4, by + dy + 4,
                           fill=GREEN_DK, outline="")
    # 闪烁星点
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

    # 宠物 (橘色，安静待命、轻轻摇摆)
    _draw_body(c, cx, cy, ORANGE, ORANGE_HI, ORANGE_DK)
    # 偶尔冒出的 "z" 表示打盹
    if (frame % 60) < 30:
        c.create_text(cx + 46, cy - 22 - (frame % 30) // 3, text="z",
                      fill=ORANGE_DK,
                      font=("Segoe UI", 9 + ((frame // 6) % 3), "italic"))


# ------------------------------------------------ idle 满 60s：本体 + 分身踢足球
SOC_CY = 112                    # 两只宠物的身体中心 y
SOC_GROUND = SOC_CY + 52        # 地面/落脚线
SOC_BALL_R = 9                  # 足球半径
SOC_PERIOD = 26                 # 球从一侧飞到另一侧的帧数 (90ms*26≈2.3s)


def _soccer_player(c, cx, facing, kick):
    """画一只踢球的宠物：facing=+1 朝右 / -1 朝左；kick 时前腿向球方向蹬出、身体前倾。"""
    lean = facing * 3 if kick else 0
    pcx = cx + lean
    _draw_body(c, pcx, SOC_CY, ORANGE, ORANGE_HI, ORANGE_DK, sprite=BODY_TOP)
    ox, oy = _origin(pcx, SOC_CY)
    legtop = oy + 8 * CELL
    for i, col in enumerate(LEG_COLS):
        lx = ox + col * CELL
        front = (i >= 2) if facing > 0 else (i < 2)   # 朝向那一侧的两条腿为"前腿"
        if kick and front:
            # 前腿水平蹬出（踢球动作）
            kx = lx + facing * 12
            c.create_rectangle(min(lx, kx), legtop, max(lx, kx) + CELL - 1,
                               legtop + CELL - 1, fill=ORANGE, outline="")
            px(c, kx, legtop, ORANGE_HI, ORANGE)
        else:
            foot = legtop + (12 if i % 2 else 18)
            c.create_rectangle(lx, legtop, lx + CELL - 1, foot,
                               fill=ORANGE, outline="")
            px(c, lx - 1, foot - CELL, ORANGE_HI, ORANGE)


def _soccer_ball(c, bx, by, frame):
    """白色像素足球，黑点随飞行旋转。"""
    bx, by, r = int(bx), int(by), SOC_BALL_R
    c.create_oval(bx - r, by - r, bx + r, by + r,
                  fill=BALL_WHITE, outline=BALL_DARK, width=2)
    rot = frame * 0.45
    for k in range(5):
        a = rot + k * 2 * math.pi / 5
        sx = bx + int(math.cos(a) * 4)
        sy = by + int(math.sin(a) * 4)
        c.create_rectangle(sx - 2, sy - 2, sx + 2, sy + 2,
                           fill=BALL_DARK, outline="")


def draw_soccer(c, frame):
    """空闲满 60s：左边本体、右边分身，足球在两者之间来回弹射。"""
    lcx, rcx = 96, SOCCER_W - 96          # 96 与 264
    lkx, rkx = lcx + 46, rcx - 46         # 两侧的踢球点

    phase = frame % (2 * SOC_PERIOD)
    if phase < SOC_PERIOD:                # 球：左 -> 右
        t = phase / SOC_PERIOD
        bx = lkx + (rkx - lkx) * t
        left_kick, right_kick = t < 0.15, t > 0.85
    else:                                 # 球：右 -> 左
        t = (phase - SOC_PERIOD) / SOC_PERIOD
        bx = rkx - (rkx - lkx) * t
        right_kick, left_kick = t < 0.15, t > 0.85
    by = SOC_GROUND - int(math.sin(t * math.pi) * 72)   # 抛物线弧顶

    _soccer_player(c, lcx, +1, left_kick)
    _soccer_player(c, rcx, -1, right_kick)
    _soccer_ball(c, bx, by, frame)

    # 分身刚出现的头 ~1.8s 标注一下"分身!"
    if frame < 20:
        c.create_text(rcx, SOC_CY - 56, text="分身!", fill=ORANGE_DK,
                      font=("Microsoft YaHei", 9, "bold"))


DRAWERS = {"working": draw_working, "done": draw_done, "idle": draw_idle}


# ---------------------------------------------------------------- 宠物窗口
class Pet:
    """全桌面唯一的一只宠物。状态由 Manager 聚合所有会话后下发。"""

    def __init__(self, root, state="idle"):
        self.state = state
        self.frame = 0
        self.cw = W                # 当前画布宽度
        self.bubble = None         # done 时冒泡显示的"完成的窗口"名(None 则不冒泡)

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

        # 初始位置：屏幕右下角
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        x = sw - (W + 6)
        y = sh - H - 56
        self.win.geometry(f"{W}x{H}+{max(0,x)}+{max(0,y)}")

        # 交互：左键拖动，右键菜单
        self._drag = (0, 0)
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<Button-3>", self._menu)

        self.menu = tk.Menu(self.win, tearoff=0)
        self.menu.add_command(label="Claude 宠物", state="disabled")
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=lambda: os._exit(0))

    def _press(self, e):
        self._drag = (e.x_root - self.win.winfo_x(),
                      e.y_root - self.win.winfo_y())

    def _move(self, e):
        self.win.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def _menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def set_state(self, state):
        if state != self.state:
            self.state = state
            self.frame = 0

    def set_bubble(self, text):
        self.bubble = text or None

    def _set_width(self, width):
        """改变窗口/画布宽度，并保持右边缘不动(宠物常在屏幕右下角)。"""
        if width == self.cw:
            return
        old = self.cw
        self.cw = width
        try:
            y = self.win.winfo_y()
            x = max(0, self.win.winfo_x() + (old - width))   # 右边缘固定
            self.canvas.config(width=width)
            self.win.geometry(f"{width}x{H}+{x}+{y}")
        except tk.TclError:
            pass

    def _draw_bubble(self, c, text, body_cx):
        """在身体左侧画一个语音气泡，写上刚完成的窗口名。"""
        tx, ty = 18, 40
        t = c.create_text(tx, ty, text=f"✓ {text} 完成", anchor="w",
                          fill="#2A2A2A", font=("Microsoft YaHei", 10, "bold"))
        x1, y1, x2, y2 = c.bbox(t)
        pad = 8
        c.create_rectangle(x1 - pad, y1 - pad, x2 + pad, y2 + pad,
                           fill="#FFFDF5", outline=GREEN_DK, width=2)
        # 指向身体的小尾巴
        bx = x2 + pad
        cyt = (y1 + y2) // 2
        c.create_polygon(bx, cyt - 6, bx, cyt + 6, bx + 12, cyt,
                         fill="#FFFDF5", outline=GREEN_DK, width=2)
        c.tag_raise(t)

    def tick(self):
        self.frame += 1
        c = self.canvas

        if self.state == "done":
            wide = self.bubble is not None
            self._set_width(DONE_W if wide else W)
            c.delete("all")
            body_cx = (self.cw - 78) if wide else CX
            draw_done(c, self.frame, cx=body_cx)
            if wide:
                self._draw_bubble(c, self.bubble, body_cx)
            return

        # 空闲满 IDLE_SOCCER_SEC -> 进入踢足球(本体+分身)；一旦切到 working/done 立刻收场
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
        self.resident = resident        # 由 hook/开机自启以分离方式拉起的标记(行为不再据此分叉)
        self.pet = Pet(root, "idle")    # 全桌面唯一一只宠物
        self.last_session_seen = time.time()
        self.ended = set()              # 已收到 SessionEnd 的会话(墓碑)，不再被 transcript 复活
        self.work_seen = {}             # session_id -> 最近一次据 transcript 判定为 working 的时刻
        self.cwd_map = {}               # session_id -> cwd(用于冒泡显示"完成的窗口"名)
        self.prev_states = {}           # 上一轮各会话状态(用于边沿检测"刚完成")
        self.last_done_at = 0.0         # 最近一次有会话完成的时刻
        self.last_done_name = None      # 最近完成的窗口名
        os.makedirs(STATUS_DIR, exist_ok=True)

    def _friendly_name(self, sid):
        """会话 -> 人类可读的"窗口名"，优先取工作目录最后一段。"""
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
        """读取 hook 写入的状态文件 -> {session_id: (status, ts)}。

        status=='end' 视为墓碑：登记到 self.ended(令 transcript 兜底不再复活该会话)，
        并在 transcript 必定离线后(TRANSCRIPT_LIVE_SEC)清理墓碑文件——保留这段时间是为了
        即便渲染器在会话结束后才重启，也不会因 transcript mtime 仍新鲜而把宠物又拉回来。"""
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
        """扫描各会话 transcript 的 mtime -> {session_id: age_seconds}。

        ~/.claude/projects/<proj>/<session_id>.jsonl 在 Claude Code 每追加一条
        消息/工具结果时刷新 mtime。超过 TRANSCRIPT_LIVE_SEC 无更新即认为离线(不返回)。
        排除 subagents 目录(子代理 transcript 不是真实会话)与已结束(墓碑)的会话。"""
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
        """融合 hook 状态(json)与 transcript 活跃度，得到 {session_id: state}。

        两条信号互补：json 是 hook 显式写入(done 含提示音、end 是墓碑)，权威但漏触发就会卡死；
        transcript mtime 始终反映真实活动。规则：
          - 显式 done(且新鲜) -> done，让 Stop hook 的绿色庆祝优先；
          - transcript 新鲜(<WORK) -> working；
          - 曾在干活、刚安静下来(<DONE_INFER) -> done —— 兜底「Stop hook 没触发时也变绿」；
          - 否则 idle(无 transcript 时回退到 json，working 卡死超时也转 idle)。"""
        now = time.time()
        json_map = self._read_json()        # {sid: (status, ts)}
        tr_map = self._read_transcripts()   # {sid: age}
        out = {}
        for sid in (set(json_map) | set(tr_map)) - self.ended:
            js = json_map.get(sid)          # (status, ts) 或 None
            age = tr_map.get(sid)           # float 或 None
            jstatus = js[0] if js else None

            # 1) Stop hook 显式 done(新鲜) -> 立即变绿(并触发提示音)
            if jstatus == "done" and now - js[1] < DONE_HOLD_SEC:
                self.work_seen.pop(sid, None)
                out[sid] = "done"
                continue
            # 2) transcript 新鲜 -> 正在干活
            if age is not None and age < TRANSCRIPT_WORK_SEC:
                self.work_seen[sid] = now
                out[sid] = "working"
                continue
            # 3) 兜底：刚从干活安静下来 -> 维持一小段绿色"完成"(覆盖 Stop hook 漏触发)
            if sid in self.work_seen and now - self.work_seen[sid] < DONE_INFER_SEC:
                out[sid] = "done"
                continue
            self.work_seen.pop(sid, None)
            # 4) 无 transcript 时回退到 json：working 卡死超时转 idle，done 已在上面处理
            if age is None and js:
                st = jstatus
                if st == "working" and now - js[1] > WORK_STALE_SEC:
                    st = "idle"
                out[sid] = "idle" if st == "done" else st
            else:
                out[sid] = "idle"
        return out

    def poll(self):
        # 写存活心跳：渲染器只要还在跑 poll，就持续刷新此文件的时间戳；
        # ensure_pet 启动器据此识别"进程在但窗口僵死/卡住"的实例并替换。
        try:
            with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
                f.write(str(time.time()))
        except OSError:
            pass

        now = time.time()
        states = self.compute_states()   # {session_id: state}

        # 边沿检测：任一会话从"非完成"变为"完成" -> 触发一次"变绿+冒泡+响铃"
        for sid, st in states.items():
            if st == "done" and self.prev_states.get(sid) != "done":
                self.last_done_at = now
                self.last_done_name = self._friendly_name(sid)
                done_beep()
        self.prev_states = dict(states)

        # 聚合成唯一宠物的状态：
        #   - 最近 DONE_HOLD_SEC 秒内有会话完成 -> done(绿+冒泡)
        #   - 否则有会话在干活 -> working
        #   - 否则 idle
        if now - self.last_done_at < DONE_HOLD_SEC:
            self.pet.set_state("done")
            self.pet.set_bubble(self.last_done_name)
        elif any(v == "working" for v in states.values()):
            self.pet.set_state("working")
            self.pet.set_bubble(None)
        else:
            self.pet.set_state("idle")
            self.pet.set_bubble(None)

        # 无任何会话超过 NO_SESSION_EXIT_SEC -> 退出进程(随 Claude Code 全部关闭而退出)
        if states:
            self.last_session_seen = now
        elif not self.resident and now - self.last_session_seen > NO_SESSION_EXIT_SEC:
            os._exit(0)

        self.root.after(POLL_MS, self.poll)

    def animate(self):
        try:
            self.pet.tick()
        except tk.TclError:
            pass
        self.root.after(FRAME_MS, self.animate)


# ---------------------------------------------------------------- 单例 & 入口
def acquire_singleton():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", SINGLETON_PORT))
        s.listen(1)
        return s            # 持有 socket 直到进程退出
    except OSError:
        return None


def main():
    selftest = "--selftest" in sys.argv
    resident = "--resident" in sys.argv   # 开机自启常驻模式

    guard = acquire_singleton()
    if guard is None and not selftest:
        return              # 已有实例在运行

    root = tk.Tk()
    root.withdraw()         # 隐藏根窗口

    mgr = Manager(root, resident=resident)

    if selftest:
        # 自检：唯一一只宠物循环切换 working -> done(带冒泡) -> idle，数秒后退出
        seq = [("working", None),
               ("done", "claude-pet"),
               ("idle", None),
               ("working", None),
               ("done", "抗体发现知识库"),
               ("idle", None)]

        def cycle(k=0):
            st, bubble = seq[k % len(seq)]
            mgr.pet.set_state(st)
            mgr.pet.set_bubble(bubble)
            if k < len(seq) - 1:
                root.after(1200, lambda: cycle(k + 1))
            else:
                root.after(800, root.destroy)
        root.after(400, cycle)
        mgr.animate()
        root.mainloop()
        return

    mgr.animate()
    mgr.poll()
    root.mainloop()


if __name__ == "__main__":
    main()
