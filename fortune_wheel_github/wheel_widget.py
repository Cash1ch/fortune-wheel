# -*- coding: utf-8 -*-
"""Виджет колеса на Kivy.

Канвас строится ОДИН раз при смене размера / вариантов / темы; в каждом кадре меняется только угол
Rotate (колесо) и Rotate стрелки — это дёшево даже на слабых телефонах.

Углы в ядре — по часовой от «верха». В Kivy ось Y направлена вверх, а Rotate положителен против
часовой, поэтому колесо поворачивается на -rot, а стрелка — на +flap.
"""
import math

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import (Color, Ellipse, InstructionGroup, Line, Mesh, PopMatrix, PushMatrix,
                           Rectangle, Rotate, Translate)
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


def _fan(a0, a1, radius):
    """Вершины веера (центр + дуга) для Mesh(mode='triangle_fan')."""
    steps = max(2, int(math.ceil((a1 - a0) / 4.0)) + 1)
    verts = [0, 0, 0, 0]
    for k in range(steps + 1):
        x, y = _pt(a0 + (a1 - a0) * k / steps, radius)
        verts += [x, y, 0, 0]
    return verts, list(range(steps + 2))


class FortuneWheel(Widget):
    __events__ = ("on_spin_start", "on_peg", "on_speed", "on_finished", "on_tap")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.phys = WheelPhysics()
        self.options = []
        self.theme = "classic"
        self._rot = self._flap_rot = None
        self._win_group = None
        self._win_fill = self._win_line = None
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
        self._shown_winner = None
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
        if self._idle_ev is None:
            self._idle_ev = Clock.schedule_interval(self._idle_tick, 1 / 30.0)

    def _stop_idle(self):
        if self._idle_ev is not None:
            self._idle_ev.cancel()
            self._idle_ev = None

    def _idle_tick(self, dt):
        self._t += dt
        self._sync()

    def _sync(self):
        """Переносит состояние физики в инструкции канваса (без перестройки)."""
        if self._rot is None:
            return
        self._rot.angle = -self.phys.rot
        self._flap_rot.angle = self.phys.flap * 18.0
        w = self.phys.winner if not self.phys.spinning else -1
        if w != self._shown_winner:
            self._build_winner(w)
        if self._win_fill is not None:
            pulse = 0.5 + 0.5 * math.sin(self._t * 3.0)
            wt = THEMES[self.theme]["wheel"]
            self._win_fill.rgba = _c(wt["win"], (50 + 60 * pulse) / 255.0)
            self._win_line.rgba = _c(wt["win_edge"], (180 + 75 * pulse) / 255.0)

    def _build_winner(self, w):
        self._shown_winner = w
        g = self._win_group
        g.clear()
        self._win_fill = self._win_line = None
        n = len(self.options)
        if w < 0 or w >= n:
            return
        s = 360.0 / n
        R = self._R
        wt = THEMES[self.theme]["wheel"]
        g.add(Color(*_c(wt["dim"])))
        for i in range(n):                                  # остальные сектора приглушаем
            if i != w:
                v, idx = _fan(i * s, (i + 1) * s, R)
                g.add(Mesh(vertices=v, indices=idx, mode="triangle_fan"))
        v, idx = _fan(w * s, (w + 1) * s, R)
        self._win_fill = Color(*_c(wt["win"], 0.3))
        g.add(self._win_fill)
        g.add(Mesh(vertices=v, indices=idx, mode="triangle_fan"))
        self._win_line = Color(*_c(wt["win_edge"]))
        g.add(self._win_line)
        g.add(Line(points=self._outline(w * s, (w + 1) * s, R), width=dp(2), close=True))

    @staticmethod
    def _outline(a0, a1, R):
        pts = [0, 0]
        steps = max(2, int(math.ceil((a1 - a0) / 4.0)) + 1)
        for k in range(steps + 1):
            x, y = _pt(a0 + (a1 - a0) * k / steps, R)
            pts += [x, y]
        return pts

    # ------------------------------------------------------------------ построение канваса
    def _rebuild(self, *_):
        self.canvas.clear()
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

        with self.canvas:
            # свечение (аура): концентрические полупрозрачные круги
            glow_r = max(R + 1, min(R + margin - 2, side / 2 - 1))
            for k in range(10):
                r = glow_r - (glow_r - R * 0.9) * k / 9.0
                Color(*_c(wt["aura"], 0.035 + 0.004 * k))
                Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
            if wt["rim_glow"]:                              # свечение обода (неон / сакура / лапки)
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

            # подписи вдоль радиуса
            arc = R * 2 * math.pi / max(n, 1)
            font_px = max(dp(10), min(arc * 0.30, R * 0.115))
            avail = R * 0.60
            for i, text in enumerate(self.options):
                col = sector_cols[i]
                lum = 0.299 * col[0] * 255 + 0.587 * col[1] * 255 + 0.114 * col[2] * 255
                tex = self._label_texture(text, font_px, avail)
                if tex is None:
                    continue
                PushMatrix()
                Rotate(angle=90 - (i * s + s / 2), origin=(0, 0))
                Color(*_c(wt["text_dark"] if lum > 150 else wt["text_light"]))
                tw, thh = tex.size
                Rectangle(texture=tex, pos=(R * 0.80 - tw, -thh / 2), size=(tw, thh))
                PopMatrix()

            Color(*_c(wt["rim"]))                           # обод
            Line(circle=(0, 0, R), width=max(dp(2), R * wt["rim_w"] / 2))
            if wt["rim2"]:
                Color(*_c(wt["rim2"]))
                Line(circle=(0, 0, R * 0.955), width=max(dp(0.8), R * 0.006))
            pr = max(dp(2), R * 0.03)                       # штифты на границах секторов
            if n:
                for i in range(n):
                    x, y = _pt(i * s, R)
                    Color(*_c(wt["peg"][1]))
                    Ellipse(pos=(x - pr, y - pr), size=(2 * pr, 2 * pr))
                    Color(*_c(wt["peg"][0]))
                    Ellipse(pos=(x - pr * 0.6, y - pr * 0.4), size=(pr, pr))

            self._win_group = InstructionGroup()            # подсветка победителя (вращается с колесом)
            self.canvas.add(self._win_group)
            PopMatrix()

            # втулка и звезда
            hub = R * 0.15
            Color(*_c(wt["hub"][2]))
            Ellipse(pos=(cx - hub - dp(1.5), cy - hub - dp(1.5)), size=(2 * hub + dp(3), 2 * hub + dp(3)))
            Color(*_c(wt["hub"][0]))
            Ellipse(pos=(cx - hub, cy - hub), size=(2 * hub, 2 * hub))
            Color(*_c(wt["hub"][1]))
            Ellipse(pos=(cx - hub * 0.7, cy - hub * 0.7), size=(1.4 * hub, 1.4 * hub))
            star = [cx, cy, 0, 0]
            for k in range(11):
                a = k * 36.0
                rad = R * (0.085 if k % 2 == 0 else 0.037)
                x, y = _pt(a, rad)
                star += [cx + x, cy + y, 0, 0]
            Color(*_c(wt["star"]))
            Mesh(vertices=star, indices=list(range(12)), mode="triangle_fan")

            # указатель сверху: качается от щелчков штифтов (поворот вокруг его основания)
            PushMatrix()
            px, py = cx, cy + R + R * 0.01
            Translate(px, py)
            self._flap_rot = Rotate(angle=self.phys.flap * 18.0, origin=(0, 0))
            half = R * (0.045 if wt["ptr_sharp"] else 0.055)
            up = R * 0.045
            down = R * (0.11 if wt["ptr_sharp"] else 0.09)
            tri_outer = [-half * 1.25, up * 1.2, 0, 0, half * 1.25, up * 1.2, 0, 0, 0, -down * 1.2, 0, 0]
            Color(*_c(wt["ptr"][1]))
            Mesh(vertices=tri_outer, indices=[0, 1, 2], mode="triangle_fan")
            tri = [-half, up, 0, 0, half, up, 0, 0, 0, -down, 0, 0]
            Color(*_c(wt["ptr"][0]))
            Mesh(vertices=tri, indices=[0, 1, 2], mode="triangle_fan")
            Color(*_c(wt["ptr"][2]))
            Ellipse(pos=(-R * 0.016, up * 0.1 - R * 0.016), size=(R * 0.032, R * 0.032))
            PopMatrix()

        self._shown_winner = None
        self._sync()

    @staticmethod
    def _label_texture(text, font_px, avail):
        """Текстура подписи; если не влезает по ширине — обрезается с «…» (как elidedText)."""
        try:
            lbl = CoreLabel(text=text, font_size=font_px, bold=True)
            if lbl.get_extents(text)[0] > avail:
                t = text
                while len(t) > 1 and lbl.get_extents(t + "…")[0] > avail:
                    t = t[:-1]
                lbl = CoreLabel(text=t.rstrip() + "…", font_size=font_px, bold=True)
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
                self.dispatch("on_tap")                     # и тап, и свайп запускают вращение
            return True
        return super().on_touch_up(touch)
