# -*- coding: utf-8 -*-
"""线条人健身引导会话（升级版 exercise.py）。

与 exercise.ExerciseSession 完全同接口：ExerciseSession(root, routine, on_done)，
因此 pet.py 可直接 drop-in 替换。区别在于：动作姿势来自 linefit/ 真人演示照
抽取的真实骨架，用「线条勾勒轮廓」的线条人复现，覆盖 43 个《健身環大冒險》动作。

若动作库缺失，自动回退到旧版块状吉祥物 exercise.py。
"""
import math
import os
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
_LF = os.path.join(HERE, "linefit")
import sys
if _LF not in sys.path:
    sys.path.insert(0, _LF)

try:
    import linefit as LF
    _LIB = LF.load_library()
except Exception:
    _LIB = None

# 调色板（与宠物一致）
O, OHI = "#E89A7C", "#FF7A59"
RING = "#1C8C7E"
BG, CARD = "#10131C", "#1B2030"
INK, SUB, ACCENT, GO = "#EAF0FF", "#9AA6C2", "#E8622E", "#3E9E55"
PANEL = "#EEF1F6"          # 浅色画板，贴近采集照白底扁平插画
# 扁平插画背心色：肌肉=蓝、瑜珈=青、完成=绿
SHIRT_MUSCLE = "#3B7DD8"
SHIRT_YOGA = "#2FB3A3"
SHIRT_DONE = "#46A85E"

# 桌宠三套针对性训练 → 动作库 code 序列（皆站姿，适合工位）
PET_ROUTINES = {
    "full":          ["sq", "up", "bsb", "swtw", "yota", "bm"],
    "neck_shoulder": ["bm", "bsb", "baar", "sp"],
    "breathe":       ["bm", "yota"],
}
DEF_PERIOD = {"muscle": 2.2, "rhythm": 1.6, "yoga": 3.0}
REPS, HOLD = 8, 12

ENCOURAGE = ["保持节奏～", "做得很好！", "再坚持一下", "感受肌肉发力", "呼吸别憋住",
             "稳住核心", "棒极了 👏", "就是这样！"]


def _seq(routine):
    codes = PET_ROUTINES.get(routine, PET_ROUTINES["full"])
    out = []
    for c in codes:
        r = _LIB["by_code"].get(c)
        if not r:
            continue
        r = dict(r)
        r["period"] = DEF_PERIOD.get(r["cat"], 2.2)
        # 放松操/呼吸放慢节奏
        if routine == "breathe":
            r["period"] *= 1.5
        r["dur"] = HOLD if r["anim"] == "hold" else REPS * r["period"]
        out.append(r)
    return out


