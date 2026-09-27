@echo off
rem InkForge first-run setup (Windows).
rem This file only forwards to scripts\setup.ps1, which contains the real
rem logic and all user-facing messages. Keeping this .bat file plain ASCII
rem avoids a known cmd.exe bug where batch files with non-ASCII (Cyrillic)
rem text in comments/echo can get corrupted while parsing (commands get
rem cut off mid-word, e.g. "setlocal" becomes "etlocal").
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
