@echo off
rem InkForge -- запуск one-click launcher-а (Рівень 3).
rem Подвійний клік на цьому файлі щоразу, коли треба зверстати новий випуск.
rem Спершу треба один раз запустити setup.bat (створює віртуальне середовище).

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\inkforge-launcher.exe" (
    echo [ПОМИЛКА] Віртуальне середовище не знайдено або InkForge не встановлено.
    echo Спершу запусти setup.bat -- і лише потім цей файл.
    pause
    exit /b 1
)

echo Запускаю InkForge... За кілька секунд відкриється браузер.
echo Це вікно НЕ закривати, поки триває робота з InkForge.
".venv\Scripts\inkforge-launcher.exe"
pause
