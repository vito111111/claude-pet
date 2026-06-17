# -*- coding: utf-8 -*-
"""桌面健身引导窗口（Ring Fit Adventure 风格）。

被宠物在"久坐/驼背/压力"建议被确认后调用：宠物在桌面居中放大，
带着用户跟练一套针对性体操，逐节计数、给出"用力捏"挤压提示与鼓励。
动作参照 Switch《健身环大冒险》自订训练动作（深蹲 / 過頭推舉 / 側彎 /
扭動 / 立木 / 晨式 / 俯身划船 / 深呼吸）。纯本地动画，不联网、无大模型。
"""
import math
import time
import tkinter as tk

# 与宠物一致的橘色调色板
O, OHI, ODK = "#D77959", "#E89A7C", "#B25C3E"
RING = "#3FB5A6"          # 健身环青色
RING_DK = "#2A8A7E"
BG = "#10131C"            # 深色运动背景
CARD = "#1B2030"
INK = "#EAF0FF"
SUB = "#9AA6C2"
ACCENT = "#FF7A59"
GO = "#5BB06A"


def _M(cn, en, kind, period, tip, reps=None, hold=None):
    return {"cn": cn, "en": en, "kind": kind, "period": period,
            "tip": tip, "reps": reps, "hold": hold}


# 三套针对性训练
ROUTINES = {
    # 久坐起身：全身唤醒
    "full": [
        _M("深蹲", "Squat", "squat", 2.2, "像坐下椅子一样下蹲，膝盖别超过脚尖", reps=8),
        _M("高舉雙臂推入", "Overhead Press", "press", 1.8, "双臂用力向上推举，顶端停一下", reps=10),
        _M("高舉雙臂側彎", "Overhead Side Bend", "sidebend", 2.4, "双臂上举，向左右侧弯拉伸腰侧", reps=8),
        _M("高舉雙臂扭動", "Overhead Twist", "twist", 2.2, "双臂上举，转动上半身扭一扭", reps=8),
        _M("立木姿勢", "Tree Pose", "tree", 2.0, "单脚站立、双手上举合十，保持平衡", hold=14),
        _M("高舉雙臂晨式", "Morning Stretch", "morning", 3.0, "缓慢深长地向上伸展，舒展全身", reps=5),
    ],
    # 坐姿/驼背：颈肩脊柱
    "neck_shoulder": [
        _M("高舉雙臂晨式", "Morning Stretch", "morning", 3.0, "缓慢向上伸展，放松僵硬的肩颈", reps=5),
        _M("高舉雙臂側彎", "Side Bend", "sidebend", 2.4, "向左右侧弯，拉开腰侧与肩背", reps=8),
        _M("俯身划船", "Bent Row", "row", 1.8, "俯身、双臂向后划，挤压肩胛骨", reps=10),
    ],
    # 压力：呼吸放松
    "breathe": [
        _M("高舉雙臂晨式", "Morning Stretch", "morning", 3.4, "吸气抬臂、呼气放下", reps=4),
        _M("深呼吸放鬆", "Deep Breathing", "breathe", 4.0, "鼻子深吸、缓缓呼出，放松神经", hold=18),
    ],
}

ENCOURAGE = ["保持节奏～", "做得很好！", "再坚持一下", "感受肌肉发力", "呼吸别憋住",
             "稳住核心", "棒极了 👏", "就是这样！"]


def _dur(m):
    return (m["reps"] * m["period"]) if m["reps"] else m["hold"]


