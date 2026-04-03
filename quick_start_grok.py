#!/usr/bin/env python3
"""
Quick start script for DoctorBot with Grok API
"""

import os
import sys
from pathlib import Path

def main():
    print("🏥 DoctorBot - Grok API Quick Start")
    print("=" * 40)
    
    # Check if .env exists
    env_file = Path(".env")
    if not env_file.exists():
        print("📝 Creating .env file...")
        with open(".env", "w") as f:
            f.write("""# DoctorBot Configuration

# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# AI Provider (grok or gemini)
AI_PROVIDER=grok

# Grok API Key (get FREE $25/month from https://console.x.ai/)
GROK_API_KEY=xai-your-grok-api-key-here

# Optional: Gemini as fallback
GOOGLE_API_KEY=your_google_api_key_here

# Database
DATABASE_URL=sqlite:///./doctorbot.db

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# n8n Webhook
N8N_WEBHOOK_URL=http://localhost:5678/webhook/reminders
""")
        print("✅ .env file created!")
    else:
        print("✅ .env file already exists")
    
    print("\n🔧 Setup Steps:")
    print("1. Get Telegram Bot Token:")
    print("   - Message @BotFather on Telegram")
    print("   - Create new bot with /newbot")
    print("   - Copy the token")
    
    print("\n2. Get FREE Grok API Key:")
    print("   - Visit: https://console.x.ai/")
    print("   - Sign up with X (Twitter) account")
    print("   - Get $25 FREE credits monthly")
    print("   - Create API key")
    
    print("\n3. Edit .env file:")
    print("   - Replace 'your_telegram_bot_token_here' with your bot token")
    print("   - Replace 'xai-your-grok-api-key-here' with your Grok key")
    
    print("\n4. Install and run:")
    print("   pip install -r requirements.txt")
    print("   python setup.py")
    print("   python main.py all")
    
    print("\n5. Test your setup:")
    print("   python tests/test_grok_api.py")
    
    print("\n🎯 Alternative Free Options:")
    print("• Gemini API (Google) - Free tier available")
    print("• OpenRouter - $5 free credits")
    print("• Hugging Face - Completely free (local)")
    print("• Ollama - Free local models")
    
    print("\n📚 Documentation:")
    print("• Full setup: GROK_SETUP.md")
    print("• Deployment: DEPLOYMENT.md")
    print("• Main docs: README.md")
    
    print("\n🚀 Ready to start? Run:")
    print("   python main.py all")

if __name__ == "__main__":
    main()