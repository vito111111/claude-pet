# -*- coding: utf-8 -*-
import urllib.request, os, ssl, time, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manifest import ACTIONS, MODEL_BASE
ssl._create_default_https_context = ssl._create_unverified_context
hdr={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}
os.makedirs("model_png", exist_ok=True)
ok=fail=skip=0
for a in ACTIONS:
    c=a["code"]; path=f"model_png/{c}.png"
    if os.path.exists(path) and os.path.getsize(path)>2000:
        skip+=1; continue
    done=False
    for k in range(6):
        try:
            req=urllib.request.Request(MODEL_BASE+c+".png", headers=hdr)
            with urllib.request.urlopen(req, timeout=45) as r, open(path,"wb") as f:
                f.write(r.read())
            ok+=1; done=True; print("OK",c,os.path.getsize(path),flush=True); break
        except Exception as e:
            time.sleep(1.5)
    if not done:
        fail+=1; print("FAIL",c,flush=True)
print(f"=== done ok={ok} skip={skip} fail={fail} total={len(ACTIONS)} ===", flush=True)
