@echo off
REM PowerTrader AI+ Launcher Script
REM This ensures the virtual environment is used

echo Starting PowerTraderAI+...
echo Using virtual environment...

REM Change to the PowerTrader directory
cd /d "%~dp0"

REM The program folder is read-only at runtime: no bytecode cache is written
REM next to the modules, by the hub or the processes it starts (#148)
set PYTHONDONTWRITEBYTECODE=1

REM Activate virtual environment and run PowerTrader
.venv\Scripts\python.exe app\pt_hub.py

pause