# -*- coding: utf-8 -*-
"""Колесо Фортуны — мобильное приложение (Kivy), v2. Интерфейс на русском.

Запуск на ПК для отладки:  pip install kivy plyer  &&  python main.py
Сборка APK:               GitHub Actions / buildozer (см. README.md)
"""
import json
import os

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex, platform

from fortune_core import FortuneState, INTRO_TEXTS, THEMES, THEME_ORDER
from sounds import Feedback
from wheel_widget import AnimatedBackground, FortuneWheel  # noqa: F401  (нужны для KV)

Window.softinput_mode = "below_target"          # клавиатура не перекрывает поле ввода
if platform not in ("android", "ios"):
    Window.size = (400, 780)                    # окно «как телефон» при отладке на ПК

KV = """
<FlatButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: app.c_btn_fg
    font_size: '15sp'
    bold: True
    canvas.before:
        Color:
            rgba: (app.c_btn[0]*0.8, app.c_btn[1]*0.8, app.c_btn[2]*0.8, 1) if self.state == 'down' else app.c_btn
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]

<Root>:
    canvas.before:
        Color:
            rgba: app.c_bg
        Rectangle:
            pos: self.pos
            size: self.size

    AnimatedBackground:
        id: bg
        size_hint: 1, 1
        pos_hint: {'x': 0, 'y': 0}

    BoxLayout:
        orientation: 'vertical'
        padding: dp(12), dp(8), dp(12), dp(12)
        spacing: dp(6)
        size_hint: 1, 1
        pos_hint: {'x': 0, 'y': 0}

        Label:
            text: app.title_text
            font_size: '22sp'
            bold: True
            color: app.c_title
            size_hint_y: None
            height: dp(38)
        Label:
            text: app.intro_text
            italic: True
            color: app.c_text
            font_size: '13sp'
            halign: 'center'
            valign: 'middle'
            text_size: self.width - dp(16), None
            size_hint_y: None
            height: self.texture_size[1] + dp(6)
        Label:
            text: app.subtitle
            font_size: '12sp'
            color: app.c_hint
            size_hint_y: None
            height: dp(18)

        FloatLayout:
            FortuneWheel:
                id: wheel
                size_hint: 1, 1
                pos_hint: {'x': 0, 'y': 0}

        Label:
            text: app.status
            color: app.c_hint
            font_size: '14sp'
            size_hint_y: None
            height: dp(24)

        BoxLayout:
            size_hint_y: None
            height: dp(52)
            spacing: dp(8)
            FlatButton:
                text: 'Варианты (%d)' % app.option_count
                disabled: app.busy
                on_release: app.open_options()
            FlatButton:
                text: 'Стиль'
                disabled: app.busy
                on_release: app.open_styles()
            FlatButton:
                text: 'На выбывание: ' + ('вкл' if app.elim_on else 'выкл')
                disabled: app.busy
                on_release: app.toggle_elim()
            FlatButton:
                text: 'Звук: ' + ('вкл' if app.sound_on else 'выкл')
                on_release: app.toggle_sound()

        Button:
            id: spin_btn
            text: 'Удачи!'
            font_size: '24sp'
            bold: True
            size_hint_y: None
            height: dp(72)
            disabled: app.busy or not app.has_options
            background_normal: ''
            background_down: ''
            background_color: 0, 0, 0, 0
            color: app.c_spin_fg if not self.disabled else app.c_hint
            on_release: app.spin()
            canvas.before:
                Color:
                    rgba: (app.c_spin if not self.disabled else (0.5, 0.5, 0.5, 0.35))
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(20)]
"""

STATE_FILE = "state.json"
NO_OPTIONS_HINT = "Нажмите «Варианты» и впишите свои варианты."


class Root(FloatLayout):
    pass


