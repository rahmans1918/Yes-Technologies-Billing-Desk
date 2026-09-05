@echo off
setlocal
cd /d "%~dp0"

py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

if not exist instance mkdir instance

echo.
echo Yes Technologies billing app is ready.
echo Start it with: run.bat
pause
