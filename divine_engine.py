# -*- coding: utf-8 -*-
"""
占卜引擎：本地语料库抽取 + 2 小时结果锁定 + 可选 `claude -p` 增强/开放生成。

仅两种玩法：
  iching  易经卦象 —— 点击起卦，头顶核心卦词(乾卦…)，小字卦辞/解读
  shijing 诗经摇签 —— 摇签筒抽签，四字签题 + 诗经原句

设计要点：
  - 纯标准库，零 pip 依赖；Claude 增强通过 subprocess 调用本地 `claude` CLI，免 API key。
  - 【2 小时锁定】任一玩法点击后，结果(含 Claude 解读)写入 cache.json 并锁定 LOCK_SEC(2h)。
    期内再点同一玩法 -> 返回同一缓存结果(不再调用 claude，完全一致)。
    force=True(“再抽一次”)显式重抽并重置 2h 窗口。
  - 【内容库开放/自生长】接通 claude 时：
      * 卦象/签的解读由 claude 现生成(≤20 字)，库内文案为离线兜底；
      * shijing 签库会在后台由 claude 校验生成“新签”追加到 ~/.divination-pet/shijing_generated.json，
        与基础库合并参与抽取 —— 越用越丰富(本库 40 签为种子，非封闭上限)。
  - divine_local() 先返回本地库结果(离线即完整可用)，claude 解读为可选 claude_reading 字段，
    由 UI 在后台线程拿到后补显示；调不通则静默回退。
"""

import os
import re
import sys
import json
import time
import shutil
import hashlib
import datetime
import subprocess

# ---------------------------------------------------------------- 路径
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
USER_DIR = os.path.join(os.path.expanduser("~"), ".divination-pet")
CONFIG_FILE = os.path.join(USER_DIR, "config.json")
CACHE_FILE = os.path.join(USER_DIR, "cache.json")
SHIJING_GROW_FILE = os.path.join(USER_DIR, "shijing_generated.json")  # claude 生成的新签(自生长)

LOCK_SEC = 2 * 3600           # 结果锁定窗口：2 小时
GROW_MIN_INTERVAL = 6 * 3600  # 诗经签自生长最小间隔(节流)

MODES = ("iching", "shijing")
MODE_LABELS = {"iching": "易经卦象", "shijing": "诗经摇签"}

DEFAULT_CONFIG = {
    "use_claude": True,         # Claude 增强开关(≤20 字现代解读)
    "open_generate": True,      # 接通 claude 时允许后台生成新诗经签(自生长)
    "daily_reminder": False,    # 每日定时弹一签(默认关，尊重「手动占卜」)
    "reminder_time": "09:00",
    "reminder_mode": "shijing", # 提醒时弹哪种：shijing / iching
}


# ---------------------------------------------------------------- 配置/缓存读写
def _ensure_user_dir():
    os.makedirs(USER_DIR, exist_ok=True)


def load_config():
    _ensure_user_dir()
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    _ensure_user_dir()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_cache(cache):
    _ensure_user_dir()
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ---------------------------------------------------------------- 工具
def _load_data(name):
    with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _rng(*parts):
    """由若干字符串拼出『跨进程稳定』的随机源(不依赖 PYTHONHASHSEED)。"""
    import random
    key = "|".join(str(p) for p in parts)
    seed = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)
    return random.Random(seed)


# ---------------------------------------------------------------- 易经
def _divine_iching(cfg, rng):
    d = _load_data("iching.json")
    hx = rng.choice(d["hexagrams"])
    sections = [
        ("卦辞", hx["ci"]),
        ("解读", hx["reading"]),                       # 详细内容(小字) / 离线兜底
    ]
    laozi = hx.get("laozi", "")
    if laozi:
        sections.append((f"道德经·{hx.get('laozi_ch', '')}", laozi))  # 与卦义相印的道德经
    return {
        "mode": "iching",
        "icon": hx["symbol"],
        "title": f"{hx['symbol']} {hx['name']}卦",     # 核心卦词(大字)
        "subtitle": hx["gua"],
        "sections": sections,
        "lucky": {},
        "footer": "卦象示其势，道德经明其理，趋避在人心。",
        "_seed": {"name": hx["name"], "gua": hx["gua"], "ci": hx["ci"], "laozi": laozi},
    }


# ---------------------------------------------------------------- 诗经摇签
def _load_shijing_signs():
    """基础诗经签库 + claude 自生长签库(去重合并)。"""
    base = _load_data("shijing.json").get("signs", [])
    grown = []
    try:
        with open(SHIJING_GROW_FILE, "r", encoding="utf-8") as f:
            grown = json.load(f).get("signs", [])
    except (OSError, ValueError):
        grown = []
    seen = {(s.get("title"), s.get("poem")) for s in base}
    merged = list(base)
    for s in grown:
        k = (s.get("title"), s.get("poem"))
        if k not in seen:
            seen.add(k)
            merged.append(s)
    return merged


