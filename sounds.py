# -*- coding: utf-8 -*-
"""Звуки и вибрация (v2): у каждого стиля свой набор.

  classic — деревянный щелчок, фанфары, тёплый «пэд» на фоне
  nte     — электронные блипы, синтезаторное арпеджио, пульсирующий бас
  sakura  — щипок кото, глиссандо кото, ветряные колокольчики
  paws    — звон музыкальной шкатулки, мелодия + мягкое послезвучие, колыбельная

Звуки синтезируются при первом запуске стиля в фоновом потоке и кэшируются в папке приложения.
Щелчки штифтов на Android играет SoundPool (малая задержка), остальное — SoundLoader.
При любом сбое — тишина, без падения приложения.
"""
import math
import os
import random
import struct
import threading
import time
import wave

from kivy.clock import Clock, mainthread
from kivy.utils import platform

RATE = 16000
TAU = math.tau
VERSION = "v3"
THEMES = ("classic", "nte", "sakura", "paws")

# частоты нот (Гц)
N = {"D3": 146.83, "A2": 110.0, "C3": 130.81, "A3": 220.0, "B3": 246.94, "C4": 261.63, "D4": 293.66,
     "E4": 329.63, "F3": 174.61, "G3": 196.0, "G4": 392.0, "A4": 440.0, "B4": 493.88, "C5": 523.25,
     "D5": 587.33, "E5": 659.25, "G5": 783.99, "A5": 880.0, "B5": 987.77, "C6": 1046.5, "D6": 1174.66,
     "E6": 1318.51}


# ---------------------------------------------------------------- строительные блоки
def _buf(seconds):
    return [0.0] * int(RATE * seconds)


def _note(buf, t0, freq, dur, amp, decay, partials=((1, 1.0),), attack=0.004, tremolo=0.0):
    i0, n = int(t0 * RATE), int(dur * RATE)
    for i in range(n):
        j = i0 + i
        if j >= len(buf):
            break
        t = i / RATE
        env = math.exp(-decay * t) * min(1.0, t / attack)
        v = 0.0
        for k, a in partials:
            v += a * math.sin(TAU * freq * k * t)
        if tremolo:
            v *= 1.0 - tremolo + tremolo * math.sin(TAU * 5.0 * t)
        buf[j] += v * env * amp
        if i % 3000 == 2999:
            time.sleep(0.0005)        # отдаём GIL интерфейсу


def _square(buf, t0, f0, f1, dur, amp, decay):
    i0, n = int(t0 * RATE), int(dur * RATE)
    for i in range(n):
        j = i0 + i
        if j >= len(buf):
            break
        t = i / RATE
        f = f0 + (f1 - f0) * (i / max(1, n))
        v = 1.0 if math.sin(TAU * f * t) >= 0 else -1.0
        buf[j] += v * amp * math.exp(-decay * t)


def _pluck(buf, t0, freq, dur, amp, rnd, damp=0.996):
    """Karplus–Strong: щипок струны (кото)."""
    size = max(2, int(RATE / freq))
    ring = [rnd.uniform(-1, 1) for _ in range(size)]
    i0, n = int(t0 * RATE), int(dur * RATE)
    for i in range(n):
        j = i0 + i
        if j >= len(buf):
            break
        k = i % size
        v = ring[k]
        ring[k] = damp * 0.5 * (v + ring[(i + 1) % size])
        buf[j] += v * amp


def _finish(buf, peak, fade=0.02):
    m = max(1e-9, max(abs(x) for x in buf))
    g = peak / m
    f = int(RATE * fade)
    out = [x * g for x in buf]
    for i in range(min(f, len(out))):                 # короткие фейды — без щелчков на стыке петли
        k = i / f
        out[i] *= k
        out[-1 - i] *= k
    return out


# ---------------------------------------------------------------- наборы по стилям
def _classic():
    rnd = random.Random(1)
    tick = _buf(0.05)
    for i in range(len(tick)):
        t = i / RATE
        tick[i] = (rnd.uniform(-1, 1) * 0.5 * math.exp(-t * 170) + 0.7 * math.sin(TAU * 1700 * t) * math.exp(-t * 130))
    win = _buf(2.0)
    for k, f in enumerate((N["C5"], N["E5"], N["G5"], N["C6"])):
        _note(win, 0.11 * k, f, 1.6, 0.25, 3.2, ((1, 1.0), (2, 0.35), (3, 0.15)))
    amb = _buf(6.0)
    for c, chord in enumerate((("A3", "C4", "E4"), ("F3", "A3", "C4"), ("C4", "E4", "G4"), ("G3", "B3", "D4"))):
        for name in chord:
            _note(amb, c * 1.5, N[name], 1.6, 0.18, 0.6, ((1, 1.0), (2, 0.3)), attack=0.3, tremolo=0.1)
    return _finish(tick, 0.9, 0.002), _finish(win, 0.85), _finish(amb, 0.55, 0.05)


