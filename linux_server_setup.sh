#!/bin/bash

# Izumi Discord Bot - First Time Linux Server Setup Script
# This script sets up everything needed to run the bot on Ubuntu Linux

set -e  # Exit on any error

echo "🤖 Izumi Bot - Linux Server Setup"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
BOT_NAME="izumi-bot"
BOT_DIR="/opt/$BOT_NAME"
BOT_USER="izumi"
REPO_URL="https://github.com/dinonuwg/izumi.git"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Update system packages
update_system() {
    print_status "Updating system packages..."
    apt update && apt upgrade -y
    print_success "System updated successfully"
}

# Install required packages
install_packages() {
    print_status "Installing required packages..."
    
    # Essential packages
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        git \
        curl \
        wget \
        unzip \
        build-essential \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release \
        htop \
        nano \
        vim \
        screen \
        tmux \
        ufw \
        fail2ban
    
    print_success "Required packages installed"
}

# Create bot user
create_bot_user() {
    print_status "Creating bot user '$BOT_USER'..."
    
    if id "$BOT_USER" &>/dev/null; then
        print_warning "User '$BOT_USER' already exists"
    else
        # Create system user with home directory
        useradd -r -s /bin/bash -d "$BOT_DIR" "$BOT_USER"
        print_success "User '$BOT_USER' created"
    fi
    
    # Ensure the user can access /opt directory
    # Add user to appropriate groups if needed
    if ! groups "$BOT_USER" | grep -q "$BOT_USER"; then
        print_status "Setting up user groups for '$BOT_USER'..."
    fi
}

# Clone repository
clone_repository() {
    print_status "Cloning repository to $BOT_DIR..."
    
    # Check if parent directory exists, create if not
    if [ ! -d "/opt" ]; then
        mkdir -p "/opt"
    fi
    
    if [ -d "$BOT_DIR" ]; then
        print_warning "Directory $BOT_DIR already exists"
        read -p "Do you want to remove it and re-clone? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Removing existing directory..."
            rm -rf "$BOT_DIR"
        else
            print_status "Updating existing repository..."
            cd "$BOT_DIR"
            # Check if it's actually a git repo
            if [ -d ".git" ]; then
                sudo -u "$BOT_USER" git pull
            else
                print_error "Directory exists but is not a git repository"
                return 1
            fi
            return
        fi
    fi
    
    # Create the bot directory first with proper ownership
    mkdir -p "$BOT_DIR"
    chown "$BOT_USER:$BOT_USER" "$BOT_DIR"
    
    # Clone into the directory as the bot user
    cd "$BOT_DIR"
    sudo -u "$BOT_USER" git clone "$REPO_URL" .
    
    # Ensure all files are owned by bot user
    chown -R "$BOT_USER:$BOT_USER" "$BOT_DIR"
    print_success "Repository cloned successfully"
}

# Setup Python environment
setup_python_env() {
    print_status "Setting up Python virtual environment..."
    
    cd "$BOT_DIR"
    
    # Create virtual environment
    sudo -u "$BOT_USER" python3 -m venv venv
    
    # Activate and install packages
    sudo -u "$BOT_USER" bash -c "
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    "
    
    print_success "Python environment setup complete"
}

