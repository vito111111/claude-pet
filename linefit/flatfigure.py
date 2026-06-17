# -*- coding: utf-8 -*-
"""扁平插画人(flat figure)渲染器 —— 取代旧版「线条人/火柴人」。

风格参照「抖音采集」里的健身扁平插画：实心填充的人体剪影
（肤色四肢 + 蓝色背心 + 深灰短裤 + 棕色马尾），而非细线勾边。

只负责「画」：输入 15 点像素坐标 P(dict[str]->(x,y)) 与一个躯干像素尺度 scale，
按身体分段画成有粗细、带自描边的扁平色块。骨架数据格式保持不变，
因此 actions_poses.json / pose_at 等上游完全复用。
"""

# 基础配色（参照采集照：蓝背心 / 深灰短裤 / 暖肤色 / 深棕发）
SKIN = "#F2C49C"
HAIR = "#4A3526"
SHORTS = "#3B404A"
SHIRT_DEFAULT = "#3B7DD8"   # 蓝色背心
SHOE_TIE = True             # 鞋袜跟随背心色（采集照里为蓝袜）

# 各身体分段相对躯干长(=1.0)的粗细
W_THIGH = 0.27
W_SHIN = 0.17
W_ARM = 0.155
W_NECK = 0.185
W_TORSO = 0.46
W_SHOULDER = 0.30
W_PELVIS = 0.32
HEAD_R = 0.245              # 头半径(躯干长为单位)


def _clamp(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))


def darken(hexc, f=0.78):
    """把颜色按比例压暗，用作自描边色，营造扁平插画的边缘层次。"""
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "#%02X%02X%02X" % (_clamp(r * f), _clamp(g * f), _clamp(b * f))


def _capsule(c, p, q, w, fill, tag, ow=0.0, outline=None):
    """画一段两端浑圆的「胶囊」粗线 = 一节实心肢体；ow>0 时先铺一圈描边。"""
    if ow > 0 and outline:
        c.create_line(p[0], p[1], q[0], q[1], fill=outline, width=w + 2 * ow,
                      capstyle="round", joinstyle="round", tags=tag)
    c.create_line(p[0], p[1], q[0], q[1], fill=fill, width=w,
                  capstyle="round", joinstyle="round", tags=tag)


def _disc(c, x, y, r, fill, tag, ow=0.0, outline=None):
    if ow > 0 and outline:
        c.create_oval(x - r - ow, y - r - ow, x + r + ow, y + r + ow,
                      fill=outline, outline="", tags=tag)
    c.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline="", tags=tag)


def draw(canvas, P, scale, shirt=SHIRT_DEFAULT, head_r=HEAD_R, tag="stick"):
    """把 15 点像素坐标 P 画成扁平插画人。

    P    : dict 关节名 -> (x, y) 像素坐标（已由 place() 投影）
    scale: 躯干长对应的像素数（决定整体粗细）
    shirt: 背心(及鞋袜)颜色，用来区分系列（肌肉=蓝、瑜珈=青等）
    """
    c = canvas
    skin_o = darken(SKIN)
    shorts_o = darken(SHORTS)
    shirt_o = darken(shirt)
    hair_o = darken(HAIR, 0.7)
    shoe = shirt if SHOE_TIE else "#2E3340"
    shoe_o = darken(shoe)
    ow = max(1.0, scale * 0.014)

    wt = W_THIGH * scale
    ws = W_SHIN * scale
    wa = W_ARM * scale
    wn = W_NECK * scale
    wtorso = W_TORSO * scale
    wsh = W_SHOULDER * scale
    wp = W_PELVIS * scale
    hr = head_r * scale

    def has(*ks):
        return all(k in P for k in ks)

    # —— 1. 双腿：大腿(短裤色) + 小腿(肤色) + 鞋(背心色) ——
    for side in ("l", "r"):
        hp, kn, an = f"hip_{side}", f"kne_{side}", f"ank_{side}"
        if has(hp, kn):
            _capsule(c, P[hp], P[kn], wt, SHORTS, tag, ow, shorts_o)
        if has(kn, an):
            _capsule(c, P[kn], P[an], ws, SKIN, tag, ow, skin_o)
        if an in P:
            ax, ay = P[an]
            # 脚：沿小腿方向稍微前探的圆头
            if kn in P:
                dx, dy = ax - P[kn][0], ay - P[kn][1]
                d = (dx * dx + dy * dy) ** 0.5 or 1.0
                tx, ty = ax + dx / d * ws * 0.5, ay + dy / d * ws * 0.5
            else:
                tx, ty = ax, ay
            _capsule(c, (ax, ay), (tx, ty), ws * 0.92, shoe, tag, ow, shoe_o)

    # —— 2. 骨盆(短裤色)，把两腿在髋部连成一体 ——
    if has("hip_l", "hip_r"):
        _capsule(c, P["hip_l"], P["hip_r"], wp, SHORTS, tag, ow, shorts_o)

    # —— 3. 躯干(背心色)：脊柱粗胶囊 + 肩部横档 ——
    if has("neck", "hip_c"):
        _capsule(c, P["neck"], P["hip_c"], wtorso, shirt, tag, ow, shirt_o)
    if has("sho_l", "sho_r"):
        _capsule(c, P["sho_l"], P["sho_r"], wsh, shirt, tag, ow, shirt_o)

    # —— 4. 双臂(肤色，背心无袖) + 手 ——
    for side in ("l", "r"):
        sh, el, wr = f"sho_{side}", f"elb_{side}", f"wri_{side}"
        if has(sh, el):
            _capsule(c, P[sh], P[el], wa, SKIN, tag, ow, skin_o)
        if has(el, wr):
            _capsule(c, P[el], P[wr], wa * 0.9, SKIN, tag, ow, skin_o)
        if wr in P:
            _disc(c, P[wr][0], P[wr][1], wa * 0.55, SKIN, tag, ow, skin_o)

    # —— 5. 脖子(肤色) ——
    if has("neck", "head"):
        _capsule(c, P["neck"], P["head"], wn, SKIN, tag, ow, skin_o)

    # —— 6. 头：脸(肤色圆) + 头发(顶部扇形) ——
    if "head" in P:
        hx, hy = P["head"]
        c.create_oval(hx - hr - ow, hy - hr - ow, hx + hr + ow, hy + hr + ow,
                      fill=skin_o, outline="", tags=tag)
        c.create_oval(hx - hr, hy - hr, hx + hr, hy + hr,
                      fill=SKIN, outline="", tags=tag)
        # 头发盖在头顶（画布 y 向下，200°起 140°扇形≈上半圈）
        c.create_arc(hx - hr, hy - hr, hx + hr, hy + hr,
                     start=200, extent=140, style="pieslice",
                     fill=HAIR, outline="", tags=tag)
        # 一缕马尾（朝后上方的小发束，方向用 颈→头 反推个偏移）
        if "neck" in P:
            dx, dy = hx - P["neck"][0], hy - P["neck"][1]
            d = (dx * dx + dy * dy) ** 0.5 or 1.0
            px, py = hx - dx / d * hr * 0.2, hy - dy / d * hr * 1.05
            _disc(c, px, py, hr * 0.5, HAIR, tag)
    return P
