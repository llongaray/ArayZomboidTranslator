@echo off
cd /d "%~dp0"
if exist .analyst-venv\Scripts\python.exe (
  .analyst-venv\Scripts\python.exe -m arayzt.cli dashboard
  exit /b
)
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  .venv\Scripts\python.exe -m pip install -e .
)
.venv\Scripts\python.exe -m arayzt.cli dashboard
pause
