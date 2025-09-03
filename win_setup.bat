@echo off
title Izumi Bot Setup
echo ==========================================
echo          IZUMI BOT SETUP SCRIPT
echo ==========================================
echo.

echo Installing Python dependencies...
python3.12 -m pip install --upgrade pip
python3.12 -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo Trying with alternative Python command...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
)

echo.
echo ==========================================
echo Setup complete! You can now run the bot.
echo ==========================================
echo.
echo To start the bot, run: python bot.py
echo Or use the run_bot.bat file
echo.
pause
