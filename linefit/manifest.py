# -*- coding: utf-8 -*-
"""《健身環大冒險》43 个「健身技能」动作清单。

数据源：Nintendo 香港官网 ringadventure/list 页面。每个动作在官网都有一张
真人高清演示照(model/<code>.png)，是提取骨架的权威单姿势来源。

字段：code, cn, en, cat(muscle/rhythm/yoga), part(锻炼部位), tags(效果标签),
      anim(rep=往复计次 / hold=静态保持), tip(跟练提示)
图片 URL = MODEL_BASE + code + ".png"
"""
MODEL_BASE = "https://www.nintendo.com/hk/switch/ringadventure/assets/img/list/model/"

ACTIONS = [
    # ---------------- 肌肉訓練系列 ----------------
    dict(code="bp",  cn="背面推壓",     en="Back Press",        cat="muscle", part="豎脊肌/上臂三頭肌", tags=["緊實上臂","改善儀態","改善肩痠"], anim="rep",  tip="Ring-Con 移到頭後方，用力向上推"),
    dict(code="up",  cn="高舉雙臂推入", en="Overhead Press",    cat="muscle", part="三角肌",          tags=["緊實上臂","提胸","改善肩痠"],    anim="rep",  tip="雙臂用力向上推舉，頂端停一下"),
    dict(code="unp", cn="向下推壓",     en="Front Press",       cat="muscle", part="胸大肌",          tags=["提胸"],                         anim="rep",  tip="Ring-Con 移到胸前下方，向內擠壓"),
    dict(code="rbp", cn="圓環箭",       en="Bow Pull",          cat="muscle", part="上臂三頭肌/背闊肌", tags=["緊實上臂","強化背肌","強化軀幹"], anim="rep",  tip="像拉弓一樣拉開 Ring-Con"),
    dict(code="sp",  cn="肩部推壓",     en="Shoulder Press",    cat="muscle", part="豎脊肌",          tags=["緊實上臂","改善儀態","改善肩痠"], anim="rep",  tip="Ring-Con 放到肩上，向上推"),
    dict(code="tk",  cn="三頭肌",       en="Tricep Kickback",   cat="muscle", part="豎脊肌/上臂三頭肌", tags=["緊實上臂"],                     anim="rep",  tip="手肘不動，上下揮動 Ring-Con"),
    dict(code="sq",  cn="深蹲",         en="Squat",             cat="muscle", part="股四頭肌",        tags=["緊實美腿","提臀","燃燒脂肪"],    anim="rep",  tip="像坐椅子般下蹲，膝蓋別超腳尖"),
    dict(code="ws",  cn="寬深蹲",       en="Wide Squat",        cat="muscle", part="臀大肌/臀小肌",   tags=["緊實美腿","提臀","燃燒脂肪"],    anim="rep",  tip="雙腿大幅張開做深蹲"),
    dict(code="bs",  cn="高舉雙臂深蹲", en="Overhead Squat",    cat="muscle", part="三角肌/臀大肌",   tags=["緊實美腿","提臀","燃燒脂肪"],    anim="rep",  tip="雙臂高舉，同時做深蹲"),
    dict(code="bsb", cn="高舉雙臂側彎", en="Overhead Side Bend",cat="muscle", part="腹斜肌/三角肌",   tags=["緊實腰部","強化軀幹","緊實上臂"], anim="rep",  tip="雙臂上舉，向左右側彎拉伸腰側"),
    dict(code="bct", cn="高舉雙臂扭動", en="Overhead Lunge Twist",cat="muscle",part="三角肌/腹斜肌", tags=["緊實腰部","緊實美腿","強化軀幹"], anim="rep",  tip="雙臂上舉，扭動上半身"),
    dict(code="bo",  cn="俯身划船",     en="Pendulum Bend",     cat="muscle", part="豎脊肌/腹斜肌",   tags=["緊實腰部","強化下半身","強化軀幹"],anim="rep", tip="上半身前傾，Ring-Con 舉向左右"),
    dict(code="bm",  cn="高舉雙臂晨式", en="Overhead Bend",     cat="muscle", part="豎脊肌",          tags=["強化軀幹","改善儀態","強化背肌"], anim="rep",  tip="雙臂上舉，緩慢向前傾身"),
    dict(code="thp", cn="大腿推壓",     en="Thigh Press",       cat="muscle", part="臀小肌",          tags=["緊實美腿","強化下半身","改善儀態"],anim="rep", tip="坐地，用大腿夾壓 Ring-Con"),
    dict(code="ktc", cn="抱膝式",       en="Knee-to-Chest",     cat="muscle", part="腹直肌/髂腰肌",   tags=["改善小腹","緊實上臂","強化軀幹"], anim="rep",  tip="坐姿伸腿，屈膝靠近胸口"),
    dict(code="fopu",cn="往前推壓",     en="Seated Forward Press",cat="muscle",part="腹直肌/上臂三頭肌",tags=["緊實上臂","改善小腹","提升柔軟度"],anim="rep",tip="坐地張腿，向前推 Ring-Con"),
    dict(code="hlp", cn="提臀",         en="Hip Lift",          cat="muscle", part="腹横肌/腿后腱",   tags=["緊實美腿","提臀","強化軀幹"],    anim="rep",  tip="平躺，抬起腰部夾緊臀部"),
    dict(code="pla", cn="平板支撐",     en="Plank",             cat="muscle", part="腹横肌",          tags=["改善小腹","強化軀幹","改善儀態"], anim="hold", tip="雙肘貼地，身體成一直線撐住"),
    dict(code="lr",  cn="提腿",         en="Leg Raise",         cat="muscle", part="腹直肌/髂腰肌",   tags=["改善小腹","強化軀幹"],          anim="rep",  tip="坐地伸腿，抬高雙腿"),
    dict(code="olg", cn="腿部開合",     en="Open & Close Leg Raise",cat="muscle",part="腹直肌/臀小肌",tags=["改善小腹","緊實美腿","提臀"],   anim="rep",  tip="坐地抬腿，大幅開合雙腿"),
    # ---------------- 節奏系列 ----------------
    dict(code="swtw",cn="甩手",         en="Standing Twist",    cat="rhythm", part="腹斜肌/豎脊肌",   tags=["緊實腰部","燃燒脂肪"],          anim="rep",  tip="向左右大幅扭動上半身"),
    dict(code="bash",cn="高舉雙臂扭腰", en="Overhead Hip Shake",cat="rhythm", part="腹斜肌/腹横肌",   tags=["緊實腰部","燃燒脂肪","緊實上臂"], anim="rep",  tip="雙臂上舉，左右擺動腰部"),
    dict(code="batw",cn="扭動手臂",     en="Overhead Arm Twist",cat="rhythm", part="上臂三頭肌/三角肌",tags=["緊實上臂","改善肩痠","強化軀幹"], anim="rep", tip="雙手向上伸直，扭動手臂"),
    dict(code="baar",cn="轉轉手臂",     en="Overhead Arm Spin", cat="rhythm", part="三角肌/上臂三頭肌",tags=["緊實上臂","改善肩痠","改善儀態"], anim="rep", tip="Ring-Con 舉過頭畫圓"),
    dict(code="twab",cn="俄式扭腰",     en="Russian Twist",     cat="rhythm", part="腹直肌/腹斜肌",   tags=["緊實腰部","改善小腹","強化軀幹"], anim="rep",  tip="屈膝坐地，左右扭動上半身"),
    dict(code="alt", cn="踢腿",         en="Flutter Kick",      cat="rhythm", part="髂腰肌/腹直肌",   tags=["改善小腹","緊實美腿"],          anim="rep",  tip="平躺，交互上下擺動雙腿"),
    dict(code="riup",cn="抬放Ring-Con", en="Seated Ring Raise", cat="rhythm", part="腹直肌/髂腰肌",   tags=["改善小腹","緊實美腿","強化軀幹"], anim="rep",  tip="屈膝坐地，上下揮動 Ring-Con"),
    dict(code="mocl",cn="登山式",       en="Mountain Climber",  cat="rhythm", part="髂腰肌/上臂三頭肌",tags=["緊實美腿","緊實上臂","提臀"],   anim="rep",  tip="撐地，雙腿交互向胸口收"),
    dict(code="scle",cn="剪刀式",       en="Leg Scissors",      cat="rhythm", part="腹直肌/臀小肌",   tags=["改善小腹","緊實美腿","燃燒脂肪"], anim="rep",  tip="坐地微抬腿，快速擺動雙腿"),
    dict(code="knup",cn="抬抬大腿",     en="Knee Lift",         cat="rhythm", part="股四頭肌/髂腰肌", tags=["改善小腹","緊實美腿","燃燒脂肪"], anim="rep",  tip="配合節奏連續抬腿"),
    dict(code="stup",cn="踏步",         en="Side Step",         cat="rhythm", part="臀小肌/上臂三頭肌",tags=["緊實上臂","緊實美腿","燃燒脂肪"], anim="rep",  tip="左右踏步，同時上下揮 Ring-Con"),
    dict(code="uodoco",cn="連續抬放",   en="Ring Raise Combo",  cat="rhythm", part="臀小肌/上臂三頭肌",tags=["緊實美腿","提臀","燃燒脂肪"],   anim="rep",  tip="配合節奏連續上下揮 Ring-Con"),
    dict(code="knupco",cn="連續抬腿",   en="Knee-Lift Combo",   cat="rhythm", part="髂腰肌",          tags=["緊實美腿","提臀","燃燒脂肪"],   anim="rep",  tip="抬腿與高舉 Ring-Con 組合"),
    # ---------------- 瑜珈系列 ----------------
    dict(code="yoch", cn="椅子姿勢",    en="Chair Pose",        cat="yoga",   part="股四頭肌/豎脊肌", tags=["強化下半身","強化軀幹","提升耐力"],anim="hold", tip="降低重心，慢慢上下揮 Ring-Con"),
    dict(code="yota", cn="立木姿勢",    en="Tree Pose",         cat="yoga",   part="腹横肌/豎脊肌",   tags=["緊實美腿","強化下半身","改善儀態"],anim="hold", tip="單腳站立，雙手上舉保持平衡"),
    dict(code="yocht",cn="合頁姿勢",    en="Hinge Pose",        cat="yoga",   part="豎脊肌/三角肌",   tags=["改善肩痠","緊實美腿","改善腰痛"], anim="hold", tip="上身前傾，慢慢上下擺動單臂"),
    dict(code="yoneta",cn="扭轉側角姿勢",en="Revolved Crescent Lunge",cat="yoga",part="腹斜肌/豎脊肌", tags=["緊實腰部","強化下半身","強化軀幹"],anim="hold",tip="弓步張腿，慢慢扭動上半身"),
    dict(code="yoeione",cn="英雄1的姿勢",en="Warrior I Pose",   cat="yoga",   part="背闊肌/豎脊肌",   tags=["強化下半身","燃燒脂肪","改善儀態"],anim="hold",tip="前後弓步，向側傾曲上半身"),
    dict(code="yoeitw",cn="英雄2的姿勢",en="Warrior II Pose",   cat="yoga",   part="旋轉肌群/三角肌", tags=["提胸","緊實上臂","改善肩痠"],   anim="hold", tip="大幅張腿張臂，慢慢扭動雙臂"),
    dict(code="yoeith",cn="英雄3的姿勢",en="Warrior III Pose",  cat="yoga",   part="髂腰肌/臀大肌",   tags=["燃燒脂肪","強化軀幹","提升耐力"], anim="hold", tip="單腳站立，上半身向前傾成一線"),
    dict(code="yoog", cn="扇形姿勢",    en="Fan Pose",          cat="yoga",   part="腹斜肌/豎脊肌",   tags=["緊實腰部","提升柔軟度","改善肩痠"],anim="hold", tip="坐地，上半身慢慢向側傾"),
    dict(code="yohu", cn="船式",        en="Boat Pose",         cat="yoga",   part="腹直肌/髂腰肌",   tags=["改善小腹","強化軀幹","提升耐力"], anim="hold", tip="坐地，雙手後垂、雙腿前伸成 V"),
    dict(code="yoor", cn="摺疊軀體姿勢",en="Standing Forward Fold",cat="yoga", part="豎脊肌/腿后腱",   tags=["緊實上臂","改善肩痠","提升柔軟度"],anim="hold",tip="手持 Ring-Con 從背後慢慢前傾"),
]

BY_CODE = {a["code"]: a for a in ACTIONS}
