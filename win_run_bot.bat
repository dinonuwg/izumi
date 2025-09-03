@echo off
echo Starting Izumi Bot...
echo.
python3.12 bot.py
if errorlevel 1 (
    echo.
    echo Trying with alternative Python command...
    python bot.py
)
if errorlevel 1 (
    echo.
    echo Python not found in PATH. Please install Python or add it to PATH.
)
pause
