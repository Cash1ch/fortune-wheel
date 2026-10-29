# -*- coding: utf-8 -*-
"""Звуки, музыка и вибрация (v4): у каждого стиля свой набор.

  classic — деревянный щелчок, фанфары, золотой вальс (арфа + бас + пэд)
  nte     — электронные блипы, синтезаторное арпеджио, неоновый синтвейв
  sakura  — щипок кото, глиссандо кото, спокойная пентатоника с бурдоном
  paws    — звон шкатулки; победа: перезвон колокольчиков на ошейнике; колыбельная

Фоновая музыка играет непрерывно, пока приложение открыто и «Звук: вкл».
Всё синтезируется при первом запуске стиля в фоновом потоке и кэшируется в папке приложения.
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
VERSION = "v5"
THEMES = ("classic", "nte", "sakura", "paws")
BGM_SECONDS = 12.0
BGM_VOLUME = 0.30
BGM_DUCKED = 0.10

# частоты нот (Гц)
N = {"A1": 55.0, "C2": 65.41, "E2": 82.41, "F2": 87.31, "G2": 98.0, "A2": 110.0, "C3": 130.81, "D3": 146.83,
     "E3": 164.81, "F3": 174.61, "G3": 196.0, "G#3": 207.65, "A3": 220.0, "B3": 246.94, "C4": 261.63,
     "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.0, "A4": 440.0, "B4": 493.88, "C5": 523.25,
     "D5": 587.33, "E5": 659.25, "F5": 698.46, "G5": 783.99, "A5": 880.0, "B5": 987.77, "C6": 1046.5,
     "D6": 1174.66, "E6": 1318.51}


# ---------------------------------------------------------------- строительные блоки
def _buf(seconds):
    return [0.0] * int(RATE * seconds)


def _yield(i):
    if i % 3000 == 2999:
        time.sleep(0.0005)            # отдаём GIL интерфейсу, пока синтезируем в фоне


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
        _yield(i)


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
        _yield(i)


def _kick(buf, t0, amp):
    """Бочка: синус с падающей частотой (чистый, без шума)."""
    i0, n = int(t0 * RATE), int(0.22 * RATE)
    phase = 0.0
    for i in range(n):
        j = i0 + i
        if j >= len(buf):
            break
        t = i / RATE
        phase += (45.0 + 80.0 * math.exp(-t * 28.0)) / RATE
        buf[j] += math.sin(TAU * phase) * amp * math.exp(-t * 13.0)


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
        _yield(i)


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


# ---------------------------------------------------------------- классика
def _classic():
    rnd = random.Random(1)
    tick = _buf(0.05)
    for i in range(len(tick)):
        t = i / RATE
        tick[i] = (rnd.uniform(-1, 1) * 0.5 * math.exp(-t * 170) + 0.7 * math.sin(TAU * 1700 * t) * math.exp(-t * 130))
    win = _buf(2.0)
    for k, f in enumerate((N["C5"], N["E5"], N["G5"], N["C6"])):
        _note(win, 0.11 * k, f, 1.6, 0.25, 3.2, ((1, 1.0), (2, 0.35), (3, 0.15)))
    return _finish(tick, 0.9, 0.002), _finish(win, 0.85), _classic_bgm()


def _classic_bgm():
    """Золотой вальс: бас на раз, арфа на два-три, тихий пэд. 6 тактов по 3 доли."""
    buf = _buf(BGM_SECONDS)
    beat = 2.0 / 3.0
    bars = (("A2", ("A3", "C4", "E4")), ("F2", ("F3", "A3", "C4")), ("C3", ("C4", "E4", "G4")),
            ("G2", ("G3", "B3", "D4")), ("F2", ("F3", "A3", "C4")), ("E2", ("E3", "G#3", "B3")))
    for b, (bass, chord) in enumerate(bars):
        t0 = b * 3 * beat
        _note(buf, t0, N[bass], 1.9, 0.32, 1.6, ((1, 1.0), (2, 0.3)), attack=0.02)
        _note(buf, t0, N[chord[0]], 1.9, 0.06, 0.4, attack=0.35, tremolo=0.1)          # пэд
        _note(buf, t0, N[chord[2]], 1.9, 0.05, 0.4, attack=0.35, tremolo=0.1)
        _note(buf, t0 + beat, N[chord[1]] * 2, 0.9, 0.16, 4.5, ((1, 1.0), (2, 0.3), (3, 0.1)))   # арфа
        _note(buf, t0 + 2 * beat, N[chord[2]] * 2, 0.9, 0.16, 4.5, ((1, 1.0), (2, 0.3), (3, 0.1)))
    return _finish(buf, 0.5, 0.05)


# ---------------------------------------------------------------- NTE
def _nte():
    tick = _buf(0.035)
    _square(tick, 0, 1900, 1200, 0.035, 0.5, 90)
    win = _buf(1.8)
    for k, name in enumerate(("A4", "C5", "E5", "A5", "C6", "E6")):
        _square(win, 0.075 * k, N[name], N[name], 0.5, 0.22, 7)
        _note(win, 0.075 * k, N[name] * 2, 0.9, 0.08, 4.5)
    _note(win, 0.5, N["A4"], 1.2, 0.18, 2.5, ((1, 1.0), (3, 0.3), (5, 0.15)))
    return _finish(tick, 0.9, 0.002), _finish(win, 0.85), _nte_bgm()


def _nte_bgm():
    """Неоновый синтвейв: бочка, пульсирующий бас, арпеджио. 4 такта по 16 шагов."""
    buf = _buf(BGM_SECONDS)
    step = BGM_SECONDS / 64.0
    chords = (("A2", ("A3", "C4", "E4")), ("F2", ("F3", "A3", "C4")), ("C3", ("C4", "E4", "G4")),
              ("G2", ("G3", "B3", "D4")))
    pattern = (0, 1, 2, 1, 0, 1, 2, 1, 0, 2, 1, 2, 0, 1, 2, 1)
    for s_i in range(64):
        bar, pos = divmod(s_i, 16)
        bass, chord = chords[bar]
        t = s_i * step
        if pos % 4 == 0:
            _kick(buf, t, 0.45)
            _note(buf, t, N[bass], step * 3.2, 0.30, 5, ((1, 1.0), (3, 0.33), (5, 0.2)))
        _note(buf, t, N[chord[pattern[pos]]] * 2, 0.15, 0.13, 22, ((1, 1.0), (2, 0.4)))
        if pos % 4 == 2:                                   # «хэт» — чистый высокий тик, без шума
            _note(buf, t, 5200.0, 0.03, 0.05, 140)
    return _finish(buf, 0.5, 0.03)


# ---------------------------------------------------------------- сакура
def _sakura():
    rnd = random.Random(3)
    tick = _buf(0.07)
    _pluck(tick, 0, N["E6"], 0.07, 0.8, rnd, damp=0.985)
    win = _buf(2.4)
    for k, name in enumerate(("D5", "E5", "G5", "A5", "B5", "D6")):          # пентатоника
        _pluck(win, 0.11 * k, N[name], 1.4, 0.5, rnd, damp=0.997)
    _note(win, 0.75, N["D6"], 1.5, 0.15, 3.0, ((1, 1.0), (2.76, 0.25)))
    return _finish(tick, 0.9, 0.002), _finish(win, 0.85), _sakura_bgm()


def _sakura_bgm():
    """Спокойная пентатоника кото над бурдоном."""
    rnd = random.Random(30)
    buf = _buf(BGM_SECONDS)
    _note(buf, 0.0, N["D3"], BGM_SECONDS, 0.09, 0.0, attack=1.0)
    _note(buf, 0.0, N["A3"], BGM_SECONDS, 0.06, 0.0, attack=1.2)
    phrase = ((0.0, "D5"), (0.75, "E5"), (1.5, "G5"), (3.0, "A5"), (3.75, "G5"), (4.5, "E5"), (6.0, "D5"),
              (6.75, "E5"), (7.5, "G5"), (8.25, "A5"), (9.0, "B5"), (10.5, "A5"), (11.25, "G5"))
    for t, name in phrase:
        _pluck(buf, t, N[name], 1.3, 0.35, rnd, damp=0.996)
    _pluck(buf, 0.0, N["D4"], 1.5, 0.25, rnd, damp=0.997)
    _pluck(buf, 6.0, N["D4"], 1.5, 0.25, rnd, damp=0.997)
    return _finish(buf, 0.5, 0.05)


# ---------------------------------------------------------------- белые лапки
def _paws():
    tick = _buf(0.06)
    _note(tick, 0, 2093.0, 0.06, 0.5, 80, ((1, 1.0), (2.76, 0.3)))
    win = _buf(2.2)
    bell = ((1, 1.0), (2.76, 0.4), (3.4, 0.2))                                  # колокольчик: неточные обертоны
    for t, a, fm in ((0.00, 0.9, 1.00), (0.05, 0.7, 1.03), (0.11, 0.8, 0.98), (0.17, 0.55, 1.02), (0.26, 0.4, 1.00)):
        _note(win, t, 2000.0 * fm, 0.6, 0.22 * a, 9, bell)                      # первый перезвон на ошейнике
    for t, a, fm in ((0.55, 0.7, 1.00), (0.61, 0.55, 1.02), (0.68, 0.45, 0.99)):
        _note(win, t, 2400.0 * fm, 0.6, 0.20 * a, 9, bell)                      # второй, выше и тише
    _note(win, 1.10, 2300.0, 1.0, 0.16, 5, bell)                                # последний тихий «динь»
    _note(win, 1.25, 3100.0, 0.8, 0.08, 6, ((1, 1.0), (2.76, 0.3)))             # и искорка над ним
    return _finish(tick, 0.85, 0.002), _finish(win, 0.85), _paws_bgm()


def _paws_bgm():
    """Колыбельная музыкальной шкатулки: 4 такта по 6 восьмых."""
    buf = _buf(BGM_SECONDS)
    melody = ("C5", "E5", "G5", "E5", "C5", "E5", "G5", "A5", "G5", "E5", "D5", "C5",
              "D5", "F5", "A5", "F5", "D5", "F5", "E5", "G5", "C6", "G5", "E5", "C5")
    for k, name in enumerate(melody):
        _note(buf, k * 0.5, N[name], 0.8, 0.28, 3.4, ((1, 1.0), (2.76, 0.25)))
    _note(buf, 0.0, N["C3"], BGM_SECONDS, 0.05, 0.0, attack=0.8)
    return _finish(buf, 0.5, 0.05)


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
    return {k: os.path.join(folder, f"{VERSION}_{theme}_{k}.wav") for k in ("tick", "win", "bgm")}


def ensure_theme(folder, theme):
    """Создаёт WAV-файлы стиля, если их ещё нет. Возвращает словарь путей."""
    os.makedirs(folder, exist_ok=True)
    paths = theme_paths(folder, theme)
    if not all(os.path.exists(p) for p in paths.values()):
        tick, win, bgm = _MAKERS[theme]()
        for key, data in (("tick", tick), ("win", win), ("bgm", bgm)):
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
    """Звук, музыка и вибрация. «Звук: вкл/выкл» — set_enabled()."""

    TICK_MIN_GAP = 0.04      # не чаще 25 щелчков/с

    def __init__(self, folder):
        self.folder = folder
        self.enabled = True
        self.theme = "classic"
        self._ticks = _TickPlayer()
        self._snd = {}                  # theme -> {"win": Sound, "bgm": Sound}
        self._loading = set()
        self._last_tick = 0.0
        self._last_vib = 0.0
        self._music_wanted = False      # приложение на экране и музыка нужна
        self._duck_ev = None
        self._vib = None
        try:
            from plyer import vibrator
            self._vib = vibrator
        except Exception:  # noqa: BLE001
            self._vib = None

    # ---- стиль ----
    def set_theme(self, theme):
        self.theme = theme if theme in _MAKERS else "classic"
        self._apply_music()                                       # старая музыка стихает, новая — по готовности
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
            bgm = SoundLoader.load(paths["bgm"])
            if bgm:
                bgm.loop = True
                bgm.volume = BGM_VOLUME
            self._snd[theme] = {"win": SoundLoader.load(paths["win"]), "bgm": bgm}
        except Exception as e:  # noqa: BLE001
            print("Звуки не загрузились:", e)
            self._snd[theme] = {"win": None, "bgm": None}
        self._ticks.load(theme, paths["tick"])
        self._apply_music()

    # ---- включение/выключение ----
    def set_enabled(self, on):
        self.enabled = bool(on)
        self._apply_music()

    def music_on(self):
        """Приложение на экране: играть фоновую музыку (если звук включён)."""
        self._music_wanted = True
        self._apply_music()

    def music_off(self):
        """Приложение свёрнуто или закрыто: музыку остановить."""
        self._music_wanted = False
        self._apply_music()

    def _apply_music(self):
        want = self._music_wanted and self.enabled
        for theme, pack in self._snd.items():
            snd = pack.get("bgm")
            if not snd:
                continue
            try:
                if want and theme == self.theme:
                    snd.volume = BGM_VOLUME
                    if snd.state != "play":
                        snd.play()
                elif snd.state == "play":
                    snd.stop()
            except Exception:  # noqa: BLE001
                pass

    def _duck(self, seconds):
        """На время победного звука музыка тише, потом возвращается."""
        snd = self._snd.get(self.theme, {}).get("bgm")
        if not snd:
            return
        try:
            snd.volume = BGM_DUCKED
        except Exception:  # noqa: BLE001
            return
        if self._duck_ev is not None:
            self._duck_ev.cancel()
        self._duck_ev = Clock.schedule_once(lambda _dt: self._apply_music(), seconds)

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

    def win(self):
        if not self.enabled:
            return
        snd = self._snd.get(self.theme, {}).get("win")
        if snd:
            try:
                snd.stop()
                snd.play()
                self._duck(2.8)
            except Exception:  # noqa: BLE001
                pass
        self._vibrate(0.25)
