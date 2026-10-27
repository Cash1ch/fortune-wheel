# Колесо Фортуны — Android (Kivy)

Порт «Колеса Фортуны» из NTE Wish Tracker (`main.py`, строки ~15280–17100).

## Структура

| Файл | Что внутри |
|---|---|
| `fortune_core.py` | Физика колеса (3 профиля торможения, штифты, откат), состояние, режим «На выбывание», 4 темы. Без Kivy — тестируется на ПК |
| `wheel_widget.py` | Виджет колеса: рисование, анимация вращения, качание стрелки, подсветка победителя, тап = крутить |
| `sounds.py` | Синтез WAV (щелчок, победный перезвон), пул звуков, вибрация (plyer) |
| `main.py` | Приложение: экран, «Варианты», «Стиль», карточка победы, сохранение состояния |
| `buildozer.spec` | Конфиг сборки APK |
| `tests/test_core.py` | Тесты ядра (`pytest`) |

## Проверка на ПК (до сборки)

```bash
pip install kivy plyer pytest
pytest -q tests          # тесты физики и логики
python main.py           # окно 400x780, как телефон
```

## Сборка APK

Buildozer работает на **Linux** (или Windows через WSL2 / Google Colab).

```bash
# Ubuntu / WSL2
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo6 cmake libffi-dev libssl-dev
pip install --user buildozer "cython==0.29.36"

cd fortune_wheel
buildozer -v android debug          # первая сборка 20–40 мин (качает SDK/NDK)
# результат: bin/fortunewheel-1.0.0-arm64-v8a-debug.apk
```

Установка на телефон (включите «Отладку по USB»):

```bash
buildozer android deploy run logcat
```

или скопируйте APK на телефон и откройте его (разрешите установку из неизвестных источников).

Для публикации в Google Play: `buildozer android release`, затем подпишите AAB/APK своим ключом.
Если нужны телефоны с 32-битным ARM, поменяйте `android.archs = arm64-v8a, armeabi-v7a`.

## Настройки в коде

- `fortune_core.FIX_ROLLBACK` — `True` (по умолчанию): исправленный откат колеса от штифта;
  `False` — поведение 1 в 1 как в оригинале.
- `fortune_core.MAX_OPTIONS` — максимум вариантов (24, как в оригинале).
- `sounds.Feedback.TICK_MIN_GAP` — минимальный интервал между щелчками.
