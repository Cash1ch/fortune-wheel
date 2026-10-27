[app]
title = Колесо Фортуны
package.name = fortunewheel
package.domain = org.fortune
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = tests,bin,.buildozer,__pycache__
version = 1.0.0

requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,plyer

orientation = portrait
fullscreen = 0

android.permissions = VIBRATE
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
