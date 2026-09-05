@echo off
setlocal
cd /d "%~dp0"

.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\python.exe -m PyInstaller --onefile --name setup --console setup_launcher.py

copy /Y dist\setup.exe setup.exe >nul
echo.
echo Created setup.exe in the project folder.
pause