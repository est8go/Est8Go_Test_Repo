#!/usr/bin/env bash
# EST8GO RENDER BUILD SCRIPT
# Installs FFmpeg and Python dependencies

set -o errexit  # Exit on error

echo "🚀 EST8GO BUILD STARTING..."

# Install FFmpeg
echo "📦 Installing FFmpeg..."
apt-get update -y
apt-get install -y ffmpeg

# Verify FFmpeg
echo "✅ FFmpeg version:"
ffmpeg -version | head -1

# Install Python dependencies
echo "📦 Installing Python packages..."
pip install -r requirements.txt

echo "🎉 BUILD COMPLETE"