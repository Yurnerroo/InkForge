@echo off
rem InkForge one-click launcher (Windows).
rem This file only forwards to scripts\start_launcher.ps1, which contains
rem the real logic and all user-facing messages. Keeping this .bat file
rem plain ASCII avoids a known cmd.exe bug where batch files with non-ASCII
rem (Cyrillic) text in comments/echo can get corrupted while parsing.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_launcher.ps1"
