# -*- coding: utf-8 -*-
"""线条人(stick figure)骨架格式 + 渲染器。

骨架统一用 15 点归一化坐标表示，坐标系：
  - 原点在「髋中心(hip_c)」，x 向右、y 向下；
  - 单位 = 肩到髋的躯干长度(scale=1.0)，与画面分辨率无关；
  - 因此同一套数据可在任意画布/任意尺寸下用线条复现。

15 个关节键名：
  head, neck, sho_l, sho_r, elb_l, elb_r, wri_l, wri_r,
  hip_c, hip_l, hip_r, kne_l, kne_r, ank_l, ank_r

骨骼连线(BONES) + 头部画圆，即「用线条勾勒人的轮廓」。
"""
import math

# MediaPipe Pose 33 点 → 本 15 点骨架 的下标映射
MP_IDX = {
    "nose": 0, "sho_l": 11, "sho_r": 12, "elb_l": 13, "elb_r": 14,
    "wri_l": 15, "wri_r": 16, "hip_l": 23, "hip_r": 24,
    "kne_l": 25, "kne_r": 26, "ank_l": 27, "ank_r": 28,
    "ear_l": 7, "ear_r": 8,
}

JOINTS = ["head", "neck", "sho_l", "sho_r", "elb_l", "elb_r", "wri_l", "wri_r",
          "hip_c", "hip_l", "hip_r", "kne_l", "kne_r", "ank_l", "ank_r"]

# 线条骨架：四肢 + 脊柱 + 肩带 + 髋带
BONES = [
    ("neck", "sho_l"), ("neck", "sho_r"),
    ("sho_l", "elb_l"), ("elb_l", "wri_l"),
    ("sho_r", "elb_r"), ("elb_r", "wri_r"),
    ("neck", "hip_c"),
    ("hip_c", "hip_l"), ("hip_c", "hip_r"),
    ("hip_l", "kne_l"), ("kne_l", "ank_l"),
    ("hip_r", "kne_r"), ("kne_r", "ank_r"),
]


def mp_to_skeleton(lm):
    """MediaPipe landmark 列表(33) → 归一化 15 点骨架(dict[str]->[x,y])。

    归一化：以髋中心为原点，以「肩中点→髋中点」躯干长为单位 1。
    返回的坐标 y 向下为正(图像坐标系)。
    """
    def pt(name):
        i = MP_IDX[name]
        return (lm[i].x, lm[i].y)

    sl, sr = pt("sho_l"), pt("sho_r")
    hl, hr = pt("hip_l"), pt("hip_r")
    neck = ((sl[0] + sr[0]) / 2, (sl[1] + sr[1]) / 2)
    hip_c = ((hl[0] + hr[0]) / 2, (hl[1] + hr[1]) / 2)
    torso = math.hypot(neck[0] - hip_c[0], neck[1] - hip_c[1]) or 1e-6

    raw = {
        "neck": neck, "hip_c": hip_c,
        "sho_l": sl, "sho_r": sr, "hip_l": hl, "hip_r": hr,
        "elb_l": pt("elb_l"), "elb_r": pt("elb_r"),
        "wri_l": pt("wri_l"), "wri_r": pt("wri_r"),
        "kne_l": pt("kne_l"), "kne_r": pt("kne_r"),
        "ank_l": pt("ank_l"), "ank_r": pt("ank_r"),
    }
    # 头：用鼻尖方向，从颈部沿「颈→鼻」延伸 0.55 躯干，画圆中心
    nose = pt("nose")
    hd = (nose[0] - neck[0], nose[1] - neck[1])
    hlen = math.hypot(*hd) or 1e-6
    raw["head"] = (neck[0] + hd[0] / hlen * 0.55 * torso,
                   neck[1] + hd[1] / hlen * 0.55 * torso)

    out = {}
    for k, (x, y) in raw.items():
        out[k] = [round((x - hip_c[0]) / torso, 4),
                  round((y - hip_c[1]) / torso, 4)]
    return out


def avg_visibility(lm):
    keys = ["nose", "sho_l", "sho_r", "hip_l", "hip_r",
            "wri_l", "wri_r", "ank_l", "ank_r"]
    return sum(lm[MP_IDX[k]].visibility for k in keys) / len(keys)


# ---------------- 渲染 ----------------
def lerp_skel(a, b, t):
    """两骨架线性插值。"""
    return {k: [a[k][0] + (b[k][0] - a[k][0]) * t,
                a[k][1] + (b[k][1] - a[k][1]) * t] for k in a}


def place(skel, cx, cy, scale):
    """归一化骨架 → 画布像素坐标。scale = 躯干长对应的像素数。"""
    return {k: (cx + v[0] * scale, cy + v[1] * scale) for k, v in skel.items()}


def bbox(skel):
    xs = [v[0] for v in skel.values()]
    ys = [v[1] for v in skel.values()]
    return min(xs), min(ys), max(xs), max(ys)


def draw_tk(canvas, skel, cx, cy, scale, color="#E89A7C", joint="#FF7A59",
            width=10, head_r=0.42, tag="stick"):
    """在 tkinter Canvas 上把骨架画成线条人。head_r 单位为躯干长。"""
    P = place(skel, cx, cy, scale)
    canvas.delete(tag)
    for a, b in BONES:
        if a in P and b in P:
            canvas.create_line(*P[a], *P[b], fill=color, width=width,
                               capstyle="round", joinstyle="round", tags=tag)
    # 关节点
    for k in ("sho_l", "sho_r", "elb_l", "elb_r", "wri_l", "wri_r",
              "hip_l", "hip_r", "kne_l", "kne_r", "ank_l", "ank_r"):
        if k in P:
            x, y = P[k]
            r = width * 0.55
            canvas.create_oval(x - r, y - r, x + r, y + r, fill=joint,
                               outline="", tags=tag)
    # 头(圆)
    if "head" in P and "neck" in P:
        hx, hy = P["head"]
        hr = head_r * scale
        canvas.create_oval(hx - hr, hy - hr, hx + hr, hy + hr, outline=color,
                           width=width, fill="", tags=tag)
    return P
