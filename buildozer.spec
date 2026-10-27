[app]
title = Колесо Фортуны
package.name = fortunewheel
package.domain = org.fortune
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = tests,bin,.buildozer,__pycache__
version = 1.0.0

# kivy 2.3.0 — стабильная связка с python-for-android; plyer нужен только для вибрации
requirements = python3,kivy==2.3.0,plyer

orientation = portrait
fullscreen = 0

# VIBRATE — тактильный отклик на щелчках штифтов и при победе
android.permissions = VIBRATE
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
