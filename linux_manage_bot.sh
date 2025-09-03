#!/bin/bash

# Discord Bot Management Script
# Usage: ./linux_manage_bot.sh {command} [bot-name]

# Default bot name (change this to match your bot)
DEFAULT_BOT_NAME="izumi-bot"
BOT_NAME=${2:-$DEFAULT_BOT_NAME}

case "$1" in
    start)
        echo "🚀 Starting $BOT_NAME..."
        sudo systemctl start $BOT_NAME
        sudo systemctl status $BOT_NAME --no-pager -l
        ;;
    stop)
        echo "🛑 Stopping $BOT_NAME..."
        sudo systemctl stop $BOT_NAME
        ;;
    restart)
        echo "🔄 Restarting $BOT_NAME..."
        sudo systemctl restart $BOT_NAME
        sudo systemctl status $BOT_NAME --no-pager -l
        ;;
    status)
        echo "📊 $BOT_NAME Status:"
        sudo systemctl status $BOT_NAME --no-pager -l
        ;;
    logs)
        echo "📋 Recent logs:"
        sudo journalctl -u $BOT_NAME --no-pager -l -n 50
        ;;
    follow)
        echo "👀 Following logs (Ctrl+C to exit):"
        sudo journalctl -u $BOT_NAME -f
        ;;
    update)
        echo "📦 Updating $BOT_NAME..."
        sudo systemctl stop $BOT_NAME
        cd /opt/$BOT_NAME
        git pull
        source venv/bin/activate
        echo "🔄 Installing/updating Python dependencies..."
        pip install -r requirements.txt --upgrade --quiet
        sudo systemctl restart $BOT_NAME
        sudo systemctl status $BOT_NAME --no-pager -l
        ;;
    backup)
        echo "💾 Creating backup..."
        timestamp=$(date +%Y%m%d_%H%M%S)
        tar -czf "/tmp/$BOT_NAME-backup-$timestamp.tar.gz" -C /opt/$BOT_NAME data/ .env
        echo "✅ Backup created: /tmp/$BOT_NAME-backup-$timestamp.tar.gz"
        ;;
    *)
        echo "🤖 Discord Bot Management Script"
        echo "Usage: $0 {start|stop|restart|status|logs|follow|update|backup} [bot-name]"
        echo ""
        echo "Commands:"
        echo "  start   - Start the bot service"
        echo "  stop    - Stop the bot service"
        echo "  restart - Restart the bot service"
        echo "  status  - Show current status"
        echo "  logs    - Show recent logs"
        echo "  follow  - Follow logs in real-time"
        echo "  update  - Pull updates and restart"
        echo "  backup  - Create backup of data and config"
        echo ""
        echo "Bot name: $BOT_NAME (default: $DEFAULT_BOT_NAME)"
        echo "To use different bot: $0 command bot-name"
        ;;
esac
