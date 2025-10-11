#!/bin/bash

# Quick script to install FFmpeg on Ubuntu/Debian
# Run this on your server: sudo bash install_ffmpeg.sh

set -e

echo "🎬 Installing FFmpeg..."

# Update package list
apt update

# Install FFmpeg
apt install -y ffmpeg

# Verify installation
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg installed successfully!"
    ffmpeg -version | head -n 1
else
    echo "❌ FFmpeg installation failed"
    exit 1
fi
