#!/bin/bash

# Discord Bot Transfer Script  
# Run this on your local machine (using Git Bash, WSL, or Linux/Mac terminal)

# Configuration - Update these values
SERVER_IP="server-ip"          # Replace with your server IP
SERVER_USER="user"         # Replace with your server username  
BOT_NAME="izumi-bot"              # Replace with your bot directory name

echo "📦 Preparing Discord bot for transfer to Ubuntu server..."

# Create transfer directory
mkdir -p transfer_package

# Copy essential bot files
echo "📋 Copying bot files..."
cp bot.py transfer_package/ 2>/dev/null || echo "⚠️ bot.py not found"
cp requirements.txt transfer_package/ 2>/dev/null || echo "⚠️ requirements.txt not found"
cp -r cogs transfer_package/ 2>/dev/null || echo "⚠️ cogs directory not found"
cp -r utils transfer_package/ 2>/dev/null || echo "⚠️ utils directory not found"
cp -r data transfer_package/ 2>/dev/null || echo "📝 No data directory found (will be created on first run)"
cp .env transfer_package/ 2>/dev/null || echo "⚠️ .env file not found - you'll need to create it on the server"
cp .env.template transfer_package/ 2>/dev/null || echo "📝 No .env.template found"

# Copy documentation and other files
cp *.md transfer_package/ 2>/dev/null || echo "📝 No markdown files found"
cp *.bat transfer_package/ 2>/dev/null || echo "📝 No batch files found"

# Create a compressed archive
echo "🗜️ Creating compressed archive..."
tar -czf ${BOT_NAME}-transfer.tar.gz transfer_package/

echo "✅ Transfer package created: ${BOT_NAME}-transfer.tar.gz"
echo ""
echo "🚀 Transfer commands to run:"
echo "1. Upload to server:"
echo "   scp ${BOT_NAME}-transfer.tar.gz $SERVER_USER@$SERVER_IP:~/"
echo ""
echo "2. On server, extract files:"
echo "   ssh $SERVER_USER@$SERVER_IP"
echo "   tar -xzf ${BOT_NAME}-transfer.tar.gz"
echo "   sudo cp -r transfer_package/* /opt/$BOT_NAME/"
echo "   sudo chown -R $USER:$USER /opt/$BOT_NAME"
echo "   rm -rf transfer_package ${BOT_NAME}-transfer.tar.gz"
echo ""
echo "3. Set up environment:"
echo "   cd /opt/$BOT_NAME"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo ""
echo "4. Configure .env file with your API tokens"
echo "5. Test run: python bot.py"
echo "6. Enable service: sudo systemctl enable $BOT_NAME && sudo systemctl start $BOT_NAME"
echo "7. Use /opt/$BOT_NAME/linux_manage_bot.sh to control the bot"

# Clean up
rm -rf transfer_package

echo ""
echo "📝 Note: Make sure to run the linux_server_setup.sh script on your server first!"
echo "   Usage: ./linux_server_setup.sh $BOT_NAME"