# Create data directory and set permissions
setup_data_directory() {
    print_status "Setting up data directory..."
    
    cd "$BOT_DIR"
    
    if [ ! -d "data" ]; then
        sudo -u "$BOT_USER" mkdir -p data
    fi
    
    # Create empty data files if they don't exist
    data_files=(
        "allowed_channels.json"
        "auto_roles.json"
        "birthday_notifications.json"
        "birthdays.json"
        "event_config.json"
        "izumi_memories.json"
        "izumi_self.json"
        "learning_data.json"
        "level_roles.json"
        "osu_events.json"
        "osu_gacha.json"
        "osu_leaderboard_cache.json"
        "party_beatmaps_cache.json"
        "party_recent_maps.json"
        "reaction_roles.json"
        "reminders.json"
        "store_config.json"
        "unified_memory.json"
        "warnings.json"
        "xp_data.json"
    )
    
    for file in "${data_files[@]}"; do
        if [ ! -f "data/$file" ]; then
            sudo -u "$BOT_USER" bash -c "echo '{}' > data/$file"
        fi
    done
    
    # Ensure proper ownership and permissions
    chown -R "$BOT_USER:$BOT_USER" data/
    chmod -R 644 data/*
    chmod 755 data/
    
    print_success "Data directory setup complete"
}

# Make scripts executable
setup_permissions() {
    print_status "Setting up file permissions..."
    
    cd "$BOT_DIR"
    
    # Make shell scripts executable
    chmod +x *.sh
    
    # Set proper ownership
    chown -R "$BOT_USER:$BOT_USER" .
    
    print_success "Permissions configured"
}

# Setup environment file
setup_env_file() {
    print_status "Setting up environment file..."
    
    cd "$BOT_DIR"
    
    if [ ! -f ".env" ]; then
        sudo -u "$BOT_USER" cat > .env << EOF
# Discord Bot Token - GET THIS FROM DISCORD DEVELOPER PORTAL
DISCORD_TOKEN=your_discord_token_here

# Google AI Token (for AI features) - GET THIS FROM GOOGLE AI STUDIO
GOOGLE_AI_TOKEN=your_google_ai_token_here

# Optional: Database URL (if using external database)
# DATABASE_URL=your_database_url_here

# Optional: Debug mode not implemented yet
# DEBUG=false
EOF
        print_warning "Created .env file - YOU MUST EDIT IT WITH YOUR TOKENS!"
        print_warning "Edit $BOT_DIR/.env and add your Discord bot token"
    else
        print_warning ".env file already exists"
    fi
}

# Create systemd service
create_systemd_service() {
    print_status "Creating systemd service..."
    
    cat > "/etc/systemd/system/$BOT_NAME.service" << EOF
[Unit]
Description=Izumi Discord Bot
After=network.target

[Service]
Type=simple
User=$BOT_USER
WorkingDirectory=$BOT_DIR
Environment=PATH=$BOT_DIR/venv/bin
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=$BOT_DIR
ExecStart=$BOT_DIR/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=izumi-bot

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable "$BOT_NAME"
    
    print_success "Systemd service created and enabled"
}

# Setup firewall (basic)
setup_firewall() {
    print_status "Configuring basic firewall..."
    
    # Enable UFW if not already enabled
    if ! ufw status | grep -q "Status: active"; then
        ufw --force enable
    fi
    
    # Allow SSH (be careful!)
    ufw allow ssh
    
    print_success "Basic firewall configured"
}

# Setup log rotation
setup_log_rotation() {
    print_status "Setting up log rotation..."
    
    cat > "/etc/logrotate.d/$BOT_NAME" << EOF
/var/log/izumi/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 $BOT_USER $BOT_USER
}
EOF
    
    # Create log directory
    mkdir -p "/var/log/izumi"
    chown "$BOT_USER:$BOT_USER" "/var/log/izumi"
    
    print_success "Log rotation configured"
}

# Main installation function
main() {
    echo "Starting Izumi bot installation..."
    echo ""
    
    check_root
    update_system
    install_packages
    create_bot_user
    clone_repository
    setup_python_env
    setup_data_directory
    setup_permissions
    setup_env_file
    create_systemd_service
    setup_firewall
    setup_log_rotation
    
    echo ""
    echo "🎉 Installation completed successfully!"
    echo ""
    echo "⚠️  IMPORTANT: Before starting the bot:"
    echo "   1. Edit $BOT_DIR/.env and add your Discord bot token"
    echo "   2. Edit $BOT_DIR/.env and add your Google AI token (if using AI features)"
    echo ""
    echo "📋 Useful commands:"
    echo "   Start bot:    sudo systemctl start $BOT_NAME"
    echo "   Stop bot:     sudo systemctl stop $BOT_NAME"
    echo "   Restart bot:  sudo systemctl restart $BOT_NAME"
    echo "   Check status: sudo systemctl status $BOT_NAME"
    echo "   View logs:    sudo journalctl -u $BOT_NAME -f"
    echo ""
    echo "   Or use the management script:"
    echo "   cd $BOT_DIR && ./linux_manage_bot.sh start"
    echo ""
    echo "🔧 Configuration files:"
    echo "   Bot config:   $BOT_DIR/.env"
    echo "   Service file: /etc/systemd/system/$BOT_NAME.service"
    echo "   Data folder:  $BOT_DIR/data/"
    echo ""
    echo "✅ Your bot is ready to start once you configure the tokens!"
}

# Run main function
main "$@"
