# -*- coding: utf-8 -*-
"""把官网真人演示照逐张抽成归一化骨架，构建线条人动作库。

输出 data/actions_poses.json：
{
  "neutral": {关节: [x,y]},          # 中性站姿(用于 rep 动画起止帧)
  "actions": [ {code, cn, en, cat, part, tags, anim, tip,
                keypose:{关节:[x,y]}, vis:{关节:float} }, ... ]
}
坐标系：髋中心原点、躯干长为 1、y 向下。MediaPipe 手性(person-left 在图像右=+x)。
"""
import cv2, numpy as np, os, sys, json
import mediapipe as mp
from mediapipe.tasks import python as mpy
from mediapipe.tasks.python import vision
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stickfigure as sf
from manifest import ACTIONS

# 中性站姿(与 MediaPipe 手性一致：_l 在 +x，_r 在 -x)
NEUTRAL = {
    "hip_c": [0.00, 0.00], "neck": [0.00, -1.00], "head": [0.00, -1.55],
    "sho_l": [0.22, -0.93], "sho_r": [-0.22, -0.93],
    "elb_l": [0.27, -0.45], "elb_r": [-0.27, -0.45],
    "wri_l": [0.30, 0.05],  "wri_r": [-0.30, 0.05],
    "hip_l": [0.15, 0.00],  "hip_r": [-0.15, 0.00],
    "kne_l": [0.16, 0.64],  "kne_r": [-0.16, 0.64],
    "ank_l": [0.17, 1.28],  "ank_r": [-0.17, 1.28],
}


def load_white(p):
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.ndim == 3 and im.shape[2] == 4:
        a = im[:, :, 3:4] / 255.0
        im = (im[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
    return im


def main():
    opts = vision.PoseLandmarkerOptions(
        base_options=mpy.BaseOptions(model_asset_path=os.path.join(HERE, "pose_landmarker_lite.task")),
        running_mode=vision.RunningMode.IMAGE, num_poses=1,
        min_pose_detection_confidence=0.25, min_pose_presence_confidence=0.25)
    det = vision.PoseLandmarker.create_from_options(opts)

    out = {"neutral": NEUTRAL, "actions": []}
    miss = []
    for a in ACTIONS:
        p = os.path.join(HERE, "model_png", a["code"] + ".png")
        if not os.path.exists(p):
            miss.append(a["code"]); continue
        im = load_white(p)
        if im is None:
            miss.append(a["code"]); continue
        mpimg = mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
        res = det.detect(mpimg)
        if not res.pose_landmarks:
            miss.append(a["code"]); print("NO POSE", a["code"]); continue
        lm = res.pose_landmarks[0]
        skel = sf.mp_to_skeleton(lm)
        vis = {k: round(lm[sf.MP_IDX[mk]].visibility, 3)
               for k, mk in [("wri_l", "wri_l"), ("wri_r", "wri_r"),
                             ("ank_l", "ank_l"), ("ank_r", "ank_r"),
                             ("kne_l", "kne_l"), ("kne_r", "kne_r")]}
        rec = {k: a[k] for k in ("code", "cn", "en", "cat", "part", "tags", "anim", "tip")}
        rec["keypose"] = skel
        rec["vis"] = vis
        out["actions"].append(rec)
        print(f"OK {a['code']:8s} {a['cn']}")
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    fp = os.path.join(HERE, "data", "actions_poses.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n=== {len(out['actions'])}/{len(ACTIONS)} actions -> {fp} ===")
    if miss:
        print("MISSING:", miss)


if __name__ == "__main__":
    main()
