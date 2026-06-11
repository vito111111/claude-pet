# -*- coding: utf-8 -*-
"""生成"咳咳"双声咳嗽提示音 -> sounds/done.wav（纯标准库，无需联网）。"""
import os
import wave
import array
import math
import random

SR = 16000
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sounds", "done.wav")


def cough(dur=0.18, amp=1.0, decay=26.0, cutoff=0.30, voice_f=170.0):
    """一声咳：带包络的低通噪声 + 一点低频"声带"成分。"""
    n = int(SR * dur)
    lp = 0.0
    out = []
    for i in range(n):
        t = i / SR
        # 快起音 + 指数衰减包络
        env = math.exp(-decay * t) * (1.0 - math.exp(-t / 0.004))
        noise = random.uniform(-1.0, 1.0)
        lp += cutoff * (noise - lp)               # 一阶低通，去掉刺耳高频
        voice = math.sin(2.0 * math.pi * voice_f * t)
        out.append((0.85 * lp + 0.15 * voice) * env * amp)
    return out


def main():
    random.seed(20240608)
    samples = []
    samples += cough(amp=1.00, voice_f=175, decay=24)      # 咳
    samples += [0.0] * int(SR * 0.11)                       # 间隔
    samples += cough(amp=0.82, voice_f=158, decay=27)       # 咳
    samples += [0.0] * int(SR * 0.04)

    peak = max(1e-3, max(abs(x) for x in samples))
    pcm = array.array(
        "h",
        [int(max(-1.0, min(1.0, x / peak * 0.95)) * 32767) for x in samples],
    )

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with wave.open(OUT, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote", OUT, "frames", len(pcm), "dur",
          round(len(pcm) / SR, 2), "s")


if __name__ == "__main__":
    main()
