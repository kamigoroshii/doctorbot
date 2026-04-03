#!/usr/bin/env python3
"""
Simple startup script for DoctorBot
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def _provider_requirements_ok() -> bool:
    """Validate required API keys based on selected AI provider."""
    provider = os.getenv("AI_PROVIDER", "demo").lower()

    if provider == "demo":
        print("✅ Demo mode: no external AI key required")
        return True

    if provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY")
        if key:
            print("✅ OpenRouter API Key: Configured")
            print("🎯 Free Credits: $5 available")
            return True
        print("❌ OpenRouter API Key: Missing")
        return False

    if provider == "grok":
        key = os.getenv("GROK_API_KEY")
        if key:
            print("✅ Grok API Key: Configured")
            return True
        print("❌ Grok API Key: Missing")
        return False

    if provider == "gemini":
        key = os.getenv("GOOGLE_API_KEY")
        if key:
            print("✅ Google Gemini API Key: Configured")
            return True
        print("❌ Google Gemini API Key: Missing")
        return False

    print(f"❌ Unsupported AI provider: {provider}")
    return False

def main():
    print("🏥 Starting DoctorBot...")
    print("=" * 30)
    
    # Load environment
    load_dotenv()
    
    # Check configuration
    print("🔧 Configuration Check:")
    
    # Check Telegram token
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if telegram_token and telegram_token != "your_telegram_bot_token_here":
        print("✅ Telegram Bot Token: Configured")
    else:
        print("❌ Telegram Bot Token: Missing")
        print("💡 Get token from @BotFather on Telegram")
        print("💡 Add to .env: TELEGRAM_BOT_TOKEN=your_token")
        return
    
    # Check AI provider
    ai_provider = os.getenv("AI_PROVIDER", "demo")
    print(f"✅ AI Provider: {ai_provider}")

    if not _provider_requirements_ok():
        return
    
    print("\n🚀 Starting DoctorBot components...")
    
    try:
        # Import and start the main application
        from main import main as start_main
        
        print("✅ All systems ready!")
        print("📱 Send prescription photos to your Telegram bot")
        print("🔄 Press Ctrl+C to stop")
        
        # start_main is a synchronous function that orchestrates backend/bot startup.
        start_main()
        
    except KeyboardInterrupt:
        print("\n👋 DoctorBot stopped gracefully")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Run: pip install -r requirements.txt")
    except Exception as e:
        print(f"❌ Error starting DoctorBot: {e}")

if __name__ == "__main__":
    main()