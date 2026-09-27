@echo off
chcp 65001 >nul
rem InkForge -- перший запуск (Windows).
rem Подвійний клік на цьому файлі: створює віртуальне середовище Python і
rem встановлює InkForge разом з усім потрібним для launcher-а (Рівень 3).
rem Потрібно виконати лише один раз (або повторно -- після оновлення проєкту).

setlocal
cd /d "%~dp0"

rem Різні способи встановлення Python реєструють різну команду в PATH:
rem старий інсталятор -- "python", новий Python Install Manager -- лише "py".
rem Пробуємо обидва, від новішого до старшого.
set "PY_CMD="
where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD (
    py -3 --version >nul 2>nul && set "PY_CMD=py -3"
)
if not defined PY_CMD (
    py --version >nul 2>nul && set "PY_CMD=py"
)

if not defined PY_CMD (
    echo [ПОМИЛКА] Python не знайдено.
    echo Встанови Python з https://www.python.org/downloads/ -- і обов'язково
    echo постав галочку "Add python.exe to PATH" на першому екрані інсталятора.
    echo Якщо встановлював через Python Install Manager -- відкрий PowerShell і
    echo виконай: py install 3.13
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Створюю віртуальне середовище...
    %PY_CMD% -m venv .venv
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
