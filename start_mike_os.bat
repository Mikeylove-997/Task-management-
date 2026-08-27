@echo off
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 run.py
) else (
  python run.py
)