def _divine_shijing(cfg, rng):
    """诗经摇签：四字签题 + 诗经原句。等概率从(基础库+自生长库)抽一签。"""
    signs = _load_shijing_signs()
    s = rng.choice(signs)
    return {
        "mode": "shijing",
        "icon": "🎋",
        "title": s["title"],                          # 四字签题(大字)
        "subtitle": f"{s.get('level', '')} · {s.get('theme', '')}".strip(" ·"),
        "sections": [
            ("签诗", s["poem"]),                       # 诗经原句(小字)
            ("出处", s.get("source", "")),
        ],
        "lucky": {},
        "footer": s.get("jie", "签是缘起，路在脚下。"),  # 离线兜底解
        "_seed": {"title": s["title"], "level": s.get("level", ""),
                  "poem": s["poem"], "source": s.get("source", "")},
    }


_BUILDERS = {
    "iching": _divine_iching,
    "shijing": _divine_shijing,
}


# ---------------------------------------------------------------- 2 小时锁定缓存
def _cache_key(mode, cfg):
    return mode   # 两种玩法均不依赖个人参数


def _cache_get(mode, cfg):
    cache = _load_cache()
    ent = cache.get(_cache_key(mode, cfg))
    if isinstance(ent, dict) and ent.get("expires_at", 0) > time.time():
        return ent.get("result")
    return None


def _cache_put(mode, cfg, result):
    cache = _load_cache()
    now = time.time()
    cache[_cache_key(mode, cfg)] = {"result": result, "expires_at": now + LOCK_SEC}
    for k in list(cache.keys()):
        v = cache[k]
        if isinstance(v, dict) and "expires_at" in v and v["expires_at"] <= now:
            cache.pop(k, None)
    _save_cache(cache)


def cache_put_reading(mode, cfg, reading):
    """claude 解读到达后写回缓存，使 2h 窗口内的重复点击也带同一解读。"""
    cache = _load_cache()
    ent = cache.get(_cache_key(mode, cfg))
    if isinstance(ent, dict) and isinstance(ent.get("result"), dict):
        ent["result"]["claude_reading"] = reading
        _save_cache(cache)


# ---------------------------------------------------------------- 对外主函数
def divine_local(mode, cfg, force=False):
    """产出本地库结果(同步、即时)。

    非 force：命中未过期缓存则直接返回(2h 锁定，含已缓存的 claude_reading)。
    force / 未命中：现抽并写入缓存，锁定 2h。
    """
    if mode not in _BUILDERS:
        mode = "shijing"
    if not force:
        hit = _cache_get(mode, cfg)
        if hit:
            hit = dict(hit)
            hit["_cached"] = True
            return hit
    rng = _rng(mode, time.time_ns(), os.getpid())
    result = _BUILDERS[mode](cfg, rng)
    _cache_put(mode, cfg, result)
    result["_cached"] = False
    return result


