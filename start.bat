@echo off
cd /d "%~dp0"
where py >nul 2>&1 && (set "PY=py -3.12") || (set "PY=python")
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Could not create a Python 3.12 virtual environment.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install -U pip
python -m pip install paddlepaddle-gpu==3.3.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu129/
if errorlevel 1 python -m pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install -r requirements.txt
set "PYTHONPATH=%CD%"
python -m blacklist_detect
if errorlevel 1 pause
