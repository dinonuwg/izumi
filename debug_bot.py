#!/usr/bin/env python3
"""
Debug script for Izumi Discord Bot
Run this to diagnose common issues
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} is too old (need 3.8+)")
        return False

def check_environment_file():
    """Check if .env file exists and has required variables"""
    print("\n📄 Checking .env file...")
    
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        return False
    
    print("✅ .env file exists")
    
    # Check for required variables
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ['DISCORD_TOKEN', 'GEMINI_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value == 'your_token_here':
            missing_vars.append(var)
        else:
            print(f"✅ {var} is set")
    
    if missing_vars:
        print(f"❌ Missing or invalid environment variables: {', '.join(missing_vars)}")
        return False
    
    return True

def check_data_directory():
    """Check if data directory and files exist"""
    print("\n📁 Checking data directory...")
    
    if not os.path.exists('data'):
        print("❌ data directory not found!")
        return False
    
    print("✅ data directory exists")
    
    # Check for important data files
    important_files = [
        'allowed_channels.json',
        'xp_data.json',
        'osu_gacha.json'
    ]
    
    for file in important_files:
        path = f"data/{file}"
        if os.path.exists(path):
            print(f"✅ {file} exists")
            # Check if it's valid JSON
            try:
                with open(path, 'r') as f:
                    json.load(f)
                print(f"✅ {file} is valid JSON")
            except json.JSONDecodeError:
                print(f"❌ {file} has invalid JSON!")
        else:
            print(f"⚠️ {file} not found (will be created)")
    
    return True

def check_cogs():
    """Check if all cog files exist"""
    print("\n🧩 Checking cog files...")
    
    cog_modules = [
        'cogs/ai/izumi_ai.py',
        'cogs/ai/memory.py',
        'cogs/moderation/leveling.py',
        'cogs/osugacha/osugacha_commands.py',
        'cogs/osugacha/osugacha_store.py'
    ]
    
    missing_cogs = []
    for cog in cog_modules:
        if os.path.exists(cog):
            print(f"✅ {cog} exists")
        else:
            print(f"❌ {cog} missing!")
            missing_cogs.append(cog)
    
    if missing_cogs:
        print(f"❌ Missing cog files: {', '.join(missing_cogs)}")
        return False
    
    return True

def check_dependencies():
    """Check if required packages are installed"""
    print("\n📦 Checking dependencies...")
    
    required_packages = [
        'discord.py',
        'python-dotenv',
        'aiohttp',
        'google-generativeai'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            if package == 'discord.py':
                import discord
                print(f"✅ discord.py {discord.__version__} installed")
            elif package == 'python-dotenv':
                import dotenv
                print(f"✅ python-dotenv installed")
            elif package == 'aiohttp':
                import aiohttp
                print(f"✅ aiohttp {aiohttp.__version__} installed")
            elif package == 'google-generativeai':
                import google.generativeai
                print(f"✅ google-generativeai installed")
        except ImportError:
            print(f"❌ {package} not installed!")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📝 Install missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_permissions():
    """Check file permissions"""
    print("\n🔐 Checking file permissions...")
    
    # Check if bot.py is readable
    if os.access('bot.py', os.R_OK):
        print("✅ bot.py is readable")
    else:
        print("❌ bot.py is not readable!")
        return False
    
    # Check if data directory is writable
    if os.access('data', os.W_OK):
        print("✅ data directory is writable")
    else:
        print("❌ data directory is not writable!")
        return False
    
    return True

def run_syntax_check():
    """Check if bot.py has syntax errors"""
    print("\n🔍 Checking Python syntax...")
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'py_compile', 'bot.py'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ bot.py syntax is valid")
            return True
        else:
            print(f"❌ Syntax error in bot.py: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Could not check syntax: {e}")
        return False

def main():
    print("🤖 Izumi Bot Diagnostic Tool")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Environment File", check_environment_file),
        ("Data Directory", check_data_directory),
        ("Cog Files", check_cogs),
        ("Dependencies", check_dependencies),
        ("File Permissions", check_permissions),
        ("Python Syntax", run_syntax_check)
    ]
    
    passed = 0
    total = len(checks)
    
    for name, check_func in checks:
        if check_func():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Diagnostic Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 All checks passed! Your bot should work correctly.")
    else:
        print("⚠️ Some issues found. Please fix them before running the bot.")
        print("\n💡 Tips:")
        print("- Make sure your .env file has valid tokens")
        print("- Run 'pip install -r requirements.txt' to install dependencies")
        print("- Check file permissions if running on Linux")

if __name__ == "__main__":
    main()
