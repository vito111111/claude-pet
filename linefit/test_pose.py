# -*- coding: utf-8 -*-
import cv2, numpy as np, os, sys
import mediapipe as mp
from mediapipe.tasks import python as mpy
from mediapipe.tasks.python import vision
sys.path.insert(0, os.path.dirname(__file__))
import stickfigure as sf

opts = vision.PoseLandmarkerOptions(
    base_options=mpy.BaseOptions(model_asset_path="pose_landmarker_lite.task"),
    running_mode=vision.RunningMode.IMAGE, num_poses=1,
    min_pose_detection_confidence=0.3, min_pose_presence_confidence=0.3)
det = vision.PoseLandmarker.create_from_options(opts)

def load_white(p):
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None: return None
    if im.ndim==3 and im.shape[2]==4:
        a=im[:,:,3:4]/255.0; im=(im[:,:,:3]*a+255*(1-a)).astype(np.uint8)
    return im

def render_overlay(im, skel, path):
    """把抽到的线条人画在白底上对照保存。"""
    h,w=im.shape[:2]
    canvas = im.copy()
    cx,cy = w*0.5, h*0.55
    scale = h*0.22
    P = sf.place(skel, cx, cy, scale)
    for a,b in sf.BONES:
        pa,pb=P[a],P[b]
        cv2.line(canvas,(int(pa[0]),int(pa[1])),(int(pb[0]),int(pb[1])),(0,90,255),6,cv2.LINE_AA)
    if "head" in P:
        hx,hy=P["head"]; cv2.circle(canvas,(int(hx),int(hy)),int(0.42*scale),(0,90,255),6,cv2.LINE_AA)
    cv2.imwrite(path, canvas, [cv2.IMWRITE_JPEG_QUALITY,82])

for c in ["up","sq","bsb","yota"]:
    p=f"model_png/{c}.png"
    if not os.path.exists(p): print(c,"missing"); continue
    im=load_white(p); h,w=im.shape[:2]
    mpimg=mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(im,cv2.COLOR_BGR2RGB))
    res=det.detect(mpimg)
    if not res.pose_landmarks:
        print(c,"NO POSE"); continue
    lm=res.pose_landmarks[0]
    vis=sf.avg_visibility(lm)
    skel=sf.mp_to_skeleton(lm)
    render_overlay(im, skel, f"frames/check_{c}.jpg")
    print(f"{c}: OK vis={vis:.2f}  wri_l_y={skel['wri_l'][1]:.2f} wri_r_y={skel['wri_r'][1]:.2f} ank_y={skel['ank_l'][1]:.2f}")
print("DONE")
