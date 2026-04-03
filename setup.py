#!/usr/bin/env python3
"""
Setup script for DoctorBot
"""

import os
import sys
from pathlib import Path

def create_env_file():
    """Create .env file from template if it doesn't exist"""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        print("📝 Creating .env file from template...")
        env_file.write_text(env_example.read_text())
        print("✅ .env file created. Please update it with your API keys.")
        return True
    return False

def check_requirements():
    """Check if all requirements are installed"""
    try:
        import fastapi
        import telegram
        import cv2
        import pytesseract
        print("✅ All required packages are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing package: {e.name}")
        print("Run: pip install -r requirements.txt")
        return False

def setup_database():
    """Initialize database"""
    try:
        from backend.database import init_db
        import asyncio
        
        print("🗄️ Initializing database...")
        asyncio.run(init_db())
        print("✅ Database initialized")
        return True
    except Exception as e:
        print(f"❌ Database setup failed: {str(e)}")
        return False

def main():
    """Main setup function"""
    print("🏥 DoctorBot Setup")
    print("=" * 30)
    
    # Create .env file
    env_created = create_env_file()
    
    # Check requirements
    if not check_requirements():
        print("\n❌ Setup incomplete. Please install requirements first.")
        return
    
    # Setup database
    if not setup_database():
        print("\n❌ Database setup failed.")
        return
    
    print("\n✅ Setup completed successfully!")
    
    if env_created:
        print("\n📋 Next steps:")
        print("1. Edit .env file with your API keys:")
        print("   - TELEGRAM_BOT_TOKEN (get from @BotFather)")
        print("   - GROK_API_KEY (get from X.AI Console - FREE $25/month)")
        print("   - Set AI_PROVIDER=grok")
        print("2. Run: python main.py")
    else:
        print("\n🚀 Ready to run: python main.py")

if __name__ == "__main__":
    main()