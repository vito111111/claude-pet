# -*- coding: utf-8 -*-
"""线条人动作播放器：读取 actions_poses.json，把每个动作复现成会动的线条人。

动画模型：
  - rep  往复计次：u = (1-cos(2πφ))/2  在「中性站姿 ↔ 关键姿势」之间往返，
          一个 period 完成一次 rep；顶/底点触发「用力」提示。
  - hold 静态保持：维持关键姿势 + 轻微呼吸起伏 / 摆动。

提供 standalone tkinter 预览：python linefit.py [routine]
"""
import json, math, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "actions_poses.json")

if HERE not in sys.path:
    sys.path.insert(0, HERE)
import flatfigure as FF

# 扁平插画配色（参照「抖音采集」健身插画）：蓝背心 / 青背心(瑜珈)
SHIRT_MUSCLE = "#3B7DD8"
SHIRT_YOGA = "#2FB3A3"

# 与 stickfigure.BONES 保持一致(本文件自带一份，便于被 pet 单独引用)
BONES = [
    ("neck", "sho_l"), ("neck", "sho_r"),
    ("sho_l", "elb_l"), ("elb_l", "wri_l"),
    ("sho_r", "elb_r"), ("elb_r", "wri_r"),
    ("neck", "hip_c"),
    ("hip_c", "hip_l"), ("hip_c", "hip_r"),
    ("hip_l", "kne_l"), ("kne_l", "ank_l"),
    ("hip_r", "kne_r"), ("kne_r", "ank_r"),
]
JOINT_DOTS = ("sho_l", "sho_r", "elb_l", "elb_r", "wri_l", "wri_r",
              "hip_l", "hip_r", "kne_l", "kne_r", "ank_l", "ank_r")


def load_library(path=DATA):
    with open(path, "r", encoding="utf-8") as f:
        lib = json.load(f)
    lib["by_code"] = {a["code"]: a for a in lib["actions"]}
    return lib


def _lerp(a, b, t):
    return {k: [a[k][0] + (b[k][0] - a[k][0]) * t,
                a[k][1] + (b[k][1] - a[k][1]) * t] for k in a}


def pose_at(neutral, rec, tt):
    """返回 (skel, info)。info: dict(rep_done, total_reps?, squeeze, phase)。"""
    key = rec["keypose"]
    # 关键姿势可能缺中性里某些键(理论上同集)，对齐到 neutral 的键
    key = {k: key.get(k, neutral[k]) for k in neutral}
    if rec["anim"] == "hold":
        # 呼吸起伏：整体上下微动 + 手臂轻摆
        br = math.sin(tt * 1.4) * 0.02
        sway = math.sin(tt * 0.9) * 0.015
        skel = {k: [v[0] + sway * (1 if v[1] < 0 else 0), v[1] - br] for k, v in key.items()}
        return skel, {"phase": 0.0, "squeeze": False}
    # rep
    P = rec.get("period", 2.0)
    ph = (tt % P) / P
    u = (1 - math.cos(2 * math.pi * ph)) / 2.0      # 0→1→0
    skel = _lerp(neutral, key, u)
    return skel, {"phase": ph, "squeeze": u > 0.82}


# ---------------- 渲染(纯坐标，便于多后端) ----------------
def place(skel, cx, cy, scale):
    return {k: (cx + v[0] * scale, cy + v[1] * scale) for k, v in skel.items()}


def fit_scale(skel, cx, cy, w, h, margin=0.16):
    """根据骨架包围盒自动求缩放与基准点，使其稳定地居中铺满画布。"""
    xs = [v[0] for v in skel.values()]; ys = [v[1] for v in skel.values()]
    bw = max(xs) - min(xs) or 1e-6
    bh = (max(ys) - min(ys)) + 0.5      # 给头圈留点空间
    sx = w * (1 - 2 * margin) / bw
    sy = h * (1 - 2 * margin) / bh
    return min(sx, sy)


def draw_tk(canvas, skel, cx, cy, scale, color=SHIRT_MUSCLE, joint=None,
            width=11, head_r=FF.HEAD_R, ring=None, tag="stick"):
    """把骨架画成扁平插画人。`color` 解释为背心(及鞋袜)颜色，用于区分系列。

    (保留旧签名以便 drop-in；joint/width/ring 参数已不再使用。)
    """
    P = place(skel, cx, cy, scale)
    canvas.delete(tag)
    return FF.draw(canvas, P, scale, shirt=color, head_r=head_r, tag=tag)


