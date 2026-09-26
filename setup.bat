@echo off
rem InkForge -- перший запуск (Windows).
rem Подвійний клік на цьому файлі: створює віртуальне середовище Python і
rem встановлює InkForge разом з усім потрібним для launcher-а (Рівень 3).
rem Потрібно виконати лише один раз (або повторно -- після оновлення проєкту).

setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ПОМИЛКА] Python не знайдено в PATH.
    echo Встанови Python з https://www.python.org/downloads/ -- і обов'язково
    echo постав галочку "Add python.exe to PATH" на першому екрані інсталятора.
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Створюю віртуальне середовище...
    python -m venv .venv
    if errorlevel 1 (
        echo [ПОМИЛКА] Не вдалося створити віртуальне середовище.
        pause
        exit /b 1
    )
)

echo Встановлюю InkForge та залежності launcher-а...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
call ".venv\Scripts\pip.exe" install -e ".[launcher]"
if errorlevel 1 (
    echo [ПОМИЛКА] Встановлення не вдалося -- див. повідомлення вище.
    pause
    exit /b 1
)

echo.
echo Готово! Тепер запускай InkForge подвійним кліком на start_launcher.bat
pause
