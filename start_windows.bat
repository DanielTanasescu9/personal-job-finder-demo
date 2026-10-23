@echo off
setlocal
cd /d "%~dp0"
if not defined JOB_FINDER_PORT set JOB_FINDER_PORT=7860
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
echo Python 3 was not found. Install Python 3.11 or newer and try again.
pause
exit /b 1
:use_py
py -3 main.py
goto finished
:use_python
python main.py
:finished
echo Public demo stopped.
pause
endlocal
