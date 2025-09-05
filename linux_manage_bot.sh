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
        
        # Create backup directory if it doesn't exist
        backup_dir="/opt/$BOT_NAME/backups"
        mkdir -p "$backup_dir"
        
        timestamp=$(date +%Y%m%d_%H%M%S)
        backup_file="$backup_dir/$BOT_NAME-backup-$timestamp.tar.gz"
        
        # Create backup archive
        tar -czf "$backup_file" -C /opt/$BOT_NAME data/ .env
        
        echo "✅ Backup created: $backup_file"
        
        # Show backup info
        backup_size=$(du -h "$backup_file" | cut -f1)
        echo "📊 Backup size: $backup_size"
        
        # Optional: Clean up old backups (keep last 50)
        backup_count=$(ls -1 "$backup_dir"/*.tar.gz 2>/dev/null | wc -l)
        if [ "$backup_count" -gt 50 ]; then
            echo "🧹 Cleaning up old backups (keeping 50 most recent)..."
            ls -t "$backup_dir"/*.tar.gz | tail -n +51 | xargs rm -f
        fi
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
