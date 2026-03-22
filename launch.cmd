@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\pythonw.exe" start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launch.py" & exit /b 0
if exist "%~dp0.venv\Scripts\python.exe" start "" "%~dp0.venv\Scripts\python.exe" "%~dp0launch.py" & exit /b 0
start "" py -3 "%~dp0launch.py"
endlocal
