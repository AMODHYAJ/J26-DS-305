@echo off
setlocal
cd /d "%~dp0\..\.."
set "C2_TLA_DIR=components\C2_TLA_true_load_analysis"
set "C2_TLA_PY=.venv\Scripts\python.exe"
if not exist "%C2_TLA_PY%" set "C2_TLA_PY=C2_TLA_tools\C2_TLA_python\python.exe"
if not exist "%C2_TLA_PY%" (
  echo Python environment missing. Run C2_TLA_setup.cmd first.
  exit /b 1
)
set "PYTHONPATH=%CD%\%C2_TLA_DIR%;%CD%"
set "PYTHONUTF8=1"
if /i "%~1"=="ui" (
  if not exist "%C2_TLA_DIR%\C2_TLA_web\C2_TLA_index.html" (
    "%C2_TLA_PY%" "%C2_TLA_DIR%\C2_TLA_build_ui.py"
    if errorlevel 1 exit /b 1
  )
  if not defined C2_TLA_UI_PORT set "C2_TLA_UI_PORT=8502"
  goto serveui
)
if /i "%~1"=="build-ui" (
  "%C2_TLA_PY%" "%C2_TLA_DIR%\C2_TLA_build_ui.py"
  exit /b
)
if /i "%~1"=="api" (
  "%C2_TLA_PY%" -m uvicorn C2_TLA_api:app --app-dir "%C2_TLA_DIR%" --host 127.0.0.1 --port 8002
  exit /b
)
if /i "%~1"=="test" (
  "%C2_TLA_PY%" -m pytest -c "%C2_TLA_DIR%\C2_TLA_pytest.ini" "%C2_TLA_DIR%\C2_TLA_tests"
  exit /b
)
"%C2_TLA_PY%" "%C2_TLA_DIR%\C2_TLA_pipeline.py" %*
exit /b
:serveui
"%C2_TLA_PY%" -m uvicorn C2_TLA_api:app --app-dir "%C2_TLA_DIR%" --host 127.0.0.1 --port "%C2_TLA_UI_PORT%"