def _nte():
    tick = _buf(0.035)
    _square(tick, 0, 1900, 1200, 0.035, 0.5, 90)
    win = _buf(1.8)
    for k, name in enumerate(("A4", "C5", "E5", "A5", "C6", "E6")):
        _square(win, 0.075 * k, N[name], N[name], 0.5, 0.22, 7)
        _note(win, 0.075 * k, N[name] * 2, 0.9, 0.08, 4.5)
    _note(win, 0.5, N["A4"], 1.2, 0.18, 2.5, ((1, 1.0), (3, 0.3), (5, 0.15)))
    amb = _buf(6.0)
    step = 0.125                                                   # 120 bpm, шестнадцатые
    arp = ("A3", "C4", "E4", "C4", "A3", "E4", "G4", "E4")
    for s_i in range(48):
        t = s_i * step
        if s_i % 4 == 0:
            _note(amb, t, N["A2"] if (s_i // 16) % 2 == 0 else N["F3"] / 2, 0.45, 0.40, 6, ((1, 1.0), (3, 0.33), (5, 0.2)))
        _note(amb, t, N[arp[s_i % len(arp)]], 0.12, 0.16, 28, ((1, 1.0), (2, 0.4)))
    return _finish(tick, 0.9, 0.002), _finish(win, 0.85), _finish(amb, 0.5, 0.03)


def _sakura():
    rnd = random.Random(3)
    tick = _buf(0.07)
    _pluck(tick, 0, N["E6"], 0.07, 0.8, rnd, damp=0.985)
    win = _buf(2.4)
    for k, name in enumerate(("D5", "E5", "G5", "A5", "B5", "D6")):          # пентатоника
        _pluck(win, 0.11 * k, N[name], 1.4, 0.5, rnd, damp=0.997)
    _note(win, 0.75, N["D6"], 1.5, 0.15, 3.0, ((1, 1.0), (2.76, 0.25)))
    amb = _buf(6.0)
    for name, t0 in (("D3", 0.0), ("A3", 0.0)):
        _note(amb, t0, N[name], 6.0, 0.10, 0.0, attack=1.0)
    scale = ("D5", "E5", "G5", "A5", "B5", "D6")
    t = 0.3
    while t < 5.4:
        _pluck(amb, t, N[rnd.choice(scale)], 0.9, 0.35, rnd, damp=0.996)
        t += rnd.uniform(0.45, 0.95)
    return _finish(tick, 0.9, 0.002), _finish(win, 0.85), _finish(amb, 0.5, 0.05)


def _paws():
    rnd = random.Random(4)
    tick = _buf(0.06)
    _note(tick, 0, 2093.0, 0.06, 0.5, 80, ((1, 1.0), (2.76, 0.3)))
    win = _buf(2.6)
    for k, name in enumerate(("C5", "E5", "G5", "E5", "C6")):                 # музыкальная шкатулка
        _note(win, 0.16 * k, N[name], 1.2, 0.35, 3.5, ((1, 1.0), (2.76, 0.28), (5.4, 0.1)))
    for name in ("C5", "E5", "G5"):                                           # мягкое тёплое послезвучие, без шума
        _note(win, 0.8, N[name], 1.7, 0.10, 2.2, ((1, 1.0), (2, 0.15)), attack=0.06)
    amb = _buf(6.0)
    melody = ("C5", "E5", "G5", "E5", "C5", "E5", "G5", "A5", "G5", "E5", "D5", "E5")
    for k, name in enumerate(melody):                                          # колыбельная
        _note(amb, k * 0.5, N[name], 0.9, 0.28, 3.0, ((1, 1.0), (2.76, 0.25)))
    _note(amb, 0, N["C3"], 6.0, 0.05, 0.0, attack=0.8)
    return _finish(tick, 0.85, 0.002), _finish(win, 0.85), _finish(amb, 0.5, 0.05)


_MAKERS = {"classic": _classic, "nte": _nte, "sakura": _sakura, "paws": _paws}


def _write_wav(path, samples):
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples))
    os.replace(tmp, path)


def theme_paths(folder, theme):
    return {k: os.path.join(folder, f"{VERSION}_{theme}_{k}.wav") for k in ("tick", "win", "amb")}


def ensure_theme(folder, theme):
    """Создаёт WAV-файлы стиля, если их ещё нет. Возвращает словарь путей."""
    os.makedirs(folder, exist_ok=True)
    paths = theme_paths(folder, theme)
    if not all(os.path.exists(p) for p in paths.values()):
        tick, win, amb = _MAKERS[theme]()
        for key, data in (("tick", tick), ("win", win), ("amb", amb)):
            _write_wav(paths[key], data)
    return paths


