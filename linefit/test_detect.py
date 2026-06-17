# -*- coding: utf-8 -*-
import cv2, numpy as np, urllib.request, os, ssl
import mediapipe as mp
ssl._create_default_https_context = ssl._create_unverified_context
BASE = "https://www.nintendo.com/hk/switch/ringadventure/assets/img/list/model/"
codes = ["sq","up","bsb","yota"]   # 深蹲/过头推/侧弯/立木
d = r"C:\Users\megarobo-BJ\claude-pet\linefit\model_png"
os.makedirs(d, exist_ok=True)
hdr={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
for c in codes:
    p=os.path.join(d,c+".png")
    if not os.path.exists(p):
        try:
            req=urllib.request.Request(BASE+c+".png",headers=hdr)
            with urllib.request.urlopen(req,timeout=30) as r, open(p,"wb") as f:
                f.write(r.read())
            print("dl",c,os.path.getsize(p),"B")
        except Exception as e:
            print("FAIL dl",c,e)
mpp = mp.solutions.pose
pose = mpp.Pose(static_image_mode=True, model_complexity=2, min_detection_confidence=0.3)
def test(img, tag):
    if img is None: print(tag,"img=None"); return
    h,w=img.shape[:2]
    res=pose.process(cv2.cvtColor(img,cv2.COLOR_BGR2RGB))
    if not res.pose_landmarks:
        print(f"{tag}: NO POSE ({w}x{h})"); return
    vis=[lm.visibility for lm in res.pose_landmarks.landmark]
    print(f"{tag}: POSE OK ({w}x{h}) avg_vis={np.mean(vis):.2f} key_vis(nose/Lwri/Rwri/Lank/Rank)="
          f"{vis[0]:.2f},{vis[15]:.2f},{vis[16]:.2f},{vis[27]:.2f},{vis[28]:.2f}")
# model PNGs (may have alpha -> composite on white)
for c in codes:
    p=os.path.join(d,c+".png")
    if not os.path.exists(p): continue
    im=cv2.imread(p,cv2.IMREAD_UNCHANGED)
    if im is None: print("read fail",c); continue
    if im.ndim==3 and im.shape[2]==4:
        a=im[:,:,3:4]/255.0; rgb=im[:,:,:3]
        im=(rgb*a+255*(1-a)).astype(np.uint8)
    test(im, "PNG "+c)
# a video frame (left model region) at t=3.3s
cap=cv2.VideoCapture(r"G:\录屏视频\任天堂健身动作.mp4")
cap.set(cv2.CAP_PROP_POS_FRAMES, int(3.3*16.211))
ok,fr=cap.read(); cap.release()
if ok:
    test(fr,"VIDEO full")
    # crop a likely model area: rows have model around x in [0.30,0.52], variable y
    h,w=fr.shape[:2]
    crop=fr[int(0.10*h):int(0.55*h), int(0.30*w):int(0.55*w)]
    test(crop,"VIDEO crop")
