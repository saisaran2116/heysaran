@echo off
cd /d "%~dp0"
if not exist ".hey-baby-venv\Scripts\python.exe" (
    echo Hey Baby is not installed. Run: py -3.12 setup.py
    exit /b 1
)
".hey-baby-venv\Scripts\python.exe" hey_saran.py %*
