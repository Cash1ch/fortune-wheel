# -*- coding: utf-8 -*-
"""Звуки и вибрация. Звуки синтезируются при первом запуске (как в оригинале), внешние файлы не нужны.
При любом сбое (нет аудио, нет plyer) — тишина без падения приложения."""
import math
import os
import random
import struct
import time
import wave

RATE = 22050


def _write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples))


def _synth_tick():
    rnd = random.Random(7)
    n = int(RATE * 0.04)
    out = []
    for i in range(n):
        t = i / RATE
        env = math.exp(-t * 130.0)
        out.append((0.55 * math.sin(math.tau * 2200 * t) + 0.45 * (rnd.random() * 2 - 1)) * env * 0.9)
    return out


def _synth_win():
    notes = (523.25, 659.25, 783.99, 1046.5)          # до-ми-соль-до: победный перезвон
    total = int(RATE * 1.9)
    out = [0.0] * total
    for k, f in enumerate(notes):
        start = int(RATE * 0.11 * k)
        for i in range(total - start):
            t = i / RATE
            env = math.exp(-t * 3.2) * min(1.0, t * 200)
            v = math.sin(math.tau * f * t) + 0.35 * math.sin(math.tau * 2 * f * t) + 0.15 * math.sin(math.tau * 3 * f * t)
            out[start + i] += v * env * 0.25
    peak = max(1e-6, max(abs(s) for s in out))
    return [s * 0.85 / peak for s in out]


class Feedback:
    """Звук + вибрация. enabled — общий переключатель «Звук»."""

    TICK_MIN_GAP = 0.04      # не чаще 25 щелчков/с: на максимальной скорости штифтов ~90/с

    def __init__(self, folder):
        self.enabled = True
        self._pool, self._next, self._win = [], 0, None
        self._last_tick = 0.0
        self._last_vib = 0.0
        self._vib = None
        try:
            os.makedirs(folder, exist_ok=True)
            tick, win = os.path.join(folder, "tick.wav"), os.path.join(folder, "win.wav")
            if not os.path.exists(tick):
                _write_wav(tick, _synth_tick())
            if not os.path.exists(win):
                _write_wav(win, _synth_win())
            from kivy.core.audio import SoundLoader
            self._pool = [s for s in (SoundLoader.load(tick) for _ in range(4)) if s]
            self._win = SoundLoader.load(win)
        except Exception as e:  # noqa: BLE001
            print("Звук недоступен:", e)
        try:
            from plyer import vibrator
            self._vib = vibrator
        except Exception:  # noqa: BLE001
            self._vib = None

    def _vibrate(self, seconds):
        if self._vib is not None:
            try:
                self._vib.vibrate(seconds)
            except Exception:  # noqa: BLE001
                self._vib = None

    def tick(self, speed=100.0):
        now = time.monotonic()
        if now - self._last_tick < self.TICK_MIN_GAP:
            return
        self._last_tick = now
        if self.enabled and self._pool:
            snd = self._pool[self._next % len(self._pool)]
            self._next += 1
            try:
                snd.volume = max(0.15, min(1.0, speed / 400.0))
                snd.stop()
                snd.play()
            except Exception:  # noqa: BLE001
                pass
        if self.enabled and now - self._last_vib > 0.07:
            self._last_vib = now
            self._vibrate(0.008)

    def win(self):
        if self.enabled and self._win:
            try:
                self._win.stop()
                self._win.play()
            except Exception:  # noqa: BLE001
                pass
        if self.enabled:
            self._vibrate(0.25)
