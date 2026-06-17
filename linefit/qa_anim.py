import cv2,numpy as np,os,sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import linefit as LF
lib=LF.load_library(); neutral=lib["neutral"]
def draw(img,skel,cx,cy,scale,col=(124,160,232),w=7):
    P=LF.place(skel,cx,cy,scale)
    for a,b in LF.BONES: cv2.line(img,(int(P[a][0]),int(P[a][1])),(int(P[b][0]),int(P[b][1])),col,w,cv2.LINE_AA)
    for k in LF.JOINT_DOTS: cv2.circle(img,(int(P[k][0]),int(P[k][1])),int(w*0.7),(89,122,255),-1,cv2.LINE_AA)
    hx,hy=P["head"];cv2.circle(img,(int(hx),int(hy)),int(0.42*scale),col,w,cv2.LINE_AA)
cell=200
for code in ["sq","up"]:
    rec=dict(lib["by_code"][code]);rec["period"]=2.0
    strip=np.full((cell,cell*5,3),20,np.uint8)
    for i,ph in enumerate([0,0.25,0.5,0.75,1.0]):
        tt=ph*2.0; skel,info=LF.pose_at(neutral,rec,tt)
        ys=[v[1] for v in skel.values()];xs=[v[0] for v in skel.values()]
        bh=(max(ys)-min(ys))+0.6;bw=(max(xs)-min(xs)) or 1
        sc=min(cell*0.66/bh,cell*0.8/bw); ox=i*cell
        cy=cell/2-(min(ys)+max(ys))/2*sc
        draw(strip,skel,ox+cell/2,cy,sc)
        cv2.rectangle(strip,(ox,0),(ox+cell-1,cell-1),(40,48,64),1)
    cv2.imwrite(f"frames/anim_{code}.jpg",strip,[cv2.IMWRITE_JPEG_QUALITY,85])
    print("wrote anim",code)
