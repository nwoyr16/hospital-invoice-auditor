@echo off
setlocal
cd /d "%~dp0"
python -m unittest -v test_engine
if errorlevel 1 exit /b 1
python run.py --evaluate-h1
if errorlevel 1 exit /b 1
python build_report.py
if errorlevel 1 exit /b 1
echo DONE: submission.csv and reports\report.pdf