class ExerciseSession:
    MC_W, MC_H = 360, 300       # 吉祥物画布

    def __init__(self, root, routine="full", on_done=None):
        self.root = root
        self.moves = ROUTINES.get(routine, ROUTINES["full"])
        self.on_done = on_done
        self.idx = 0
        self.t0 = time.time()
        self.move_t0 = self.t0
        self.finished = False
        self.fin_t0 = None
        self._after = None

        self.win = tk.Toplevel(root)
        self.win.title("健身引导")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=BG)
        self._build()
        self._center()
        self._loop()

    # ---------------- UI ----------------
    def _build(self):
        pad = 18
        wrap = tk.Frame(self.win, bg=BG)
        wrap.pack(fill="both", expand=True, padx=2, pady=2)

        head = tk.Frame(wrap, bg=BG)
        head.pack(fill="x", padx=pad, pady=(pad, 4))
        tk.Label(head, text="💪 起身动一动 · 跟我一起做", bg=BG, fg=INK,
                 font=("Microsoft YaHei", 15, "bold")).pack(side="left")
        tk.Button(head, text="✕ 结束", command=self.close, relief="flat",
                  bg=CARD, fg=SUB, activebackground="#332030", bd=0,
                  font=("Microsoft YaHei", 9), padx=10, pady=3,
                  cursor="hand2").pack(side="right")

        self.lbl_move = tk.Label(wrap, text="", bg=BG, fg=ACCENT,
                                 font=("Microsoft YaHei", 22, "bold"))
        self.lbl_move.pack(pady=(2, 0))
        self.lbl_step = tk.Label(wrap, text="", bg=BG, fg=SUB,
                                 font=("Microsoft YaHei", 10))
        self.lbl_step.pack()

        self.mc = tk.Canvas(wrap, width=self.MC_W, height=self.MC_H, bg=CARD,
                            highlightthickness=0, bd=0)
        self.mc.pack(pady=10, padx=pad)

        self.lbl_count = tk.Label(wrap, text="", bg=BG, fg=INK,
                                  font=("Consolas", 26, "bold"))
        self.lbl_count.pack()
        self.lbl_tip = tk.Label(wrap, text="", bg=BG, fg=SUB, wraplength=320,
                                justify="center", font=("Microsoft YaHei", 11))
        self.lbl_tip.pack(pady=(2, 8))

        # 总进度条
        self.bar = tk.Canvas(wrap, width=self.MC_W, height=8, bg=CARD,
                             highlightthickness=0, bd=0)
        self.bar.pack(padx=pad)
        self.lbl_enc = tk.Label(wrap, text="", bg=BG, fg=GO,
                                font=("Microsoft YaHei", 11, "bold"))
        self.lbl_enc.pack(pady=(6, 0))

        btns = tk.Frame(wrap, bg=BG)
        btns.pack(pady=(6, pad))
        tk.Button(btns, text="跳过这节 ⏭", command=self._skip, relief="flat",
                  bg=CARD, fg=INK, activebackground="#2A3142", bd=0,
                  font=("Microsoft YaHei", 10), padx=16, pady=6,
                  cursor="hand2").pack(side="left", padx=6)
        tk.Button(btns, text="完成收工 ✓", command=self._finish, relief="flat",
                  bg=GO, fg="white", activebackground="#3C8A4C",
                  bd=0, font=("Microsoft YaHei", 10, "bold"), padx=16, pady=6,
                  cursor="hand2").pack(side="left", padx=6)

        self._enc_i = 0

    def _center(self):
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"+{(sw - w) // 2}+{max(20, (sh - h) // 2 - 30)}")

    # ---------------- 动作姿态 ----------------
    def _pose(self, move, tt):
        P = move["period"]
        ph = (tt % P) / P
        s = math.sin(ph * math.pi)                 # 单次 0→1→0
        dir_ = 1 if int(tt / P) % 2 == 0 else -1    # 左右交替
        p = {"armL": -68, "armR": -68, "lean": 0, "head": 0,
             "squat": 0.0, "forward": 0.0, "leg": 0, "breath": 0,
             "squeeze": False}
        k = move["kind"]
        if k == "squat":
            p["squat"] = s
            p["armL"] = p["armR"] = 8
            p["squeeze"] = s > 0.7
        elif k == "press":
            p["armL"] = p["armR"] = 35 + 55 * s
            p["squeeze"] = s > 0.75
        elif k == "sidebend":
            p["armL"] = p["armR"] = 92
            p["lean"] = int(26 * dir_ * s)
            p["head"] = int(8 * dir_ * s)
        elif k == "twist":
            p["armL"] = 92 - 14 * dir_ * s
            p["armR"] = 92 + 14 * dir_ * s
            p["head"] = int(16 * dir_ * s)
        elif k == "tree":
            sway = math.sin(tt * math.pi / P)
            p["armL"] = p["armR"] = 96
            p["lean"] = int(4 * sway)
            p["leg"] = 1
        elif k == "morning":
            u = (1 - math.cos(ph * 2 * math.pi)) / 2   # 0→1→0 平滑
            p["armL"] = p["armR"] = 25 + 65 * u
            p["breath"] = int(6 * u)
        elif k == "row":
            p["forward"] = 0.6
            p["armL"] = p["armR"] = -18 - 34 * s
            p["squeeze"] = s > 0.6
        elif k == "breathe":
            u = (1 - math.cos(ph * 2 * math.pi)) / 2
            p["armL"] = p["armR"] = 18 + 42 * u
            p["breath"] = int(9 * u)
            p["inhale"] = ph < 0.5
        return p

    def _arm(self, sx, sy, ang, side, color=O):
        a = math.radians(ang)
        ex = sx + side * math.cos(a) * 66
        ey = sy - math.sin(a) * 66
        self.mc.create_line(sx, sy, ex, ey, fill=color, width=18,
                            capstyle="round")
        self.mc.create_oval(ex - 11, ey - 11, ex + 11, ey + 11,
                            fill=OHI, outline="")
        return ex, ey

    def _draw_mascot(self, move, tt):
        c = self.mc
        c.delete("all")
        W, H = self.MC_W, self.MC_H
        pose = self._pose(move, tt)
        bw, bh = 116, 96
        cx0, cy0 = W // 2, H // 2 - 6
        lower = pose["squat"] * 44
        bx = cx0 + pose["lean"]
        by0 = cy0 - bh // 2 + int(lower) - pose["breath"]
        ground = cy0 + bh // 2 + 70
        tilt = int(pose["forward"] * 26)

        # 腿
        hipL, hipR = bx - 26, bx + 26
        hipY = by0 + bh
        if pose["leg"]:   # 立木：单脚站立
            c.create_line(hipR, hipY, hipR, ground, fill=O, width=22, capstyle="round")
            c.create_line(hipL, hipY, bx - 2, hipY + 26, fill=O, width=20, capstyle="round")
            c.create_line(bx - 2, hipY + 26, hipR - 8, hipY + 12, fill=O, width=20, capstyle="round")
        elif pose["squat"] > 0.02:   # 深蹲：屈膝外展
            kneeOut = int(20 * pose["squat"])
            kneeY = (hipY + ground) // 2 + int(6 * pose["squat"])
            for hip, kx in ((hipL, -kneeOut), (hipR, kneeOut)):
                knee = (hip + kx, kneeY)
                c.create_line(hip, hipY, *knee, fill=O, width=22, capstyle="round")
                c.create_line(*knee, hip, ground, fill=O, width=22, capstyle="round")
        else:
            c.create_line(hipL, hipY, hipL, ground, fill=O, width=22, capstyle="round")
            c.create_line(hipR, hipY, hipR, ground, fill=O, width=22, capstyle="round")

        # 身体
        sx_l, sx_r = bx - bw // 2 + 10, bx + bw // 2 - 10
        sy = by0 + 30
        self._arm(sx_l, sy, pose["armL"], -1)
        hand_r = self._arm(sx_r, sy, pose["armR"], +1)
        if pose.get("leg"):   # 双手合十：右手向中间靠
            pass
        body = [bx - bw // 2 + tilt, by0, bx + bw // 2 + tilt, by0,
                bx + bw // 2, by0 + bh, bx - bw // 2, by0 + bh]
        c.create_polygon(body, fill=O, outline=ODK, width=4, smooth=False)
        # 眼睛 + 笑脸
        ey = by0 + 30
        for dx in (-24, 24):
            ex = bx + dx + pose["head"] + tilt
            c.create_oval(ex - 11, ey - 11, ex + 11, ey + 11, fill="white", outline="")
            c.create_oval(ex - 5, ey - 4, ex + 5, ey + 6, fill="#141210", outline="")
        mxc = bx + pose["head"] + tilt
        c.create_arc(mxc - 18, ey + 8, mxc + 18, ey + 34, start=200, extent=140,
                     style="arc", outline=ODK, width=4)

        # 健身环道具(过头推举/侧弯/扭动时握在手上)
        if move["kind"] in ("press", "sidebend", "twist", "morning"):
            rx, ry = bx + tilt, by0 - int(pose["armL"] > 60) * 40 - 6
            if pose["armL"] > 60:
                c.create_oval(rx - 26, ry - 26, rx + 26, ry + 26,
                              outline=RING, width=7)

        # 挤压提示
        if pose["squeeze"]:
            c.create_text(bx + 70, by0 + 10, text="用力捏!", fill=ACCENT,
                          font=("Microsoft YaHei", 13, "bold"))
        if move["kind"] == "breathe":
            c.create_text(bx, by0 - 26, text="吸气…" if pose.get("inhale") else "呼气…",
                          fill=RING, font=("Microsoft YaHei", 13, "bold"))

    def _draw_finish(self, tt):
        c = self.mc
        c.delete("all")
        W, H = self.MC_W, self.MC_H
        bx, by0 = W // 2, H // 2 - 30
        jump = int(abs(math.sin(tt * 4)) * 10)
        by0 -= jump
        # 欢呼：双臂高举
        self._arm(bx - 48, by0 + 30, 100, -1)
        self._arm(bx + 48, by0 + 30, 100, +1)
        c.create_line(bx - 26, by0 + 96, bx - 26, by0 + 150, fill=O, width=22, capstyle="round")
        c.create_line(bx + 26, by0 + 96, bx + 26, by0 + 150, fill=O, width=22, capstyle="round")
        c.create_polygon(bx - 58, by0, bx + 58, by0, bx + 58, by0 + 96, bx - 58, by0 + 96,
                         fill="#5BB06A", outline="#3C8A4C", width=4)
        ey = by0 + 30
        for dx in (-24, 24):
            c.create_oval(bx + dx - 6, ey - 9, bx + dx + 5, ey + 2, fill="white", outline="")
            c.create_oval(bx + dx - 3, ey - 6, bx + dx + 3, ey + 1, fill="#141210", outline="")
        for i, (sx, sy) in enumerate(((-78, -10), (80, 8), (-70, 40), (74, 44))):
            if (int(tt * 6) + i) % 2 == 0:
                c.create_text(bx + sx, by0 + sy, text="✦", fill="#FFD45E",
                              font=("Segoe UI", 14, "bold"))

    # ---------------- 主循环 ----------------
    def _loop(self):
        if not self.win.winfo_exists():
            return
        now = time.time()
        try:
            if self.finished:
                self._draw_finish(now - self.fin_t0)
                if now - self.fin_t0 > 2.6:
                    self.close()
                    return
            else:
                move = self.moves[self.idx]
                tt = now - self.move_t0
                dur = _dur(move)
                if tt >= dur:
                    self.idx += 1
                    if self.idx >= len(self.moves):
                        self._finish()
                        self._after = self.win.after(33, self._loop)
                        return
                    self.move_t0 = now
                    self._enc_i = (self._enc_i + 1) % len(ENCOURAGE)
                    move = self.moves[self.idx]
                    tt = 0.0
                    dur = _dur(move)
                self._draw_mascot(move, tt)
                self._update_text(move, tt, dur, now)
        except tk.TclError:
            return
        self._after = self.win.after(33, self._loop)

    def _update_text(self, move, tt, dur, now):
        self.lbl_move.config(text=f"{move['cn']}")
        self.lbl_step.config(text=f"第 {self.idx + 1}/{len(self.moves)} 节 · {move['en']}")
        self.lbl_tip.config(text=move["tip"])
        if move["reps"]:
            done = min(move["reps"], int(tt / move["period"]) + 1)
            self.lbl_count.config(text=f"× {done} / {move['reps']}")
        else:
            self.lbl_count.config(text=f"{max(0, int(dur - tt))}s")
        self.lbl_enc.config(text=ENCOURAGE[self._enc_i])
        # 总进度
        total = sum(_dur(m) for m in self.moves)
        elapsed = sum(_dur(m) for m in self.moves[:self.idx]) + min(tt, dur)
        frac = max(0.0, min(1.0, elapsed / total)) if total else 1.0
        self.bar.delete("all")
        self.bar.create_rectangle(0, 0, self.MC_W, 8, fill=CARD, outline="")
        self.bar.create_rectangle(0, 0, int(self.MC_W * frac), 8, fill=ACCENT, outline="")

    # ---------------- 控制 ----------------
    def _skip(self):
        self.idx += 1
        if self.idx >= len(self.moves):
            self._finish()
        else:
            self.move_t0 = time.time()
            self._enc_i = (self._enc_i + 1) % len(ENCOURAGE)

    def _finish(self):
        if self.finished:
            return
        self.finished = True
        self.fin_t0 = time.time()
        try:
            self.lbl_move.config(text="完成！很棒 👏")
            self.lbl_step.config(text="活动开了吧，回去继续加油～")
            self.lbl_count.config(text="✓")
            self.lbl_tip.config(text="规律起身活动，颈肩腰背都会感谢你")
            self.lbl_enc.config(text="3 分钟的休息，值回票价")
        except tk.TclError:
            pass

    def close(self):
        if self._after:
            try:
                self.win.after_cancel(self._after)
            except tk.TclError:
                pass
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        if callable(self.on_done):
            try:
                self.on_done()
            except Exception:
                pass


if __name__ == "__main__":
    # 自检：直接弹出一套全身训练
    r = tk.Tk()
    r.withdraw()
    ExerciseSession(r, routine="full", on_done=r.destroy)
    r.mainloop()
