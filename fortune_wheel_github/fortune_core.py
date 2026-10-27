# -*- coding: utf-8 -*-
"""Ядро «Колеса Фортуны»: физика, состояние, режим «На выбывание», темы.

Не зависит от Kivy — поэтому тестируется обычным pytest на ПК.
Портировано из FortuneWheel / FortuneDialog (NTE Wish Tracker, main.py).

Соглашения те же, что в оригинале: угол rot — по часовой стрелке (градусы),
сектор i занимает [i·S, (i+1)·S) от «верха» колеса, указатель смотрит на
точку (-rot) mod 360 в системе колеса.
"""
import math
import random

# Оригинал: при «упоре в штифт» колесо ставилось на 0.001° ЗА штифт (знак +), из-за чего
# откат не происходил и колесо всегда заканчивало в следующем секторе. True — исправлено:
# колесо остаётся перед штифтом и откатывается. False — поведение 1 в 1 как в оригинале.
FIX_ROLLBACK = True

MIN_OPTIONS, MAX_OPTIONS = 1, 24

DEFAULT_OPTIONS = ("Да, действуй!", "Нет, не стоит", "Подожди до завтра", "Рискни!",
                   "Спроси совета у друга", "Сделай первый шаг", "Отложи на неделю",
                   "Доверься интуиции")

INTRO_TEXTS = {
    "classic": ("Сомневаешься? Боишься сделать шаг, который изменит всё? Не пытайся предугадать судьбу - "
                "доверься ей. Передай бразды правления в надёжные руки Госпожи Фортуны. "
                "Пусть её колесо решит за тебя. Крути и узнай, что уготовано."),
    "nte": ("Хватит строить из себя героя. В Этеро удача решает всё: от утреннего кофе до того, "
            "доживёшь ли ты до следующего заказа. Боишься, что твой выбор всё сломает? Расслабься. "
            "Отдайся в надёжные объятия Госпожи Фортуны - она хотя бы честно играет по своим правилам."),
    "sakura": ("Лепесток сакуры не выбирает, куда упасть, — его несёт ветер судьбы. "
               "Так и ты: не спорь с небом, прими дары, что протягивает тебе Госпожа Фортуна."),
    "paws": ("Кто сказал, что маленькие лапки не решают большие судьбы? Ещё как решают - просто делают это мило. "
             "Пусть Госпожа Фортуна улыбнётся - а ты просто наслаждайся подарком."),
}

CLASSIC_COLORS = ("#e94f64", "#f0a43c", "#f2d24b", "#5cc47a", "#3fb7c9", "#4a7be8",
                  "#8a5ce0", "#d65bb8", "#ff7a59", "#7bd0a0")