class FortuneApp(App):
    title = "Колесо Фортуны"

    theme_name = StringProperty("classic")
    title_text = StringProperty("")
    intro_text = StringProperty("")
    subtitle = StringProperty("")
    status = StringProperty("")
    has_options = BooleanProperty(False)
    option_count = NumericProperty(0)
    busy = BooleanProperty(False)
    elim_on = BooleanProperty(False)
    sound_on = BooleanProperty(True)
    spins = NumericProperty(0)

    c_bg = ListProperty([0, 0, 0, 1])
    c_title = ListProperty([1, 1, 1, 1])
    c_text = ListProperty([1, 1, 1, 1])
    c_hint = ListProperty([1, 1, 1, 1])
    c_btn = ListProperty([0.2, 0.2, 0.3, 1])
    c_btn_fg = ListProperty([1, 1, 1, 1])
    c_spin = ListProperty([1, 0.8, 0.2, 1])
    c_spin_fg = ListProperty([0, 0, 0, 1])

    # ------------------------------------------------------------------ жизненный цикл
    def build(self):
        Builder.load_string(KV)
        self.root_widget = Root()
        self.wheel = self.root_widget.ids.wheel
        self.bg = self.root_widget.ids.bg
        saved = self._load()
        self.state = FortuneState(saved.get("options", []), saved.get("elim_on", False))
        self.spins = int(saved.get("spins", 0))
        self.sound_on = bool(saved.get("sound", True))
        self.elim_on = self.state.elim_on
        self.feedback = Feedback(os.path.join(self.user_data_dir, "sfx"))
        self.feedback.enabled = self.sound_on

        self.wheel.bind(on_peg=lambda _w, speed: self.feedback.tick(speed),
                        on_finished=lambda _w, idx: self._on_finished(idx),
                        on_tap=lambda _w: self.spin())
        self._card = self._options_view = self._styles_view = None
        self._elim_ev = None
        self._apply_theme(saved.get("theme", "classic"))
        self._refresh_wheel()
        self.bg.start()
        Window.bind(on_keyboard=self._on_key)
        return self.root_widget

    def on_pause(self):
        self._save()
        self.feedback.ambient_stop()
        self.bg.stop()
        return True

    def on_resume(self):
        self.bg.start()

    def on_stop(self):
        self._save()
        self.feedback.ambient_stop()
        self.bg.stop()
        self.wheel.stop()

    def _on_key(self, _win, key, *_args):          # кнопка «Назад» на Android
        if key == 27:
            for view in (self._card, self._options_view, self._styles_view):
                if view is not None and getattr(view, "_is_open", False):
                    view.dismiss()
                    return True
        return False

    # ------------------------------------------------------------------ сохранение
    def _path(self):
        return os.path.join(self.user_data_dir, STATE_FILE)

    def _load(self):
        try:
            with open(self._path(), encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            return {}

    def _save(self):
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self._path(), "w", encoding="utf-8") as f:
                json.dump({"options": self.state.opts, "elim_on": self.state.elim_on, "theme": self.theme_name,
                           "sound": self.sound_on, "spins": int(self.spins)}, f, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            print("Не удалось сохранить состояние:", e)

    # ------------------------------------------------------------------ тема
    def _apply_theme(self, name):
        if name not in THEMES:
            name = "classic"
        self.theme_name = name
        th = THEMES[name]
        ui = th["ui"]
        self.title_text = th["title"]
        self.intro_text = "«" + INTRO_TEXTS[name] + "»"
        self.c_bg = get_color_from_hex(ui["bg"])
        self.c_title = get_color_from_hex(ui["title"])
        self.c_text = get_color_from_hex(ui["text"])
        self.c_hint = get_color_from_hex(ui["hint"])
        self.c_btn = get_color_from_hex(ui["btn"])
        self.c_btn_fg = get_color_from_hex(ui["btn_fg"])
        self.c_spin = get_color_from_hex(ui["spin"])
        self.c_spin_fg = get_color_from_hex(ui["spin_fg"])
        Window.clearcolor = self.c_bg
        self.wheel.set_theme(name)
        self.bg.set_theme(name)                     # свой анимированный фон у каждого стиля
        self.feedback.set_theme(name)               # свой набор звуков у каждого стиля
        self._update_subtitle()

    def _update_subtitle(self):
        self.subtitle = f"Прокручено раз: {int(self.spins)}"

    # ------------------------------------------------------------------ колесо
    def _refresh_wheel(self):
        self.wheel.set_options(self.state.wheel_options())
        self.option_count = len(self.state.opts)
        self.has_options = self.state.can_spin
        if not self.has_options:
            self.status = NO_OPTIONS_HINT
        elif self.status == NO_OPTIONS_HINT:
            self.status = ""

    def spin(self):
        if self.busy or not self.state.can_spin:
            return
        self.status = self.state.prepare_spin()
        self._hide_card()
        self._refresh_wheel()                      # колесо показывает актуальный пул (после сброса круга)
        self.busy = True
        if self.wheel.spin():
            self.feedback.ambient_start()
        else:
            self.busy = False

    def _on_finished(self, index):
        self.feedback.ambient_stop()
        self.spins += 1
        self._update_subtitle()
        self._save()
        res = self.state.on_finished(index)
        if res["kind"] == "eliminate":
            # «На выбывание»: сектор подсвечен, карточка сообщает о выбывании, через паузу вариант убирается
            self.feedback.tick(260.0)
            self._show_card(res["text"], res["top"], res["sub"])
            self._elim_ev = Clock.schedule_once(self._apply_elimination, res["delay"])
            return
        self.busy = False
        self.feedback.win()
        self._show_card(res["text"])

    def _apply_elimination(self, _dt):
        self._elim_ev = None
        res = self.state.apply_elimination()
        self._hide_card()
        self.wheel.set_options(res["options"])
        self.busy = False
        if res["done"]:                            # остался один вариант — он и есть судьба
            self.wheel.highlight(0)
            self.status = "Остался один вариант."
            self.feedback.win()
            self._show_card(res["text"])
        else:
            self.status = f"Осталось вариантов: {res['remaining']}"

    # ------------------------------------------------------------------ карточка победы
    def _show_card(self, text, top=None, sub=None):
        self._hide_card()
        th = THEMES[self.theme_name]
        ui = th["ui"]
        # background_color с альфой 0: иначе ModalView рисует свой тёмный прямоугольник,
        # и его углы торчат из-под скруглённой карточки
        view = ModalView(size_hint=(0.88, None), height=dp(280), auto_dismiss=True,
                         background="", background_color=(0, 0, 0, 0), overlay_color=(0, 0, 0, 0.35))
        box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(8))
        with box.canvas.before:
            Color(*get_color_from_hex(ui["card"]))
            bg = RoundedRectangle(radius=[dp(22)])
            Color(*get_color_from_hex(ui["card_border"]))
            border = Line(rounded_rectangle=(0, 0, 10, 10, dp(22)), width=dp(2))

        def _upd(*_a):
            bg.pos, bg.size = box.pos, box.size
            border.rounded_rectangle = (box.x, box.y, box.width, box.height, dp(22))
        box.bind(pos=_upd, size=_upd)

        def mk(txt, size, color, bold=False, h=None):
            lb = Label(text=txt, font_size=size, color=get_color_from_hex(color), bold=bold,
                       halign="center", valign="middle", size_hint_y=None if h else 1)
            if h:
                lb.height = h
            lb.bind(width=lambda w, v: setattr(w, "text_size", (v, None if h else w.height)))
            return lb
        box.add_widget(mk(top if top is not None else th["win_top"], "15sp", ui["card_top"], True, dp(40)))
        box.add_widget(mk(text, "28sp", ui["card_text"], True))
        box.add_widget(mk(sub if sub is not None else th["win_sub"], "13sp", ui["card_top"], False, dp(34)))
        ok = Button(text="Ок", size_hint_y=None, height=dp(48), background_normal="", background_down="",
                    background_color=(0, 0, 0, 0), color=self.c_spin_fg, bold=True, font_size="18sp")
        with ok.canvas.before:
            Color(*self.c_spin)
            ok_bg = RoundedRectangle(radius=[dp(14)])
        ok.bind(pos=lambda w, v: setattr(ok_bg, "pos", v), size=lambda w, v: setattr(ok_bg, "size", v))
        ok.bind(on_release=lambda *_: view.dismiss())
        box.add_widget(ok)
        view.add_widget(box)
        view.opacity = 0
        view.open()
        Animation(opacity=1, duration=0.7, t="in_out_sine").start(view)
        self._card = view

    def _hide_card(self):
        if self._card is not None:
            try:
                self._card.dismiss(animation=False)
            except Exception:  # noqa: BLE001
                pass
            self._card = None

    # ------------------------------------------------------------------ переключатели
    def toggle_elim(self):
        if self.busy:
            return
        self.state.set_elim(not self.state.elim_on)
        self.elim_on = self.state.elim_on
        self._hide_card()
        self.status = ("После каждой крутки один вариант выбывает — пока не останется один."
                       if self.elim_on else "")
        self._refresh_wheel()
        self._save()

    def toggle_sound(self):
        self.sound_on = not self.sound_on
        self.feedback.enabled = self.sound_on
        if not self.sound_on:
            self.feedback.ambient_stop()
        self._save()

    # ------------------------------------------------------------------ окно «Варианты судьбы»
    def open_options(self):
        if self.busy:
            return
        view = ModalView(size_hint=(0.96, 0.92), background="", background_color=self.c_bg,
                         overlay_color=(0, 0, 0, 0.6))
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        with root.canvas.before:
            Color(*self.c_bg)
            rect = Rectangle()
        root.bind(pos=lambda w, v: setattr(rect, "pos", v), size=lambda w, v: setattr(rect, "size", v))

        root.add_widget(Label(text="Варианты судьбы", font_size="20sp", bold=True, color=self.c_title,
                              size_hint_y=None, height=dp(36)))
        hint = Label(text="Впишите свои варианты, и Госпожа Удача решит всё за вас.", font_size="13sp",
                     color=self.c_hint, size_hint_y=None, height=dp(36), halign="center")
        hint.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
        root.add_widget(hint)

        scroll = ScrollView(do_scroll_x=False)
        rows = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        rows.bind(minimum_height=rows.setter("height"))
        scroll.add_widget(rows)
        root.add_widget(scroll)

        msg = Label(text="", font_size="13sp", color=self.c_hint, size_hint_y=None, height=dp(22))
        root.add_widget(msg)

        def fill():
            rows.clear_widgets()
            for i, text in enumerate(self.state.opts):
                row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
                ti = TextInput(text=text, multiline=False, write_tab=False, font_size="16sp",
                               padding=(dp(10), dp(12)))
                ti.bind(on_text_validate=lambda w, i=i: commit(i, w))
                ti.bind(focus=lambda w, f, i=i: (not f) and commit(i, w))
                dl = Button(text="×", size_hint_x=None, width=dp(48), font_size="22sp", bold=True,
                            background_normal="", background_down="", background_color=self.c_btn,
                            color=self.c_btn_fg)
                dl.bind(on_release=lambda _b, i=i: delete(i))
                row.add_widget(ti)
                row.add_widget(dl)
                rows.add_widget(row)

        def after_change(text=""):
            msg.text = text
            self._refresh_wheel()
            self._save()

        def commit(i, widget):
            if i >= len(self.state.opts):
                return
            ok, text = self.state.edit_option(i, widget.text)
            if not ok:
                widget.text = self.state.opts[i]
            after_change(text)

        def delete(i):
            ok, text = self.state.delete_option(i)
            fill()
            after_change(text)

        def add(*_a):
            ok, text = self.state.add_option(new.text)
            if ok:
                new.text = ""
                fill()
                Clock.schedule_once(lambda _dt: setattr(scroll, "scroll_y", 0), 0.05)
            after_change(text)

        add_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        new = TextInput(hint_text="Новый вариант…", multiline=False, write_tab=False, font_size="16sp",
                        padding=(dp(10), dp(12)))
        new.bind(on_text_validate=add)
        add_btn = Button(text="Добавить", size_hint_x=None, width=dp(110), bold=True, background_normal="",
                         background_down="", background_color=self.c_spin, color=self.c_spin_fg)
        add_btn.bind(on_release=add)
        add_row.add_widget(new)
        add_row.add_widget(add_btn)
        root.add_widget(add_row)

        bar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        for label, fn in (("Примерные", lambda: self.state.reset_defaults()),
                          ("Очистить всё", lambda: self.state.clear())):
            b = Button(text=label, background_normal="", background_down="", background_color=self.c_btn,
                       color=self.c_btn_fg, bold=True)

            def handler(_b, fn=fn):
                text = fn()
                fill()
                after_change(text)
            b.bind(on_release=handler)
            bar.add_widget(b)
        close = Button(text="Готово", background_normal="", background_down="", background_color=self.c_spin,
                       color=self.c_spin_fg, bold=True)
        close.bind(on_release=lambda *_: view.dismiss())
        bar.add_widget(close)
        root.add_widget(bar)

        view.add_widget(root)
        fill()
        view.bind(on_dismiss=lambda *_: self._save())
        self._options_view = view
        view.open()

    # ------------------------------------------------------------------ окно «Стиль»
    def open_styles(self):
        if self.busy:
            return
        view = ModalView(size_hint=(0.86, None), height=dp(64 + 58 * len(THEME_ORDER)), auto_dismiss=True,
                         background="", background_color=self.c_bg, overlay_color=(0, 0, 0, 0.6))
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        with box.canvas.before:
            Color(*self.c_bg)
            rect = Rectangle()
        box.bind(pos=lambda w, v: setattr(rect, "pos", v), size=lambda w, v: setattr(rect, "size", v))
        box.add_widget(Label(text="Стиль колеса", font_size="18sp", bold=True, color=self.c_title,
                             size_hint_y=None, height=dp(36)))
        for key in THEME_ORDER:
            # без «галочки»: символа ✓ нет в шрифте Roboto, вместо него рисовался квадратик
            name = THEMES[key]["name"] + ("  (выбран)" if key == self.theme_name else "")
            ui = THEMES[key]["ui"]
            b = Button(text=name, background_normal="", background_down="", bold=True, font_size="16sp",
                       background_color=get_color_from_hex(ui["bg"]), color=get_color_from_hex(ui["title"]),
                       size_hint_y=None, height=dp(50))
            b.bind(on_release=lambda _b, k=key: (self._apply_theme(k), self._save(), view.dismiss()))
            box.add_widget(b)
        view.add_widget(box)
        self._styles_view = view
        view.open()


if __name__ == "__main__":
    FortuneApp().run()
