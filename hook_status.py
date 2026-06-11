# -*- coding: utf-8 -*-
"""
Claude Code 宠物状态写入器 —— 由 hooks 调用。

用法 (在 hook 的 command 中):
    python hook_status.py working
    python hook_status.py done
    python hook_status.py idle
    python hook_status.py end

Claude Code 会通过 stdin 传入事件 JSON (含 session_id / cwd 等)。
本脚本据此把状态写入 ~/.claude/pet_status/<session_id>.json，
供 pet.py 轮询渲染。同时在需要时确保宠物管理进程已启动。
"""

import os
import sys
import json
import time
import subprocess

STATUS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "pet_status")
HEARTBEAT_FILE = os.path.join(STATUS_DIR, ".heartbeat")  # 渲染器存活心跳
HERE = os.path.dirname(os.path.abspath(__file__))
PET_PY = os.path.join(HERE, "pet.py")
HEARTBEAT_FRESH_SEC = 6   # 心跳新鲜 -> 渲染器在跑，无需重复拉起


def read_event():
    """从 stdin 读取 Claude Code 的事件 JSON（可能为空）。

    注意：Claude Code 以分离的 pythonw.exe 跑 async hook，此进程没有控制台，
    sys.stdin 可能为 None —— 直接 .read() 会抛 AttributeError。必须兜住所有
    异常，否则脚本在写状态文件前就崩溃，宠物永远收不到状态。"""
    try:
        if sys.stdin is None:
            return {}
        raw = sys.stdin.read()
        if raw and raw.strip():
            return json.loads(raw)
    except Exception:
        pass
    return {}


def _renderer_alive():
    """心跳文件 <HEARTBEAT_FRESH_SEC 秒新鲜则认为渲染器在跑。"""
    try:
        with open(HEARTBEAT_FILE, "r", encoding="utf-8") as f:
            return (time.time() - float(f.read().strip())) < HEARTBEAT_FRESH_SEC
    except (OSError, ValueError):
        return False


def ensure_manager_running():
    """以分离方式启动宠物管理进程；pet.py 自带单例守卫，重复启动无害。
    高频 hook(如 PreToolUse)调用时，若心跳新鲜则直接跳过，避免每次工具调用都 spawn 进程。"""
    if _renderer_alive():
        return
    exe = sys.executable or "python"
    pyw = exe.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = exe
    try:
        flags = 0
        if os.name == "nt":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            flags = 0x00000008 | 0x00000200
        subprocess.Popen([pyw, PET_PY, "--resident"], creationflags=flags,
                         close_fds=True, cwd=HERE)
    except OSError:
        pass


def main():
    status = sys.argv[1] if len(sys.argv) > 1 else "idle"
    event = read_event()
    session_id = (event.get("session_id")
                  or os.environ.get("CLAUDE_CODE_SESSION_ID")
                  or os.environ.get("CLAUDE_SESSION_ID")
                  or "default")
    cwd = event.get("cwd") or os.getcwd()

    os.makedirs(STATUS_DIR, exist_ok=True)
    path = os.path.join(STATUS_DIR, f"{session_id}.json")

    payload = {
        "session_id": session_id,
        "status": status,
        "cwd": cwd,
        "ts": time.time(),
    }
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass

    # end 写"墓碑"(status=end)而非直接删文件：渲染器据此把宠物立刻撤掉，并登记到
    # 已结束集合，避免 transcript mtime 仍新鲜时又把宠物复活；墓碑由渲染器稍后清理。
    # 仅在有真实活动(非结束)时才确保管理进程在跑——会话关闭时不该再拉起宠物。
    if status != "end":
        ensure_manager_running()

    # 不阻塞 Claude Code：始终干净退出
    sys.exit(0)


if __name__ == "__main__":
    main()
