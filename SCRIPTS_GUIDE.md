# 🚀 Script Reference Guide

This bot includes setup and deployment scripts for both Windows and Linux environments.

## 📁 Windows Scripts (.bat files)

### `win_setup.bat`
- **Purpose**: Quick setup for Windows development
- **Usage**: Double-click or run `win_setup.bat` 
- **What it does**: Installs Python dependencies, creates virtual environment

### `win_run_bot.bat` 
- **Purpose**: Run the bot on Windows
- **Usage**: Double-click or run `win_run_bot.bat`
- **What it does**: Activates virtual environment and starts the bot

### `win_transfer_helper.bat`
- **Purpose**: Helper for transferring files to Linux server
- **Usage**: Run in Windows Command Prompt
- **What it does**: Prepares files and provides transfer instructions

## 🐧 Linux Scripts (.sh files)

### `linux_server_setup.sh`
- **Purpose**: Complete Ubuntu server setup with systemd service
- **Usage**: `./linux_server_setup.sh [bot-name]`
- **What it does**: 
  - Updates system packages
  - Installs Python, Node.js, and dependencies  
  - Creates bot directory in `/opt/[bot-name]/`
  - Creates systemd service for auto-startup
  - Sets up management scripts

### `linux_manage_bot.sh`
- **Purpose**: Manage the bot service on Linux
- **Usage**: `/opt/[bot-name]/linux_manage_bot.sh {start|stop|restart|status|logs|follow|update|backup} [bot-name]`
- **Commands**:
  - `start` - Start the bot service
  - `stop` - Stop the bot service  
  - `restart` - Restart the bot service
  - `status` - Show current status
  - `logs` - Show recent logs
  - `follow` - Follow logs in real-time
  - `update` - Pull updates and restart
  - `backup` - Create backup of data and config

### `win_to_linux_transfer.sh`
- **Purpose**: Transfer bot files from Windows/Mac to Linux server
- **Usage**: `./win_to_linux_transfer.sh` (edit config variables first)
- **What it does**:
  - Packages bot files into compressed archive
  - Provides step-by-step transfer instructions
  - Includes scp commands for uploading to server
  - Transfers files to `/opt/[bot-name]/`

## 🔧 Quick Start

### For Windows Development:
1. Run `win_setup.bat`
2. Copy `.env.template` to `.env` and fill in your API keys
3. Run `win_run_bot.bat`

### For Linux Server Deployment:
1. Run `./linux_server_setup.sh` on your server
2. Use `./win_to_linux_transfer.sh` to transfer files from local machine
3. Follow the transfer instructions to complete setup
4. Use `/opt/[bot-name]/linux_manage_bot.sh start` to start the bot

## 💡 Tips

- All scripts are designed to be general purpose but default to sensible values
- You can specify custom bot names: `./linux_server_setup.sh my-bot-name`
- The Linux management script defaults to "izumi-bot" but can manage other bots too
- Make sure to edit the server IP and username in transfer scripts before using

---

*These scripts make deployment and management much easier! 🎉*