# ---------------------------------------------------------------- Claude 定位/调用
def find_claude():
    """定位本地 claude CLI(npm 全局安装)。返回可执行路径或 None。"""
    for name in ("claude", "claude.cmd", "claude.exe"):
        p = shutil.which(name)
        if p:
            return p
    candidates = [
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude"),
        os.path.join(os.environ.get("ProgramFiles", ""), "nodejs", "claude.cmd"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def claude_available():
    return find_claude() is not None


def _run_claude(prompt, timeout):
    exe = find_claude()
    if not exe:
        return None
    if exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c", exe, "-p", prompt]
    else:
        cmd = [exe, "-p", prompt]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    text = (proc.stdout or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
    return text or None


# ---------------------------------------------------------------- Claude 解读(≤20字)
def _prompt_short(result, cfg):
    mode = result.get("mode")
    seed = result.get("_seed", {})
    if mode == "iching":
        return (
            "你是一位贯通易经与道德经的解卦人。用户抽到「{name}卦」（{gua}），卦辞「{ci}」，"
            "与之相印的道德经云：「{laozi}」。请用不超过20字给出一句融合卦义与道德经智慧、"
            "贴近日常且积极中肯的现代解读，不要复述原文。只输出这一句话。"
        ).format(name=seed.get("name", ""), gua=seed.get("gua", ""),
                 ci=seed.get("ci", ""), laozi=seed.get("laozi", ""))
    return (
        "你是一位温雅的解签人。用户摇得「{title}」签（{level}），签诗出自{source}：「{poem}」。"
        "请用不超过20字给出一句贴近日常、温暖中肯的现代白话解读，呼应签题与吉凶，不复述原句。"
        "只输出这一句话。"
    ).format(title=seed.get("title", ""), level=seed.get("level", ""),
             source=seed.get("source", ""), poem=seed.get("poem", ""))


def enhance_with_claude(result, cfg, timeout=30):
    """生成 ≤20 字现代解读。失败/超时/无输出一律返回 None。"""
    text = _run_claude(_prompt_short(result, cfg), timeout)
    if not text:
        return None
    text = text.splitlines()[0].strip().strip("“”\"'。").strip()
    if len(text) > 24:
        text = text[:24]
    return text or None


# ---------------------------------------------------------------- 诗经签 自生长(开放生成)
_SOURCE_RE = re.compile(r"^《诗经·[一-龥]+·[一-龥]+》$")
_VALID_LEVELS = {"上上签", "上吉签", "中吉签", "中平签", "末吉签", "下下签"}


def _validate_generated_sign(s, existing_keys):
    if not isinstance(s, dict):
        return None
    title = str(s.get("title", "")).strip()
    poem = str(s.get("poem", "")).strip()
    source = str(s.get("source", "")).strip()
    level = str(s.get("level", "")).strip()
    jie = str(s.get("jie", "")).strip()
    theme = str(s.get("theme", "")).strip() or "运势"
    if len(title) != 4 or not all('一' <= ch <= '鿿' for ch in title):
        return None
    if not (6 <= len(poem) <= 50):
        return None
    if not _SOURCE_RE.match(source):
        return None
    if level not in _VALID_LEVELS:
        return None
    if (title, poem) in existing_keys:
        return None
    if not jie:
        jie = "签意自在，宜静心体会。"
    return {"title": title, "level": level, "theme": theme,
            "poem": poem, "source": source, "jie": jie[:20], "by": "claude"}


def maybe_grow_shijing(cfg, timeout=40):
    """后台调用：让 claude 生成 1 支全新诗经签，校验通过后追加到自生长库。节流。"""
    if not cfg.get("use_claude", True) or not cfg.get("open_generate", True):
        return None
    if not claude_available():
        return None
    cache = _load_cache()
    if time.time() - cache.get("_last_grow_ts", 0) < GROW_MIN_INTERVAL:
        return None

    existing = _load_shijing_signs()
    keys = {(s.get("title"), s.get("poem")) for s in existing}
    used_titles = "、".join(s.get("title", "") for s in existing[-12:])
    prompt = (
        "你在为一只占卜桌宠扩充『诗经签』签库。请新造 1 支签，"
        "严格使用《诗经》中真实存在的诗句(篇名准确)，不得杜撰诗句或篇名。\n"
        "输出严格的 JSON(不要任何多余文字、不要代码块)，字段：\n"
        '{"title":"四字签题","level":"上上签|上吉签|中吉签|中平签|末吉签|下下签",'
        '"theme":"主题二到四字","poem":"诗经原句(可一到两句)",'
        '"source":"《诗经·X风/雅/颂·篇名》","jie":"≤20字白话签解"}\n'
        f"避免与这些签题重复：{used_titles}。\n"
        "title 必须是四个汉字且能凝练 poem 的意象；source 必须形如《诗经·周南·关雎》。"
    )
    text = _run_claude(prompt, timeout)
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except ValueError:
        return None
    sign = _validate_generated_sign(obj, keys)
    if not sign:
        return None

    try:
        with open(SHIJING_GROW_FILE, "r", encoding="utf-8") as f:
            grow = json.load(f)
    except (OSError, ValueError):
        grow = {"_note": "claude 自生长诗经签(经校验)。与 data/shijing.json 合并参与抽取。",
                "signs": []}
    grow.setdefault("signs", []).append(sign)
    try:
        with open(SHIJING_GROW_FILE, "w", encoding="utf-8") as f:
            json.dump(grow, f, ensure_ascii=False, indent=2)
    except OSError:
        return None
    cache = _load_cache()
    cache["_last_grow_ts"] = time.time()
    _save_cache(cache)
    return sign


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    cfg = load_config()
    mode = sys.argv[1] if len(sys.argv) > 1 else "shijing"
    res = divine_local(mode, cfg, force=True)
    print(json.dumps({k: v for k, v in res.items() if not k.startswith("_")},
                     ensure_ascii=False, indent=2))
    print("\nclaude 可用:", claude_available(), "->", find_claude())
    if claude_available() and "--claude" in sys.argv:
        print("\n✨ Claude 解读:\n", enhance_with_claude(res, cfg))
