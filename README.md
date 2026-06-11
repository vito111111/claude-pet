# Claude Code 桌面宠物 🧡

一只跟着 Claude Code 状态联动的方块像素小宠物。形象是 Claude Code 的橘色"火花"小人，
**无论打开多少个 Claude Code 窗口，整个桌面只有这一只宠物**，它的状态是所有会话的聚合。

> Windows · Python 3.9+ · 纯 tkinter 矢量绘制，**零图片素材、零第三方依赖**。

## 快速开始

```powershell
# 1) 克隆
git clone https://github.com/<your-name>/claude-pet.git
cd claude-pet

# 2) 先自测预览（不依赖 Claude Code，看几秒动画即可）
python pet.py --selftest

# 3) 接入 Claude Code：把下面 hooks 合并进 ~/.claude/settings.json
#    （把 <DIR> 换成本仓库的绝对路径）
```

```jsonc
// ~/.claude/settings.json  →  "hooks" 字段（与已有 hook 合并，勿覆盖）
{
  "hooks": {
    "SessionStart":     [{ "hooks": [{ "type": "command", "command": "powershell -NoProfile -File \"<DIR>\\ensure_pet.ps1\"" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "python \"<DIR>\\hook_status.py\" working" }] }],
    "Stop":             [{ "hooks": [{ "type": "command", "command": "python \"<DIR>\\hook_status.py\" done" }] }],
    "SessionEnd":       [{ "hooks": [{ "type": "command", "command": "python \"<DIR>\\hook_status.py\" end" }] }]
  }
}
```

hooks 在**新的** Claude Code 会话才生效。`ensure_pet.ps1` 与 `hook_status.py` 均已可移植
（自动定位脚本目录与 `pythonw.exe`），换机器无需改代码。

## 三种状态

| 状态 | 触发 | 表现 |
|------|------|------|
| **工作中** working | 任意一个会话正在干活 | 橘色小人趴在键盘上"哒哒哒"打字 |
| **完成提醒** done | 任意一个会话结束（Stop） | 小人由橘色 **变绿**、轻轻跳动 + ✓ 徽章，**冒泡弹出刚完成的窗口名**（取工作目录最后一段，如 `claude-pet 完成`）+ **钉钉"新消息"提示音**；保持 **5 秒**后回到 idle/working |

> 提示音：把任意 `.wav` 放成 `sounds\done.wav` 即可（仓库不附带音频，见 `sounds/README.md`）。
> 若该文件不存在，会依次回退到系统 `tada.wav` → 合成提示音，因此不放也能正常运行。
> （`make_cough.py` 可生成一个"咳咳"咳嗽音作为 `done.wav`。）
| **空闲** idle | 所有会话都空闲 / 完成 5 秒后且无人在干活 | 安静摇摆；空闲满 60s 会变出分身踢足球解闷 |

## 聚合规则（单只宠物如何代表多个窗口）

- 只要**有任一会话刚结束**（working→done 的边沿）→ 立即变绿 + 冒泡弹出那个窗口名 + 响铃，持续 **5 秒**；
- 5 秒后：若**仍有会话在干活** → working，否则 → idle。

## 工作原理

```
多个 Claude Code 会话 ──(hooks)──▶ hook_status.py ──写──▶ ~/.claude/pet_status/<session>.json
                                                              │
                                              pet.py 每 0.5s 轮询此目录
                                                              │
                              聚合所有会话状态 ──▶ 桌面唯一一只宠物（透明 / 置顶 / 可拖动）
```

- **hook_status.py**：被 Claude Code 的 hooks 调用，把当前会话状态写成一个 JSON 文件
  （按 `session_id` 区分，含 `cwd` 供冒泡显示窗口名），并确保宠物主程序在后台运行。
- **pet.py**：单进程、单窗口。轮询所有会话状态文件后聚合成一只宠物的状态，
  并对"刚完成"的会话做边沿检测来触发变绿+冒泡+响铃。
  用本地端口 50573 做单例守卫，重复启动会自动退出。纯 tkinter 矢量绘制像素图，**无需任何图片素材**。

## 已接入的 hooks（写在 `~/.claude/settings.json`）

| Hook 事件 | 命令 | 含义 |
|-----------|------|------|
| `SessionStart`     | `hook_status.py idle`    | 会话开始：拉起宠物 + 空闲 |
| `UserPromptSubmit` | `hook_status.py working` | 你发话：进入打字模式 |
| `Stop`             | `hook_status.py done`    | Claude 答完：变绿提醒 |
| `SessionEnd`       | `hook_status.py end`     | 会话结束：移除宠物 |

> 已自动合并进现有 settings.json（保留了原有的 claude-voice 启动 hook）。

## 立即生效

hooks 在**新的** Claude Code 会话才会触发。要在当前会话先看到效果，可手动启动一次：

```powershell
Start-Process "C:\Users\megarobo-BJ\AppData\Local\Programs\Python\Python313\pythonw.exe" `
  -ArgumentList "C:\Users\megarobo-BJ\claude-pet\pet.py"
```

## 开机自启（常驻）

已在「启动」文件夹放了快捷方式 `ClaudePet.lnk`，登录 Windows 时静默拉起：

```
pythonw.exe pet.py --resident
```

- `--resident` **常驻模式**：取消「无会话 600 秒自动退出」，进程一直待命。
- 没有任何 Claude 会话时，显示**一只晒太阳的"看家"宠物**（`__resident__`，墨镜+太阳伞）；
  一旦有真实会话，看家宠物让位给各会话宠物，会话都结束后又回来。
- 单例端口 50573 保证常驻进程与 hook 临时拉起的进程不会重复（先占端口者存活）。

快捷方式位置：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ClaudePet.lnk`
（想取消开机自启，删除该快捷方式即可。）

## 交互

- **左键拖动**：把宠物拖到屏幕任意位置
- **右键**：菜单 →「退出」
- 默认停在屏幕右下角

## 自测预览（不依赖 Claude Code）

```powershell
python C:\Users\megarobo-BJ\claude-pet\pet.py --selftest
```

唯一一只宠物循环演示 working → done(带冒泡) → idle，约数秒后自动关闭。

## 可调参数（pet.py 顶部）

- `DONE_HOLD_SEC = 5`   完成提醒(绿色+冒泡)保持多久后回到 idle/working
- `FRAME_MS = 90`       动画速度
- `NO_SESSION_EXIT_SEC = 600`  无会话多久后主程序自动退出（**仅非常驻模式**；`--resident` 下永不自退）
