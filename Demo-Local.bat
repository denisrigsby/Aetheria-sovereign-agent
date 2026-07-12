@echo off
setlocal
cd /d "%~dp0"
title Aetheria Public Demo (sanitized)
echo.
echo  Aetheria — sanitized public control-plane demo
echo  No private living / companion / G4 in this tree.
echo  Chat never parents the plant.
echo.
python -u scripts\demo_local_smoke.py
set EC=%ERRORLEVEL%
echo.
if "%EC%"=="0" (
  echo  DEMO PASS. See docs\PUBLIC_DEMO.md
) else (
  echo  DEMO FAIL exit %EC%
)
echo.
pause
exit /b %EC%