# ====================== 独立预览 ======================
ROUTINES = {
    "full":          ["sq", "up", "bsb", "swtw", "yota", "bm"],
    "neck_shoulder": ["bm", "bsb", "baar", "sp"],
    "core":          ["twab", "knup", "pla", "yohu"],
    "yoga":          ["yoch", "yota", "yoeitw", "yoeith", "yoog"],
    "all":           None,   # 全部动作依次演示
}
DEF_PERIOD = {"muscle": 2.0, "rhythm": 1.4, "yoga": 3.0}
REPS = 6
HOLD = 8


def _build_seq(lib, routine):
    codes = ROUTINES.get(routine)
    recs = lib["actions"] if codes is None else [lib["by_code"][c] for c in codes if c in lib["by_code"]]
    seq = []
    for r in recs:
        r = dict(r)
        r["period"] = DEF_PERIOD.get(r["cat"], 2.0)
        r["dur"] = HOLD if r["anim"] == "hold" else REPS * r["period"]
        seq.append(r)
    return seq


def preview(routine="full"):
    import tkinter as tk
    lib = load_library()
    seq = _build_seq(lib, routine)
    neutral = lib["neutral"]
    BG, CARD, INK, SUB, ACC = "#10131C", "#1B2030", "#EAF0FF", "#9AA6C2", "#FF7A59"
    PANEL = "#EEF1F6"   # 浅色画板，贴近采集照的白底扁平插画
    W, H = 460, 520
    root = tk.Tk()
    root.title("线条人 · Ring Fit 预览")
    root.configure(bg=BG)
    title = tk.Label(root, text="", bg=BG, fg=ACC, font=("Microsoft YaHei", 20, "bold"))
    title.pack(pady=(14, 0))
    sub = tk.Label(root, text="", bg=BG, fg=SUB, font=("Microsoft YaHei", 10))
    sub.pack()
    cv = tk.Canvas(root, width=W, height=380, bg=PANEL, highlightthickness=0)
    cv.pack(padx=16, pady=10)
    cnt = tk.Label(root, text="", bg=BG, fg=INK, font=("Consolas", 20, "bold"))
    cnt.pack()
    tip = tk.Label(root, text="", bg=BG, fg=SUB, wraplength=420, font=("Microsoft YaHei", 11))
    tip.pack(pady=(2, 12))
    st = {"i": 0, "t0": time.time()}

    def loop():
        if not seq:
            root.destroy(); return
        now = time.time()
        rec = seq[st["i"]]
        tt = now - st["t0"]
        if tt >= rec["dur"]:
            st["i"] = (st["i"] + 1) % len(seq)
            st["t0"] = now; rec = seq[st["i"]]; tt = 0.0
        skel, info = pose_at(neutral, rec, tt)
        scale = fit_scale(skel, W / 2, 190, W, 380)
        cx, cy = W / 2, 190 - (min(v[1] for v in skel.values()) +
                               max(v[1] for v in skel.values())) / 2 * scale + 0
        # 居中：让骨架包围盒纵向居中
        ys = [v[1] for v in skel.values()]
        cy = 190 - (min(ys) + max(ys)) / 2 * scale
        col = SHIRT_YOGA if rec["cat"] == "yoga" else SHIRT_MUSCLE
        draw_tk(cv, skel, W / 2, cy, scale, color=col)
        if info["squeeze"]:
            cv.create_text(W - 70, 40, text="用力!", fill=ACC,
                           font=("Microsoft YaHei", 14, "bold"), tags="stick")
        cat_cn = {"muscle": "肌肉訓練", "rhythm": "節奏", "yoga": "瑜珈"}[rec["cat"]]
        title.config(text=rec["cn"])
        sub.config(text=f"{rec['en']} · {cat_cn}系列 · {rec['part']}")
        tip.config(text="🏷 " + "  ".join("#" + t for t in rec["tags"]) + "\n" + rec["tip"])
        if rec["anim"] == "hold":
            cnt.config(text=f"保持 {max(0, int(rec['dur'] - tt))}s")
        else:
            cnt.config(text=f"× {min(REPS, int(tt / rec['period']) + 1)} / {REPS}")
        root.after(33, loop)

    loop()
    root.mainloop()


if __name__ == "__main__":
    preview(sys.argv[1] if len(sys.argv) > 1 else "full")
