@echo off
cd /d "%~dp0"
echo Starting KRATOS Stock Intelligence...
where py >nul 2>nul
if %errorlevel%==0 (set "PYTHON=py -3") else (set "PYTHON=python")
if not exist .venv ( %PYTHON% -m venv .venv )
if errorlevel 1 (
 echo Could not create Python virtual environment. Install Python 3.11 or 3.12 from python.org.
 pause
 exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
 echo Package installation failed. Check internet connection.
 pause
 exit /b 1
)
echo Open http://127.0.0.1:7860 in your browser.
python app.py
pause