# Палитры колеса — 1 в 1 из FORTUNE_THEMES[...]["wheel"]. Поля "ui" — палитра интерфейса приложения
# (кнопки/фон/заголовок): значения из оригинала там, где они были заданы простыми цветами,
# остальное подобрано в тон.
THEMES = {
    "classic": {
        "name": "Классика", "title": "КОЛЕСО ФОРТУНЫ", "win_top": "ВЫПАЛО",
        "win_sub": "Госпожа решила твою судьбу",
        "ui": {"bg": "#120c24", "title": "#ffd98a", "text": "#f6e7bd", "hint": "#b8a8d8",
               "btn": "#3b2a66", "btn_fg": "#f3ecff", "spin": "#e8b542", "spin_fg": "#3b2400",
               "card": "#34204f", "card_border": "#ffe27a", "card_top": "#ffd98a", "card_text": "#ffffff"},
        "wheel": {"colors": CLASSIC_COLORS, "edge": (30, 20, 50, 200), "aura": (255, 210, 110),
                  "rim": "#d9b45a", "rim2": None, "peg": ("#fff6cf", "#b8892a"),
                  "hub": ("#fff2b8", "#b8892a", "#6b4a14"), "star": "#6b4a14",
                  "ptr": ("#ffcf4a", "#4a2a00", "#fff2b8"), "win": (255, 240, 160),
                  "win_edge": (255, 226, 122), "text_dark": "#1b1230", "text_light": "#ffffff",
                  "rim_glow": None, "rim_w": 0.045, "ptr_sharp": False, "dim": (10, 6, 25, 140)},
    },
    "nte": {
        "name": "NTE (неон)", "title": "NTE FORTUNE WHEEL", "win_top": "ВЫПАЛО",
        "win_sub": "ГОСПОЖА РЕШИЛА ТВОЮ СУДЬБУ",
        "ui": {"bg": "#0d0c1d", "title": "#00f0ff", "text": "#cfd6ff", "hint": "#6f7aa8",
               "btn": "#2b2a4a", "btn_fg": "#9fe9ff", "spin": "#ff2a8d", "spin_fg": "#ffffff",
               "card": "#19142d", "card_border": "#00f0ff", "card_top": "#ff4fa3", "card_text": "#ffffff"},
        "wheel": {"colors": ("#00e5ff", "#ff2a8d", "#9b5cff", "#ffc83d", "#2b3a6b"),
                  "edge": (13, 12, 29, 230), "aura": (0, 240, 255), "rim": "#00f0ff", "rim2": "#ff2a8d",
                  "peg": ("#eaffff", "#00a8c8"), "hub": ("#2a2062", "#0d0c1d", "#00f0ff"),
                  "star": "#ff2a8d", "ptr": ("#ff2a8d", "#00f0ff", "#ffffff"), "win": (0, 240, 255),
                  "win_edge": (255, 42, 141), "text_dark": "#0d0c1d", "text_light": "#ffffff",
                  "rim_glow": "#00f0ff", "rim_w": 0.032, "ptr_sharp": True, "dim": (10, 6, 25, 140)},
    },
    "sakura": {
        "name": "Сакура", "title": "КОЛЕСО ФОРТУНЫ", "win_top": "СУДЬБА ОПУСТИЛАСЬ КАК ЛЕПЕСТОК САКУРЫ",
        "win_sub": "Госпожа решила твою судьбу",
        "ui": {"bg": "#fff0f5", "title": "#dc143c", "text": "#4a1020", "hint": "#a47c86",
               "btn": "#f6cdd8", "btn_fg": "#4a1020", "spin": "#dc143c", "spin_fg": "#ffffff",
               "card": "#fff9fb", "card_border": "#e6ca65", "card_top": "#dc143c", "card_text": "#4a1020"},
        "wheel": {"colors": ("#ffb7c5", "#d63a5c", "#fff6ea", "#ffc9a8", "#e6ca65", "#b8735c"),
                  "edge": (255, 255, 255, 235), "aura": (255, 183, 197), "rim": "#e6ca65", "rim2": "#dc143c",
                  "peg": ("#fff6ea", "#e6ca65"), "hub": ("#fff6ea", "#ffb7c5", "#e6ca65"),
                  "star": "#dc143c", "ptr": ("#dc143c", "#e6ca65", "#fff6ea"), "win": (255, 255, 255),
                  "win_edge": (220, 20, 60), "text_dark": "#4a1020", "text_light": "#ffffff",
                  "rim_glow": "#ff8fa8", "rim_w": 0.04, "ptr_sharp": True, "dim": (10, 6, 25, 140)},
    },
    "paws": {
        "name": "Белые лапки", "title": "КОЛЕСО ФОРТУНЫ", "win_top": "МИЛАЯ ЛАПКА РЕШИЛА ТВОЮ СУДЬБУ",
        "win_sub": "Госпожа решила твою судьбу",
        "ui": {"bg": "#fdfbf7", "title": "#8b5e3c", "text": "#4a3220", "hint": "#a89580",
               "btn": "#ece0cb", "btn_fg": "#4a2a12", "spin": "#e0a068", "spin_fg": "#4a2a12",
               "card": "#fffdf8", "card_border": "#d9a86a", "card_top": "#b9794a", "card_text": "#4a2e1a"},
        "wheel": {"colors": ("#f7d9c4", "#e8b04f", "#fff6e6", "#8b5e3c", "#e6b89c", "#d9c3a9", "#f4ecd8", "#b9794a"),
                  "edge": (253, 251, 247, 240), "aura": (240, 200, 160), "rim": "#c9a27a", "rim2": "#e6b89c",
                  "peg": ("#fff6e6", "#d9c3a9"), "hub": ("#fff6e6", "#f4d9c2", "#c9a27a"),
                  "star": "#8b5e3c", "ptr": ("#e0a95a", "#6b4423", "#fff3d6"), "win": (255, 240, 200),
                  "win_edge": (184, 115, 70), "text_dark": "#4a2e1a", "text_light": "#fffaf0",
                  "rim_glow": "#f0c9a0", "rim_w": 0.042, "ptr_sharp": False, "dim": (120, 84, 52, 105)},
    },
}
THEME_ORDER = ("classic", "nte", "sakura", "paws")


