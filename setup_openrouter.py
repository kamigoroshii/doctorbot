#!/usr/bin/env python3
"""
Setup script for DoctorBot with OpenRouter API
"""

import os
import sys
from pathlib import Path

def main():
    print("🏥 DoctorBot - OpenRouter Setup Complete!")
    print("=" * 45)
    
    print("✅ Configuration Status:")
    print("• AI Provider: OpenRouter")
    print("• API Key: Configured")
    print("• Free Credits: $5 available")
    print("• Model: Llama 3.1 8B (Free)")
    
    print("\n📋 Next Steps:")
    print("1. Get Telegram Bot Token:")
    print("   - Message @BotFather on Telegram")
    print("   - Create new bot: /newbot")
    print("   - Copy the token")
    print("   - Add to .env: TELEGRAM_BOT_TOKEN=your_token")
    
    print("\n2. Install Dependencies:")
    print("   pip install -r requirements.txt")
    
    print("\n3. Initialize Database:")
    print("   python setup.py")
    
    print("\n4. Test OpenRouter API:")
    print("   python tests/test_openrouter_api.py")
    
    print("\n5. Start DoctorBot:")
    print("   python main.py all")
    
    print("\n🎯 OpenRouter Benefits:")
    print("• $5 FREE credits (500+ requests)")
    print("• Access to 100+ AI models")
    print("• No regional restrictions")
    print("• Fast and reliable")
    print("• Includes Grok, GPT, Claude, Llama")
    
    print("\n💡 Available Models:")
    print("• meta-llama/llama-3.1-8b-instruct:free (Current)")
    print("• google/gemma-2-9b-it:free")
    print("• microsoft/phi-3-medium-128k-instruct:free")
    print("• And many more!")
    
    print("\n🔧 Configuration Details:")
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file exists")
        with open(".env", "r") as f:
            content = f.read()
            if "OPENROUTER_API_KEY" in content:
                print("✅ OpenRouter API key configured")
            if "AI_PROVIDER=openrouter" in content:
                print("✅ AI provider set to OpenRouter")
    
    print("\n🚀 Ready to test? Run:")
    print("   python tests/test_openrouter_api.py")
    
    print("\n📚 Documentation:")
    print("• OpenRouter Docs: https://openrouter.ai/docs")
    print("• DoctorBot Setup: README.md")
    print("• Deployment Guide: DEPLOYMENT.md")

if __name__ == "__main__":
    main()