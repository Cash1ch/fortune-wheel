# -*- coding: utf-8 -*-
"""Виджет колеса на Kivy (v2).

Что изменилось относительно v1:
  * подсветка победителя больше НЕ создаётся на лету (раньше InstructionGroup «протекала» при
    перерисовке: копилась в левом нижнем углу и тормозила экран) — всё строится один раз в _rebuild,
    а потом меняется только прозрачность;
  * у каждого стиля своё оформление: лапки / лепестки / неоновая сетка / искры, своя втулка;
  * подписи сами уменьшаются, чтобы влезть, и только потом обрезаются с «…».

Углы в ядре — по часовой от «верха». В Kivy ось Y вверх, а Rotate положителен против часовой,
поэтому колесо поворачивается на -rot, а стрелка — на +flap.
"""
import math
import random

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import (Color, Ellipse, Line, Mesh, PopMatrix, PushMatrix, Rectangle, Rotate,
                           Translate)
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

from fortune_core import THEMES, WheelPhysics


def _c(value, alpha=None):
    """'#rrggbb' или (r,g,b[,a]) в 0..255 -> (r,g,b,a) в 0..1."""
    if isinstance(value, str):
        r, g, b, a = get_color_from_hex(value)
    else:
        v = list(value) + [255] * (4 - len(value))
        r, g, b, a = (x / 255.0 for x in v[:4])
    return (r, g, b, a if alpha is None else alpha)


def _pt(angle_deg, radius):
    a = math.radians(angle_deg)
    return radius * math.sin(a), radius * math.cos(a)     # угол по часовой от верха


def _arc_steps(a0, a1):
    return max(2, int(math.ceil((a1 - a0) / 4.0)) + 1)


def _fan(a0, a1, radius):
    """Вершины веера (центр + дуга) для Mesh(mode='triangle_fan')."""
    steps = _arc_steps(a0, a1)
    verts = [0, 0, 0, 0]
    for k in range(steps + 1):
        x, y = _pt(a0 + (a1 - a0) * k / steps, radius)
        verts += [x, y, 0, 0]
    return verts, list(range(steps + 2))


def _outline(a0, a1, radius):
    pts = [0, 0]
    steps = _arc_steps(a0, a1)
    for k in range(steps + 1):
        x, y = _pt(a0 + (a1 - a0) * k / steps, radius)
        pts += [x, y]
    return pts


# ---- мелкие фигуры (рисуются вокруг текущего начала координат) --------------------------------
def _draw_paw(size):
    Ellipse(pos=(-size * 0.55, -size * 0.62), size=(size * 1.1, size * 0.9))          # подушечка
    for dx, dy, s in ((-0.78, 0.35, 0.42), (-0.27, 0.78, 0.46), (0.27, 0.78, 0.46), (0.78, 0.35, 0.42)):
        Ellipse(pos=((dx - s / 2) * size, (dy - s * 0.6) * size), size=(s * size, s * 1.2 * size))


def _draw_petal(size):
    Ellipse(pos=(-size / 2, -size * 0.3), size=(size, size * 0.6))


# Оформление фона у каждого стиля: (тип, цвет, число элементов, диапазон размера в dp)
DECOR = {
    "classic": ("sparkle", (255, 217, 138), 22, (3, 9)),
    "nte": ("grid", (0, 240, 255), 0, (0, 0)),
    "sakura": ("petal", (255, 160, 185), 18, (14, 28)),
    "paws": ("paw", (201, 162, 122), 14, (14, 28)),
}
SEEDS = {"classic": 11, "nte": 22, "sakura": 33, "paws": 44}