# ----------------------------------------------------------------------------
# Физика колеса
# ----------------------------------------------------------------------------
class WheelPhysics:
    """Вращение с инерцией, штифтами на границах секторов, тремя профилями торможения."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.n = 0
        self.rot = self.rng.uniform(0.0, 360.0)   # случайный стартовый угол
        self.omega = 0.0                          # град/с, >0 — по часовой
        self.spinning = False
        self.winner = -1
        self.flap = 0.0                           # отклонение стрелки от щелчка штифта (0..1)
        self.profile = None
        self.rolling_back = False
        self.spin_time = 0.0

    # ---- данные ----
    def set_count(self, n):
        if self.spinning:
            return False
        self.n = max(0, int(n))
        self.winner = -1
        return True

    @property
    def sector(self):
        return 360.0 / max(1, self.n)

    def pointer_index(self):
        n = max(1, self.n)
        p = (-self.rot) % 360.0
        return min(n - 1, int(p // self.sector))

    # ---- запуск ----
    def start(self):
        if self.spinning or self.n < MIN_OPTIONS:
            return False
        r = self.rng
        kind = r.choices(("quick", "gradual", "suspense"), weights=(3, 3, 4))[0]
        if kind == "quick":        # быстро раскрутили и быстро остановили
            self.omega = r.uniform(650, 980)
            self.profile = {"c1": r.uniform(30, 55), "c2": r.uniform(1.5, 2.3),
                            "vc": 70.0, "k": r.uniform(1300, 2200), "kind": kind}
        elif kind == "gradual":    # долгий плавный накат
            self.omega = r.uniform(950, 1400)
            self.profile = {"c1": r.uniform(8, 16), "c2": r.uniform(0.30, 0.50),
                            "vc": 70.0, "k": r.uniform(1200, 2000), "kind": kind}
        else:                      # «интрига»: ползёт у штифтов, может откатиться
            self.omega = r.uniform(800, 1150)
            self.profile = {"c1": r.uniform(9, 16), "c2": r.uniform(0.55, 0.85),
                            "vc": 95.0, "k": r.uniform(2200, 3600), "kind": kind}
        self.spinning = True
        self.winner = -1
        self.rolling_back = False
        self.spin_time = 0.0
        return True

    # ---- шаг ----
    def update(self, dt):
        """Продвигает физику на dt секунд. Возвращает список событий:
        ("peg", скорость) — щелчок штифта;  ("finish", индекс_победителя) — остановка."""
        events = []
        dt = min(max(dt, 0.0), 0.05)
        self.spin_time += dt
        steps = max(1, math.ceil(dt / 0.005))     # подшаги по 5 мс: не пропустить штифт на скорости
        for _ in range(steps):
            if not self.spinning:
                break
            self._step(dt / steps, events)
        self.flap = max(0.0, self.flap - dt * 5.0)
        return events

    def _step(self, h, events):
        prof = self.profile
        c1, c2 = prof["c1"], prof["c2"]
        if self.spin_time > 22.0:                 # страховка: слишком долгий накат гасим принудительно
            c1 += 40.0
        s = self.sector
        if not self.rolling_back:
            self.omega = max(0.0, self.omega - (c1 + c2 * self.omega) * h)
            old = math.floor((-self.rot) / s)
            new_rot = self.rot + self.omega * h
            new = math.floor((-new_rot) / s)
            if new < old:                         # пересекли штифт на границе сектора
                if self.omega < prof["vc"]:       # на малой скорости штифт отнимает энергию
                    v2 = self.omega ** 2 - prof["k"]
                    if v2 <= 0:                   # не хватило сил: упёрлись и откатываемся назад
                        eps = -0.001 if FIX_ROLLBACK else 0.001
                        self.rot = -old * s + eps
                        self.omega = -self.rng.uniform(7.0, 14.0)
                        self.rolling_back = True
                        self.flap = 0.6
                        events.append(("peg", 20.0))
                        return
                    self.omega = math.sqrt(v2)
                self.flap = 1.0
                events.append(("peg", self.omega))
            self.rot = new_rot
        else:                                     # откат: трение гасит скорость, назад через штифт не идём
            self.omega = min(0.0, self.omega + (c1 + 1.2 * abs(self.omega)) * h)
            s_old = math.floor((-self.rot) / s)
            new_rot = self.rot + self.omega * h
            if math.floor((-new_rot) / s) > s_old:
                self.omega = 0.0
            else:
                self.rot = new_rot
        if abs(self.omega) < 0.8:
            self._finish(events)

    def _finish(self, events):
        self.omega = 0.0
        self.spinning = False
        self.rolling_back = False
        s = self.sector
        frac = ((-self.rot) % 360.0) % s          # не оставляем колесо точно на границе сектора
        if frac < 0.4:
            self.rot -= (0.6 - frac)
        elif frac > s - 0.4:
            self.rot += (0.6 - (s - frac))
        self.winner = self.pointer_index()
        events.append(("finish", self.winner))


# ----------------------------------------------------------------------------
# Состояние: список вариантов и режим «На выбывание»
# ----------------------------------------------------------------------------
class FortuneState:
    def __init__(self, options=None, elim_on=False):
        self.opts = list(options or [])[:MAX_OPTIONS]
        self.elim_on = bool(elim_on)
        self._reset_run()

    # ---- круг «На выбывание» ----
    def _reset_run(self):
        self.pool = list(range(len(self.opts)))   # индексы вариантов, которые ещё на колесе
        self.eliminated = set()
        self.run_done = False
        self.pending = -1                         # индекс (на колесе) выбывающего варианта

    def wheel_options(self):
        return [self.opts[i] for i in self.pool]

    def set_elim(self, on):
        self.elim_on = bool(on)
        self._reset_run()

    # ---- редактирование (как _add_option / _delete_option / ... в оригинале) ----
    def add_option(self, text):
        text = (text or "").strip()[:60]
        if not text:
            return False, "Введите текст нового варианта."
        if len(self.opts) >= MAX_OPTIONS:
            return False, f"Максимум вариантов: {MAX_OPTIONS}."
        self.opts.append(text)
        self._reset_run()
        return True, ""

    def delete_option(self, row):
        if not 0 <= row < len(self.opts):
            return False, "Выберите вариант, который нужно удалить."
        del self.opts[row]
        self._reset_run()
        return True, ""

    def edit_option(self, row, text):
        text = (text or "").strip()[:60]
        if not 0 <= row < len(self.opts):
            return False, ""
        if not text:
            return False, "Вариант не может быть пустым."
        if text != self.opts[row]:
            self.opts[row] = text
            self._reset_run()
        return True, ""

    def reset_defaults(self):
        self.opts = list(DEFAULT_OPTIONS)
        self._reset_run()
        return "Подставлены примерные варианты — измените их или очистите список."

    def clear(self):
        self.opts = []
        self._reset_run()
        return "Список очищен: впишите свои варианты."

    # ---- вращение ----
    @property
    def can_spin(self):
        return len(self.opts) >= MIN_OPTIONS

    def prepare_spin(self):
        """Вызывать перед wheel.spin(). Возвращает текст статуса."""
        if self.elim_on and len(self.opts) >= 2 and (self.run_done or len(self.pool) < 2):
            self._reset_run()                     # прошлый круг закончен — новый со всеми вариантами
        if self.elim_on and len(self.pool) >= 2:
            return f"Осталось вариантов: {len(self.pool)}"
        return ""

    def on_finished(self, index):
        """Колесо остановилось на секторе index (индекс среди wheel_options())."""
        if self.elim_on and len(self.pool) > 1 and 0 <= index < len(self.pool):
            self.pending = index
            return {"kind": "eliminate", "text": self.opts[self.pool[index]], "top": "ВЫБЫВАЕТ",
                    "sub": f"Осталось вариантов: {len(self.pool) - 1}", "delay": 1.9}
        shown = self.wheel_options()
        text = shown[index] if 0 <= index < len(shown) else ""
        return {"kind": "win", "text": text}

    def apply_elimination(self):
        """Через паузу убирает выбывший вариант; когда остался один — он и есть победитель."""
        index, self.pending = self.pending, -1
        if not 0 <= index < len(self.pool):
            return {"done": False, "options": self.wheel_options(), "remaining": len(self.pool)}
        self.eliminated.add(self.pool.pop(index))
        res = {"done": False, "options": self.wheel_options(), "remaining": len(self.pool)}
        if len(self.pool) == 1:
            self.run_done = True
            res["done"] = True
            res["text"] = self.opts[self.pool[0]]
        return res