# ---------------------------------------------------------------- воспроизведение
class _TickPlayer:
    """Щелчки штифтов: SoundPool на Android (без задержки), иначе пул SoundLoader."""

    def __init__(self):
        self.pool = None
        self.ids = {}
        self.fallback = {}
        self._next = 0
        if platform == "android":
            try:
                from jnius import autoclass
                SoundPool = autoclass("android.media.SoundPool")
                Builder = autoclass("android.media.SoundPool$Builder")
                AttrBuilder = autoclass("android.media.AudioAttributes$Builder")
                Attr = autoclass("android.media.AudioAttributes")
                attrs = (AttrBuilder().setUsage(Attr.USAGE_GAME)
                         .setContentType(Attr.CONTENT_TYPE_SONIFICATION).build())
                self.pool = Builder().setMaxStreams(8).setAudioAttributes(attrs).build()
            except Exception as e:  # noqa: BLE001
                print("SoundPool недоступен:", e)
                self.pool = None

    def load(self, theme, path):
        try:
            if self.pool is not None:
                self.ids[theme] = self.pool.load(path, 1)
            else:
                from kivy.core.audio import SoundLoader
                self.fallback[theme] = [s for s in (SoundLoader.load(path) for _ in range(4)) if s]
        except Exception as e:  # noqa: BLE001
            print("Не загрузился щелчок:", e)

    def play(self, theme, volume):
        try:
            if self.pool is not None:
                sid = self.ids.get(theme)
                if sid:
                    self.pool.play(sid, volume, volume, 1, 0, 1.0)
            else:
                snds = self.fallback.get(theme)
                if snds:
                    snd = snds[self._next % len(snds)]
                    self._next += 1
                    snd.volume = volume
                    snd.stop()
                    snd.play()
        except Exception:  # noqa: BLE001
            pass


class Feedback:
    """Звук + вибрация. enabled — общий переключатель «Звук»."""

    TICK_MIN_GAP = 0.04      # не чаще 25 щелчков/с

    def __init__(self, folder):
        self.folder = folder
        self.enabled = True
        self.theme = "classic"
        self._ticks = _TickPlayer()
        self._snd = {}                  # theme -> {"win": Sound, "amb": Sound}
        self._loading = set()
        self._last_tick = 0.0
        self._last_vib = 0.0
        self._ambient_on = False
        self._vib = None
        try:
            from plyer import vibrator
            self._vib = vibrator
        except Exception:  # noqa: BLE001
            self._vib = None

    # ---- стиль ----
    def set_theme(self, theme):
        self.theme = theme if theme in _MAKERS else "classic"
        if self.theme in self._snd or self.theme in self._loading:
            return
        self._loading.add(self.theme)
        threading.Thread(target=self._prepare, args=(self.theme,), daemon=True).start()

    def _prepare(self, theme):
        try:
            paths = ensure_theme(self.folder, theme)
        except Exception as e:  # noqa: BLE001
            print("Не удалось создать звуки:", e)
            paths = None
        self._loaded(theme, paths)

    @mainthread
    def _loaded(self, theme, paths):
        self._loading.discard(theme)
        if not paths:
            return
        try:
            from kivy.core.audio import SoundLoader
            amb = SoundLoader.load(paths["amb"])
            if amb:
                amb.loop = True
                amb.volume = 0.35
            self._snd[theme] = {"win": SoundLoader.load(paths["win"]), "amb": amb}
        except Exception as e:  # noqa: BLE001
            print("Звуки не загрузились:", e)
            self._snd[theme] = {"win": None, "amb": None}
        self._ticks.load(theme, paths["tick"])

    # ---- вибрация ----
    def _vibrate(self, seconds):
        if self._vib is not None:
            try:
                self._vib.vibrate(seconds)
            except Exception:  # noqa: BLE001
                self._vib = None

    # ---- события ----
    def tick(self, speed=100.0):
        now = time.monotonic()
        if now - self._last_tick < self.TICK_MIN_GAP or not self.enabled:
            return
        self._last_tick = now
        self._ticks.play(self.theme, max(0.2, min(1.0, speed / 400.0)))
        if now - self._last_vib > 0.07:
            self._last_vib = now
            self._vibrate(0.008)

    def ambient_start(self):
        snd = self._snd.get(self.theme, {}).get("amb")
        if self.enabled and snd and not self._ambient_on:
            try:
                snd.play()
                self._ambient_on = True
            except Exception:  # noqa: BLE001
                pass

    def ambient_stop(self):
        for pack in self._snd.values():
            snd = pack.get("amb")
            if snd:
                try:
                    snd.stop()
                except Exception:  # noqa: BLE001
                    pass
        self._ambient_on = False

    def win(self):
        if not self.enabled:
            return
        snd = self._snd.get(self.theme, {}).get("win")
        if snd:
            try:
                snd.stop()
                snd.play()
            except Exception:  # noqa: BLE001
                pass
        self._vibrate(0.25)