class ExerciseSession:
    MC_W, MC_H = 360, 320

    def __init__(self, root, routine="full", on_done=None):
        # 库不可用 → 回退旧版
        if _LIB is None:
            import exercise
            self._fallback = exercise.ExerciseSession(root, routine, on_done)
            self.close = self._fallback.close
            return
        self._fallback = None
        self.root = root
        self.routine = routine
        self.moves = _seq(routine)
        self.neutral = _LIB["neutral"]
        self.on_done = on_done
        self.idx = 0
        self.t0 = time.time()
        self.move_t0 = self.t0
        self.finished = False
        self.fin_t0 = None
        self._after = None
        self._enc_i = 0

        self.win = tk.Toplevel(root)
        self.win.title("健身引导 · 线条人")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=BG)
        self._build()
        self._center()
        self._loop()

    # ---------- UI ----------
    def _build(self):
        pad = 18
        wrap = tk.Frame(self.win, bg=BG)
        wrap.pack(fill="both", expand=True, padx=2, pady=2)
        head = tk.Frame(wrap, bg=BG)
        head.pack(fill="x", padx=pad, pady=(pad, 4))
        tk.Label(head, text="💪 起身动一动 · 跟线条人一起做", bg=BG, fg=INK,
                 font=("Microsoft YaHei", 14, "bold")).pack(side="left")
        tk.Button(head, text="✕ 结束", command=self.close, relief="flat",
                  bg=CARD, fg=SUB, bd=0, font=("Microsoft YaHei", 9),
                  padx=10, pady=3, cursor="hand2").pack(side="right")

        self.lbl_move = tk.Label(wrap, text="", bg=BG, fg=ACCENT,
                                 font=("Microsoft YaHei", 22, "bold"))
        self.lbl_move.pack(pady=(2, 0))
        self.lbl_step = tk.Label(wrap, text="", bg=BG, fg=SUB,
                                 font=("Microsoft YaHei", 10))
        self.lbl_step.pack()

        self.mc = tk.Canvas(wrap, width=self.MC_W, height=self.MC_H, bg=PANEL,
                            highlightthickness=0, bd=0)
        self.mc.pack(pady=10, padx=pad)

        self.lbl_count = tk.Label(wrap, text="", bg=BG, fg=INK,
                                  font=("Consolas", 24, "bold"))
        self.lbl_count.pack()
        self.lbl_tip = tk.Label(wrap, text="", bg=BG, fg=SUB, wraplength=320,
                                justify="center", font=("Microsoft YaHei", 11))
        self.lbl_tip.pack(pady=(2, 8))

        self.bar = tk.Canvas(wrap, width=self.MC_W, height=8, bg=CARD,
                             highlightthickness=0, bd=0)
        self.bar.pack(padx=pad)
        self.lbl_enc = tk.Label(wrap, text="", bg=BG, fg=GO,
                                font=("Microsoft YaHei", 11, "bold"))
        self.lbl_enc.pack(pady=(6, 0))

        btns = tk.Frame(wrap, bg=BG)
        btns.pack(pady=(6, pad))
        tk.Button(btns, text="跳过这节 ⏭", command=self._skip, relief="flat",
                  bg=CARD, fg=INK, bd=0, font=("Microsoft YaHei", 10),
                  padx=16, pady=6, cursor="hand2").pack(side="left", padx=6)
        tk.Button(btns, text="完成收工 ✓", command=self._finish, relief="flat",
                  bg=GO, fg="white", bd=0, font=("Microsoft YaHei", 10, "bold"),
                  padx=16, pady=6, cursor="hand2").pack(side="left", padx=6)

    def _center(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_width(), self.win.winfo_height()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f"+{(sw - w) // 2}+{max(20, (sh - h) // 2 - 30)}")

    # ---------- 绘制线条人 ----------
    def _draw(self, rec, tt):
        c = self.mc
        c.delete("all")
        W, H = self.MC_W, self.MC_H
        skel, info = LF.pose_at(self.neutral, rec, tt)
        scale = LF.fit_scale(skel, W / 2, H / 2, W, H, margin=0.14)
        ys = [v[1] for v in skel.values()]
        cy = H / 2 - (min(ys) + max(ys)) / 2 * scale
        col = SHIRT_YOGA if rec["cat"] == "yoga" else SHIRT_MUSCLE
        LF.draw_tk(c, skel, W / 2, cy, scale, color=col)
        if info.get("squeeze"):
            c.create_text(W - 56, 34, text="用力!", fill=ACCENT,
                          font=("Microsoft YaHei", 14, "bold"))
        if self.routine == "breathe":
            ph = info.get("phase", 0)
            c.create_text(W / 2, 26, text="吸气…" if ph < 0.5 else "呼气…",
                          fill=RING, font=("Microsoft YaHei", 13, "bold"))

    def _draw_finish(self, tt):
        c = self.mc
        c.delete("all")
        W, H = self.MC_W, self.MC_H
        # 欢呼：双臂高举的线条人 + 跳动
        cheer = dict(self.neutral)
        cheer = {k: list(v) for k, v in self.neutral.items()}
        cheer["wri_l"], cheer["wri_r"] = [0.34, -1.75], [-0.34, -1.75]
        cheer["elb_l"], cheer["elb_r"] = [0.30, -1.35], [-0.30, -1.35]
        jump = abs(math.sin(tt * 4)) * 0.12
        cheer = {k: [v[0], v[1] - jump] for k, v in cheer.items()}
        scale = LF.fit_scale(cheer, W / 2, H / 2, W, H, margin=0.18)
        ys = [v[1] for v in cheer.values()]
        cy = H / 2 - (min(ys) + max(ys)) / 2 * scale
        LF.draw_tk(c, cheer, W / 2, cy, scale, color=SHIRT_DONE)
        for i, (sx, sy) in enumerate(((-130, -20), (130, 10), (-110, 70), (120, 80))):
            if (int(tt * 6) + i) % 2 == 0:
                c.create_text(W / 2 + sx, H / 2 + sy, text="✦", fill="#FFD45E",
                              font=("Segoe UI", 16, "bold"))

    # ---------- 主循环 ----------
    def _loop(self):
        if not self.win.winfo_exists():
            return
        now = time.time()
        try:
            if self.finished:
                self._draw_finish(now - self.fin_t0)
                if now - self.fin_t0 > 2.6:
                    self.close(); return
            else:
                rec = self.moves[self.idx]
                tt = now - self.move_t0
                if tt >= rec["dur"]:
                    self.idx += 1
                    if self.idx >= len(self.moves):
                        self._finish()
                        self._after = self.win.after(33, self._loop); return
                    self.move_t0 = now
                    self._enc_i = (self._enc_i + 1) % len(ENCOURAGE)
                    rec = self.moves[self.idx]; tt = 0.0
                self._draw(rec, tt)
                self._text(rec, tt, now)
        except tk.TclError:
            return
        self._after = self.win.after(33, self._loop)

    def _text(self, rec, tt, now):
        cat_cn = {"muscle": "肌肉訓練", "rhythm": "節奏", "yoga": "瑜珈"}.get(rec["cat"], "")
        self.lbl_move.config(text=rec["cn"])
        self.lbl_step.config(text=f"第 {self.idx + 1}/{len(self.moves)} 节 · {rec['en']} · {cat_cn} · {rec['part']}")
        self.lbl_tip.config(text="🏷 " + "  ".join("#" + t for t in rec["tags"]) + "\n" + rec["tip"])
        if rec["anim"] == "hold":
            self.lbl_count.config(text=f"保持 {max(0, int(rec['dur'] - tt))}s")
        else:
            done = min(REPS, int(tt / rec["period"]) + 1)
            self.lbl_count.config(text=f"× {done} / {REPS}")
        self.lbl_enc.config(text=ENCOURAGE[self._enc_i])
        total = sum(m["dur"] for m in self.moves)
        elapsed = sum(m["dur"] for m in self.moves[:self.idx]) + min(tt, rec["dur"])
        frac = max(0.0, min(1.0, elapsed / total)) if total else 1.0
        self.bar.delete("all")
        self.bar.create_rectangle(0, 0, self.MC_W, 8, fill=CARD, outline="")
        self.bar.create_rectangle(0, 0, int(self.MC_W * frac), 8, fill=ACCENT, outline="")

    # ---------- 控制 ----------
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
    r = tk.Tk(); r.withdraw()
    ExerciseSession(r, routine="full", on_done=r.destroy)
    r.mainloop()
