@echo off
REM Izumi Bot Transfer Helper for Windows
REM This script helps prepare and transfer your bot to Ubuntu server

echo ========================================
echo    Izumi Bot Transfer Helper
echo ========================================
echo.

REM Check if required files exist
if not exist "bot.py" (
    echo ERROR: bot.py not found! Make sure you're in the correct directory.
    pause
    exit /b 1
)

if not exist "data" (
    echo ERROR: data folder not found! Your bot data is missing.
    pause
    exit /b 1
)

echo Creating transfer package...

REM Create transfer directory
if exist "transfer_package" rmdir /s /q "transfer_package"
mkdir transfer_package

REM Copy essential files
echo Copying bot files...
copy "bot.py" "transfer_package\"
copy "requirements.txt" "transfer_package\"
if exist ".env" copy ".env" "transfer_package\"
copy "*.md" "transfer_package\" 2>nul

REM Copy directories
echo Copying directories...
xcopy "cogs" "transfer_package\cogs\" /E /I /Y
xcopy "utils" "transfer_package\utils\" /E /I /Y
xcopy "data" "transfer_package\data\" /E /I /Y

REM Copy server setup scripts
copy "server_setup.sh" "transfer_package\"
copy "manage_bot.sh" "transfer_package\"
copy ".env.template" "transfer_package\"

echo.
echo ========================================
echo Transfer package created successfully!
echo ========================================
echo.
echo Next steps:
echo 1. Upload the 'transfer_package' folder to your Ubuntu server
echo 2. Run the server_setup.sh script on your Ubuntu server
echo 3. Copy the files from transfer_package to ~/izumi-bot/
echo 4. Set up your .env file with your bot tokens
echo 5. Install dependencies and start the bot
echo.
echo You can use WinSCP, FileZilla, or SCP to transfer files.
echo.

REM Show what's in the package
echo Contents of transfer_package:
dir /b "transfer_package"
echo.

echo Commands for Ubuntu server:
echo   chmod +x server_setup.sh manage_bot.sh
echo   ./server_setup.sh
echo   cp -r transfer_package/* ~/izumi-bot/
echo   cd ~/izumi-bot
echo   source venv/bin/activate
echo   pip install -r requirements.txt
echo   ./manage_bot.sh start
echo.

pause
