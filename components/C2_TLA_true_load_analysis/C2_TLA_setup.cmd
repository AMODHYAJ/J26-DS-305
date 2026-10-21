@echo off
setlocal
cd /d "%~dp0\..\.."
if exist "C2_TLA_tools\C2_TLA_python\python.exe" (
  set "C2_TLA_PY=C2_TLA_tools\C2_TLA_python\python.exe"
  goto install
)
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.12 x64 from python.org with the Python launcher, then rerun setup.
  exit /b 1
)
if not exist .venv\Scripts\python.exe py -3.12 -m venv .venv
if errorlevel 1 exit /b 1
set "C2_TLA_PY=.venv\Scripts\python.exe"
:install
"%C2_TLA_PY%" -m pip install -r components\C2_TLA_true_load_analysis\C2_TLA_lock.txt
if errorlevel 1 exit /b 1
call components\C2_TLA_true_load_analysis\C2_TLA_launch.cmd prepare
