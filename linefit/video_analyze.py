# -*- coding: utf-8 -*-
"""对本地录屏 任天堂健身动作.mp4 执行姿态分析并保存数据。

录屏内容是官网列表页的滚动播放，画面里始终有「当前动作的真人演示照」。
本脚本逐帧(采样)抽骨架，并把每帧骨架最近邻匹配到动作库 keypose，
得到「视频里依次出现了哪些动作 / 各停留多久」的时间线。

输出：
  data/video_pose_track.json  逐采样帧的归一化骨架 + 平均可见度
  data/video_timeline.json    去抖后的动作分段 [{code,cn,start,end,dur}]
"""
import cv2, numpy as np, os, sys, json
import mediapipe as mp
from mediapipe.tasks import python as mpy
from mediapipe.tasks.python import vision
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stickfigure as sf

SRC = r"G:\录屏视频\任天堂健身动作.mp4"
SAMPLE_DT = 0.33          # 采样间隔(秒)
VIS_MIN = 0.55            # 低于此可见度视为无有效人物


def skel_dist(a, b):
    """两归一化骨架的关节欧氏距离均值。"""
    return float(np.mean([np.hypot(a[k][0] - b[k][0], a[k][1] - b[k][1])
                          for k in a if k in b]))


def main():
    lib_fp = os.path.join(HERE, "data", "actions_poses.json")
    lib = json.load(open(lib_fp, encoding="utf-8")) if os.path.exists(lib_fp) else None
    keyposes = {a["code"]: a["keypose"] for a in lib["actions"]} if lib else {}
    cn = {a["code"]: a["cn"] for a in lib["actions"]} if lib else {}

    opts = vision.PoseLandmarkerOptions(
        base_options=mpy.BaseOptions(model_asset_path=os.path.join(HERE, "pose_landmarker_lite.task")),
        running_mode=vision.RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=0.3, min_pose_presence_confidence=0.3)
    det = vision.PoseLandmarker.create_from_options(opts)

    cap = cv2.VideoCapture(SRC)
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(SAMPLE_DT * fps)))
    track = []
    fno = 0
    while fno < n:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fno)
        ok, fr = cap.read()
        if not ok:
            break
        t = fno / fps
        mpimg = mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
        res = det.detect_for_video(mpimg, int(t * 1000))
        rec = {"t": round(t, 2)}
        if res.pose_landmarks:
            lm = res.pose_landmarks[0]
            vis = sf.avg_visibility(lm)
            rec["vis"] = round(vis, 3)
            if vis >= VIS_MIN:
                skel = sf.mp_to_skeleton(lm)
                rec["skel"] = {k: [round(v[0], 3), round(v[1], 3)] for k, v in skel.items()}
                if keyposes:
                    best = min(keyposes, key=lambda c: skel_dist(skel, keyposes[c]))
                    rec["match"] = best
                    rec["match_cn"] = cn[best]
                    rec["dist"] = round(skel_dist(skel, keyposes[best]), 3)
        track.append(rec)
        fno += step
    cap.release()

    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    json.dump(track, open(os.path.join(HERE, "data", "video_pose_track.json"), "w",
                          encoding="utf-8"), ensure_ascii=False)

    # 去抖分段：连续相同 match 且 dist 合理(<0.6) 合并为一段，时长≥0.6s 才保留
    seg = []
    for r in track:
        m = r.get("match")
        if m is None or r.get("dist", 9) > 0.6:
            continue
        if seg and seg[-1]["code"] == m:
            seg[-1]["end"] = r["t"]
        else:
            seg.append({"code": m, "cn": r.get("match_cn", m), "start": r["t"], "end": r["t"]})
    seg = [dict(s, dur=round(s["end"] - s["start"], 1)) for s in seg if s["end"] - s["start"] >= 0.6]
    json.dump(seg, open(os.path.join(HERE, "data", "video_timeline.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)

    have = sum(1 for r in track if "skel" in r)
    print(f"采样帧={len(track)} 有效人物帧={have} 时间线分段={len(seg)}")
    for s in seg[:40]:
        print(f"  {s['start']:5.1f}-{s['end']:5.1f}s ({s['dur']:4.1f}s)  {s['code']:7s} {s['cn']}")


if __name__ == "__main__":
    main()
