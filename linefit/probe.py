# -*- coding: utf-8 -*-
import cv2, sys, os
SRC = r"G:\录屏视频\任天堂健身动作.mp4"
cap = cv2.VideoCapture(SRC)
if not cap.isOpened():
    print("CANNOT OPEN", SRC); sys.exit(1)
fps = cap.get(cv2.CAP_PROP_FPS)
n   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
dur = n / fps if fps else 0
print(f"fps={fps:.3f} frames={n} size={w}x{h} dur={dur:.1f}s")
outdir = r"C:\Users\megarobo-BJ\claude-pet\linefit\frames"
# 抽 12 张等距样帧
k = 12
for i in range(k):
    fno = int(n * (i + 0.5) / k)
    cap.set(cv2.CAP_PROP_POS_FRAMES, fno)
    ok, fr = cap.read()
    if not ok: continue
    # 缩到宽 480 便于查看
    sc = 480 / fr.shape[1]
    fr = cv2.resize(fr, (480, int(fr.shape[0]*sc)))
    p = os.path.join(outdir, f"s{i:02d}_t{fno/fps:05.1f}s.jpg")
    cv2.imwrite(p, fr, [cv2.IMWRITE_JPEG_QUALITY, 80])
print("wrote", k, "sample frames to", outdir)
cap.release()