class FortuneWheel(Widget):
    __events__ = ("on_spin_start", "on_peg", "on_speed", "on_finished", "on_tap")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.phys = WheelPhysics()
        self.options = []
        self.theme = "classic"
        self._R = 100.0
        self._rot = self._flap_rot = None
        self._dim_cols = []          # Color подсветки: затемнение «чужих» секторов
        self._win_cols = []          # (Color заливки, Color контура) для каждого сектора
        self._dim_alpha = 0.5
        self._shown_winner = None
        self._t = 0.0
        self._tick_ev = self._idle_ev = None
        self._touch_start = None
        self.bind(pos=self._rebuild, size=self._rebuild)

    # ------------------------------------------------------------------ события (заглушки)
    def on_spin_start(self): pass
    def on_peg(self, speed): pass
    def on_speed(self, speed): pass
    def on_finished(self, index): pass
    def on_tap(self): pass

    # ------------------------------------------------------------------ данные
    @property
    def spinning(self):
        return self.phys.spinning

    def set_options(self, options):
        if self.phys.spinning:
            return False
        self.options = list(options)
        self.phys.set_count(len(self.options))
        self._stop_idle()
        self._rebuild()
        return True

    def set_theme(self, name):
        self.theme = name if name in THEMES else "classic"
        self._rebuild()

    def highlight(self, index):
        if 0 <= index < len(self.options):
            self.phys.winner = index
            self._start_idle()
            self._sync()

    def spin(self):
        if not self.phys.start():
            return False
        self._stop_idle()
        self._sync()
        self._tick_ev = Clock.schedule_interval(self._tick, 0)   # каждый кадр
        self.dispatch("on_spin_start")
        return True

    def stop(self):
        for ev in (self._tick_ev, self._idle_ev):
            if ev is not None:
                ev.cancel()
        self._tick_ev = self._idle_ev = None

    # ------------------------------------------------------------------ анимация
    def _tick(self, dt):
        for kind, value in self.phys.update(dt):
            if kind == "peg":
                self.dispatch("on_peg", value)
            elif kind == "finish":
                if self._tick_ev is not None:
                    self._tick_ev.cancel()
                    self._tick_ev = None
                self._sync()
                self._start_idle()
                self.dispatch("on_speed", 0.0)
                self.dispatch("on_finished", value)
                return
        self.dispatch("on_speed", abs(self.phys.omega))
        self._sync()

    def _start_idle(self):
        self._t = 0.0
        if self._idle_ev is None:
            self._idle_ev = Clock.schedule_interval(self._idle_tick, 1 / 30.0)

    def _stop_idle(self):
        if self._idle_ev is not None:
            self._idle_ev.cancel()
            self._idle_ev = None

    def _idle_tick(self, dt):
        self._t += dt
        self._sync()
        if self._t > 12.0:                    # пульсация не вечная — экономим батарею
            self._stop_idle()

    def _sync(self):
        """Переносит состояние физики в инструкции канваса. Новых инструкций НЕ создаёт."""
        if self._rot is None:
            return
        self._rot.angle = -self.phys.rot
        self._flap_rot.angle = self.phys.flap * 18.0
        w = self.phys.winner if not self.phys.spinning else -1
        if w >= len(self._dim_cols):
            w = -1
        if w != self._shown_winner:
            self._shown_winner = w
            for i, col in enumerate(self._dim_cols):
                r, g, b, _ = col.rgba
                col.rgba = (r, g, b, self._dim_alpha if (w >= 0 and i != w) else 0.0)
            for i, (fill, line) in enumerate(self._win_cols):
                if i != w:
                    fill.a = 0.0
                    line.a = 0.0
        if 0 <= w < len(self._win_cols):
            pulse = 0.5 + 0.5 * math.sin(self._t * 3.0)
            wt = THEMES[self.theme]["wheel"]
            fill, line = self._win_cols[w]
            fill.rgba = _c(wt["win"], (50 + 60 * pulse) / 255.0)
            line.rgba = _c(wt["win_edge"], (180 + 75 * pulse) / 255.0)

    # ------------------------------------------------------------------ построение канваса
    def _rebuild(self, *_):
        self.canvas.clear()
        self._dim_cols, self._win_cols = [], []
        self._rot = self._flap_rot = None
        w, h = self.size
        if w < 10 or h < 10:
            return
        th = THEMES[self.theme]
        wt = th["wheel"]
        side = float(min(w, h))
        margin = max(dp(10), side * 0.085)
        R = max(dp(40), side / 2 - margin)
        self._R = R
        u = R / 220.0
        cx, cy = self.x + w / 2, self.y + h / 2
        n = len(self.options)
        s = 360.0 / max(1, n)
        self._dim_alpha = wt["dim"][3] / 255.0

        with self.canvas:
            self._draw_decor(cx, cy, R, w, h)

            # свечение (аура): концентрические полупрозрачные круги
            glow_r = max(R + 1, min(R + margin - 2, side / 2 - 1))
            for k in range(10):
                r = glow_r - (glow_r - R * 0.9) * k / 9.0
                Color(*_c(wt["aura"], 0.035 + 0.004 * k))
                Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
            if wt["rim_glow"]:                              # свечение обода
                for width_k, alpha in ((0.13, 26), (0.08, 52), (0.045, 110)):
                    Color(*_c(wt["rim_glow"], alpha / 255.0))
                    Line(circle=(cx, cy, R * 1.01), width=R * width_k / 2)

            PushMatrix()
            Translate(cx, cy)
            self._rot = Rotate(angle=-self.phys.rot, origin=(0, 0))

            if n == 0:                                      # пустое колесо — бледный диск
                Color(1, 1, 1, 0.09)
                Ellipse(pos=(-R, -R), size=(2 * R, 2 * R))
            colors = wt["colors"]
            sector_cols = []
            for i in range(n):
                idx = i % len(colors)
                if n % len(colors) == 1 and i == n - 1:     # последний не должен совпасть цветом с первым
                    idx = (idx + 2) % len(colors)
                sector_cols.append(_c(colors[idx]))
            for i in range(n):                              # сектора + разделители
                Color(*sector_cols[i])
                v, idxs = _fan(i * s, (i + 1) * s, R)
                Mesh(vertices=v, indices=idxs, mode="triangle_fan")
                Color(*_c(wt["edge"]))
                x, y = _pt(i * s, R)
                Line(points=[0, 0, x, y], width=max(dp(0.8), 1.6 * u))

            # подписи вдоль радиуса: сначала уменьшаем шрифт, и только потом обрезаем
            arc = R * 2 * math.pi / max(n, 1)
            font_px = max(dp(10), min(arc * 0.30, R * 0.105))
            font_min = max(dp(8), R * 0.045)
            avail = R * 0.62
            for i, text in enumerate(self.options):
                col = sector_cols[i]
                lum = 0.299 * col[0] * 255 + 0.587 * col[1] * 255 + 0.114 * col[2] * 255
                tex = self._label_texture(text, font_px, font_min, avail)
                if tex is None:
                    continue
                PushMatrix()
                Rotate(angle=90 - (i * s + s / 2), origin=(0, 0))
                Color(*_c(wt["text_dark"] if lum > 150 else wt["text_light"]))
                tw, thh = tex.size
                Rectangle(texture=tex, pos=(R * 0.82 - tw, -thh / 2), size=(tw, thh))
                PopMatrix()

            Color(*_c(wt["rim"]))                           # обод
            Line(circle=(0, 0, R), width=max(dp(2), R * wt["rim_w"] / 2))
            if wt["rim2"]:
                Color(*_c(wt["rim2"]))
                Line(circle=(0, 0, R * 0.955), width=max(dp(0.8), R * 0.006))
            pr = max(dp(2), R * 0.03)                       # штифты на границах секторов
            for i in range(n):
                x, y = _pt(i * s, R)
                Color(*_c(wt["peg"][1]))
                Ellipse(pos=(x - pr, y - pr), size=(2 * pr, 2 * pr))
                Color(*_c(wt["peg"][0]))
                Ellipse(pos=(x - pr * 0.6, y - pr * 0.4), size=(pr, pr))

            # подсветка победителя: строится заранее, потом меняется только прозрачность
            dim = _c(wt["dim"], 0.0)
            for i in range(n):
                dcol = Color(*dim)
                v, idxs = _fan(i * s, (i + 1) * s, R)
                Mesh(vertices=v, indices=idxs, mode="triangle_fan")
                self._dim_cols.append(dcol)
            for i in range(n):
                fill = Color(*_c(wt["win"], 0.0))
                v, idxs = _fan(i * s, (i + 1) * s, R)
                Mesh(vertices=v, indices=idxs, mode="triangle_fan")
                line = Color(*_c(wt["win_edge"], 0.0))
                Line(points=_outline(i * s, (i + 1) * s, R), width=dp(2), close=True)
                self._win_cols.append((fill, line))
            PopMatrix()

            self._draw_hub(cx, cy, R, wt)

            # указатель сверху: качается от щелчков штифтов (поворот вокруг основания)
            PushMatrix()
            Translate(cx, cy + R + R * 0.01)
            self._flap_rot = Rotate(angle=self.phys.flap * 18.0, origin=(0, 0))
            half = R * (0.045 if wt["ptr_sharp"] else 0.055)
            up = R * 0.045
            down = R * (0.11 if wt["ptr_sharp"] else 0.09)
            Color(*_c(wt["ptr"][1]))
            Mesh(vertices=[-half * 1.25, up * 1.2, 0, 0, half * 1.25, up * 1.2, 0, 0, 0, -down * 1.2, 0, 0],
                 indices=[0, 1, 2], mode="triangle_fan")
            Color(*_c(wt["ptr"][0]))
            Mesh(vertices=[-half, up, 0, 0, half, up, 0, 0, 0, -down, 0, 0],
                 indices=[0, 1, 2], mode="triangle_fan")
            Color(*_c(wt["ptr"][2]))
            Ellipse(pos=(-R * 0.016, up * 0.1 - R * 0.016), size=(R * 0.032, R * 0.032))
            PopMatrix()

        self._shown_winner = None
        self._sync()

    # ------------------------------------------------------------------ оформление стиля
    def _draw_decor(self, cx, cy, R, w, h):
        kind, color, count, (smin, smax) = DECOR[self.theme]
        rnd = random.Random(SEEDS[self.theme])
        x0, y0 = self.x, self.y
        if kind == "grid":                                   # неоновая сетка + угловые скобки
            Color(*_c(color, 0.07))
            gap = dp(38)
            xx = x0
            while xx <= x0 + w:
                Line(points=[xx, y0, xx, y0 + h], width=1)
                xx += gap
            yy = y0
            while yy <= y0 + h:
                Line(points=[x0, yy, x0 + w, yy], width=1)
                yy += gap
            L = dp(26)
            for (px, py, sx, sy, col) in ((x0 + dp(6), y0 + h - dp(6), 1, -1, color),
                                          (x0 + w - dp(6), y0 + h - dp(6), -1, -1, "#ff2a8d"),
                                          (x0 + dp(6), y0 + dp(6), 1, 1, "#ff2a8d"),
                                          (x0 + w - dp(6), y0 + dp(6), -1, 1, color)):
                Color(*_c(col, 0.8))
                Line(points=[px + sx * L, py, px, py, px, py + sy * L], width=dp(1.5))
            return
        for _ in range(count):
            x = x0 + rnd.random() * w
            y = y0 + rnd.random() * h
            size = dp(rnd.uniform(smin, smax))
            rot = rnd.uniform(0, 360)
            alpha = rnd.uniform(0.18, 0.40)
            if math.hypot(x - cx, y - cy) < R * 1.1:         # под колесом всё равно не видно
                continue
            PushMatrix()
            Translate(x, y)
            Rotate(angle=rot, origin=(0, 0))
            if kind == "paw":
                Color(*_c(color, alpha * 0.7))
                _draw_paw(size)
            elif kind == "petal":
                Color(*_c(color, alpha * 1.4))
                _draw_petal(size)
            else:                                            # sparkle: точка + крестик
                Color(*_c(color, alpha * 2.0))
                Ellipse(pos=(-size / 3, -size / 3), size=(size * 2 / 3, size * 2 / 3))
                Line(points=[-size, 0, size, 0], width=1)
                Line(points=[0, -size, 0, size], width=1)
            PopMatrix()

    def _draw_hub(self, cx, cy, R, wt):
        hub = R * 0.15
        Color(*_c(wt["hub"][2]))
        Ellipse(pos=(cx - hub - dp(1.5), cy - hub - dp(1.5)), size=(2 * hub + dp(3), 2 * hub + dp(3)))
        Color(*_c(wt["hub"][0]))
        Ellipse(pos=(cx - hub, cy - hub), size=(2 * hub, 2 * hub))
        Color(*_c(wt["hub"][1]))
        Ellipse(pos=(cx - hub * 0.7, cy - hub * 0.7), size=(1.4 * hub, 1.4 * hub))
        PushMatrix()
        Translate(cx, cy)
        Color(*_c(wt["star"]))
        if self.theme == "paws":                             # лапка
            _draw_paw(hub * 0.62)
        elif self.theme == "sakura":                         # цветок сакуры
            for k in range(5):
                PushMatrix()
                Rotate(angle=k * 72, origin=(0, 0))
                Ellipse(pos=(-hub * 0.17, hub * 0.02), size=(hub * 0.34, hub * 0.55))
                PopMatrix()
            Color(*_c(wt["hub"][2]))
            Ellipse(pos=(-hub * 0.1, -hub * 0.1), size=(hub * 0.2, hub * 0.2))
        else:                                                # звезда
            star = [0, 0, 0, 0]
            for k in range(11):
                rad = R * (0.085 if k % 2 == 0 else 0.037)
                x, y = _pt(k * 36.0, rad)
                star += [x, y, 0, 0]
            Mesh(vertices=star, indices=list(range(12)), mode="triangle_fan")
        PopMatrix()

    @staticmethod
    def _label_texture(text, font_px, font_min, avail):
        """Текстура подписи: сначала уменьшаем шрифт, потом обрезаем с «…»."""
        try:
            fs = font_px
            lbl = CoreLabel(text=text, font_size=fs, bold=True)
            while lbl.get_extents(text)[0] > avail and fs > font_min:
                fs = max(font_min, fs * 0.92)
                lbl = CoreLabel(text=text, font_size=fs, bold=True)
            if lbl.get_extents(text)[0] > avail:
                t = text
                while len(t) > 1 and lbl.get_extents(t + "…")[0] > avail:
                    t = t[:-1]
                lbl = CoreLabel(text=t.rstrip() + "…", font_size=fs, bold=True)
            lbl.refresh()
            return lbl.texture
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------ касание: тап по колесу = крутить
    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touch_start = touch.pos
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self._touch_start is not None:
            self._touch_start = None
            if self.collide_point(*touch.pos):
                self.dispatch("on_tap")
            return True
        return super().on_touch_up(touch)
