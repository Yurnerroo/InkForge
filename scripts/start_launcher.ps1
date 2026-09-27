# InkForge -- запуск one-click launcher-а (Рівень 3).
# Спершу треба один раз запустити setup.bat (створює віртуальне середовище).
#
# Цей файл викликається з start_launcher.bat -- не запускай його напряму,
# якщо не знаєш, що робиш.

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
Set-Location $root

function Wait-ForExit {
    param([int]$Code)
    Read-Host "Натисни Enter, щоб закрити"
    exit $Code
}

if (-not (Test-Path ".venv\Scripts\inkforge-launcher.exe")) {
    Write-Host "[ПОМИЛКА] Віртуальне середовище не знайдено або InkForge не встановлено." -ForegroundColor Red
    Write-Host "Спершу запусти setup.bat -- і лише потім цей файл."
    Wait-ForExit 1
}

Write-Host "Запускаю InkForge... За кілька секунд відкриється браузер."
Write-Host "Це вікно НЕ закривати, поки триває робота з InkForge."
& ".venv\Scripts\inkforge-launcher.exe"
Wait-ForExit 0
