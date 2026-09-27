# InkForge -- перший запуск (Windows).
# Створює віртуальне середовище Python і встановлює InkForge разом з усім
# потрібним для launcher-а (Рівень 3). Запускати один раз (або повторно --
# після оновлення проєкту).
#
# Цей файл викликається з setup.bat -- не запускай його напряму, якщо не
# знаєш, що робиш.

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
Set-Location $root

function Test-PyCandidate {
    param([string]$Exe, [string[]]$PreArgs)
    try {
        & $Exe @PreArgs --version *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Wait-ForExit {
    param([int]$Code)
    Read-Host "Натисни Enter, щоб закрити"
    exit $Code
}

# Різні способи встановлення Python реєструють різні команди в PATH.
# Новий офіційний Python Install Manager дає лише робочий "py"/"py -3" --
# пробуємо їх першими. "python" перевіряємо останнім і саме запуском
# "--version", бо на деяких машинах "python" у PATH -- це лише заглушка
# Microsoft Store (WindowsApps\python.exe), яка знаходиться через "where",
# але нічого корисного не виконує.
$pyExe = $null
$pyPreArgs = @()

if (Test-PyCandidate -Exe 'py' -PreArgs @('-3')) {
    $pyExe = 'py'; $pyPreArgs = @('-3')
} elseif (Test-PyCandidate -Exe 'py' -PreArgs @()) {
    $pyExe = 'py'; $pyPreArgs = @()
} elseif (Test-PyCandidate -Exe 'python' -PreArgs @()) {
    $pyExe = 'python'; $pyPreArgs = @()
}

if (-not $pyExe) {
    Write-Host "[ПОМИЛКА] Python не знайдено." -ForegroundColor Red
    Write-Host "Встанови Python з https://www.python.org/downloads/ -- і обов'язково"
    Write-Host 'постав галочку "Add python.exe to PATH" на першому екрані інсталятора.'
    Write-Host "Якщо встановлював через Python Install Manager -- відкрий PowerShell і"
    Write-Host "виконай: py install 3.13"
    Wait-ForExit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "Створюю віртуальне середовище..."
    & $pyExe @pyPreArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ПОМИЛКА] Не вдалося створити віртуальне середовище." -ForegroundColor Red
        Wait-ForExit 1
    }
}

Write-Host "Встановлюю InkForge та залежності launcher-а..."
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\pip.exe" install -e ".[launcher]"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ПОМИЛКА] Встановлення не вдалося -- див. повідомлення вище." -ForegroundColor Red
    Wait-ForExit 1
}

Write-Host ""
Write-Host "Готово! Тепер запускай InkForge подвійним кліком на start_launcher.bat" -ForegroundColor Green
Wait-ForExit 0
