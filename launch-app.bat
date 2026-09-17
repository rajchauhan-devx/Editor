@echo off
title AI Gaming Editor
if exist "%~dp0dist-electron\win-unpacked\AI Gaming Editor.exe" (
    start "" "%~dp0dist-electron\win-unpacked\AI Gaming Editor.exe"
) else (
    cd /d "%~dp0"
    call npm run electron:dev
)
