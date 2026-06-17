# linefit · 线条人健身引导

把 Switch《健身環大冒險》43 个健身动作，用**线条勾勒人体轮廓**（stick figure）的方式
在桌宠上复现，作为「久坐/驼背/压力」时的跟练引导。

## 它怎么来的
1. **抓官网**：Nintendo 香港 `ringadventure/list`，整理 60 种健身清单
   → `铃力士官网健身内容-学习笔记.md`。
2. **取姿势源**：每个动作官网都有一张**真人高清演示照**（关键帧、白底、全身），
   比录屏里的滚动小图干净得多 → 缓存到 `model_png/<code>.png`。
   > ⚠️ `model_png/`、`frames/` 为任天堂官网版权素材，**不随仓库分发**；运行时用不到
   > （下游只依赖已抽好的 `data/actions_poses.json`）。需重建动作库时自行从官网缓存。
3. **抽骨架**：MediaPipe PoseLandmarker（Tasks API）逐张抽 33 关键点
   → 归一化成 15 点火柴人骨架（髋中心原点、躯干长为 1、与分辨率无关）。
4. **复现**：往复动作在「中性站姿 ↔ 关键姿势」间正弦插值成一次 rep；
   瑜珈静态姿势加呼吸起伏。线条 + 关节点 + 头圆即"线条人"。

## 文件
| 文件 | 作用 |
|---|---|
| `manifest.py` | 43 动作清单（中英名/系列/部位/标签/动画类型/要领/图片URL） |
| `stickfigure.py` | 骨架格式 + MediaPipe→15点映射 + tkinter 线条渲染 |
| `build_library.py` | 逐张抽骨架 → `data/actions_poses.json` |
| `linefit.py` | 动作播放器（pose_at 插值）+ **独立预览** |
| `video_analyze.py` | 对录屏跑姿态分析 → `data/video_*.json`（见下） |
| `data/actions_poses.json` | ★ 动作库：neutral + 43 动作骨架，下游唯一依赖 |
| `../linefit_player.py` | 桌宠 drop-in 会话（同 `exercise.ExerciseSession` 接口） |

## 用法
```bash
# 独立预览（看线条人跟练）
python linefit.py full            # 全身唤醒
python linefit.py yoga            # 瑜珈系列
python linefit.py all             # 全部 43 式依次演示

# 重建动作库（改了 manifest 或想换 full/heavy 模型时）
python build_library.py
```
桌宠侧：`pet.py` 已改为优先 `import linefit_player`，缺库时自动回退旧版 `exercise.py`。
桌宠三套 routine（full / neck_shoulder / breathe）映射到站姿友好的动作子集。

## 关于录屏视频
`G:\录屏视频\任天堂健身动作.mp4` 是官网列表页的**滚动录屏**：261 采样帧中仅 46 帧
能检到完整人物（滚动时模特照多为半截/移动），故不作姿态主源，仅留分析数据
（`data/video_pose_track.json` 逐帧轨迹、`data/video_timeline.json` 动作时间线）佐证。
真正的姿态来自官网源照片，质量高得多（检测可见度 0.96–0.99）。

## 依赖
`mediapipe>=0.10`（Tasks API）、`opencv-python`、`numpy`、`pose_landmarker_lite.task`
（模型文件较大未入库，首次重建动作库时从 MediaPipe 官方下载放到本目录）。
纯本地运行，不联网、无大模型。
