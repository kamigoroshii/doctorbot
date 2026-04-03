#!/usr/bin/env python3
"""
DoctorBot - AI-Powered Prescription Management System
Main application entry point
"""

import asyncio
import os
import sys
import platform
import time
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

load_dotenv()

# Fix for Windows event loop policy
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

async def start_backend():
    """Start the FastAPI backend server"""
    import uvicorn
    from backend.main import app
    
    config = uvicorn.Config(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

def wait_for_backend(base_url: str, timeout_seconds: int = 15) -> bool:
    """Wait for the backend health endpoint to become reachable."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url.rstrip('/')}/health", timeout=2.0)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def start_telegram_bot():
    """Start the Telegram bot (synchronous)"""
    try:
        from bot.telegram_bot import DoctorBot
        
        bot = DoctorBot()
        print("✅ Telegram bot initialized successfully")
        print("🔄 Bot is running... Press Ctrl+C to stop")
        bot.run()
    except Exception as e:
        print(f"❌ Failed to start Telegram bot: {str(e)}")
        raise

def main():
    """Main application entry point"""
    print("🏥 Starting DoctorBot System...")
    
    # Check required environment variables
    ai_provider = os.getenv("AI_PROVIDER", "openrouter").lower()
    
    if ai_provider == "demo":
        required_vars = ["TELEGRAM_BOT_TOKEN"]
    elif ai_provider == "openrouter":
        required_vars = ["TELEGRAM_BOT_TOKEN", "OPENROUTER_API_KEY"]
    elif ai_provider == "grok":
        required_vars = ["TELEGRAM_BOT_TOKEN", "GROK_API_KEY"]
    else:
        required_vars = ["TELEGRAM_BOT_TOKEN", "GOOGLE_API_KEY"]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file and ensure all required variables are set.")
        return
    
    # Choose what to run based on command line arguments
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode == "backend":
            print("🚀 Starting Backend API Server...")
            asyncio.run(start_backend())
        elif mode == "bot":
            print("🤖 Starting Telegram Bot...")
            start_telegram_bot()
        elif mode == "all":
            print("🚀 Starting Full System (Backend + Bot)...")
            print("📡 Starting backend API server...")
            
            # Start backend in a separate process
            import subprocess
            
            # Start backend process
            backend_process = subprocess.Popen([
                sys.executable, "main.py", "backend"
            ], cwd=project_root)
            
            api_host = os.getenv("API_HOST", "127.0.0.1")
            if api_host == "0.0.0.0":
                api_host = "127.0.0.1"
            api_port = int(os.getenv("API_PORT", 8000))
            api_base_url = os.getenv("API_BASE_URL", f"http://{api_host}:{api_port}")

            if not wait_for_backend(api_base_url):
                backend_process.terminate()
                print("❌ Backend failed to start or is unreachable.")
                print(f"Check the backend logs and verify {api_base_url}/health is reachable.")
                return

            print(f"✅ Backend started at {api_base_url}")
            
            try:
                print("🤖 Starting Telegram bot...")
                start_telegram_bot()
            finally:
                # Clean up backend process
                backend_process.terminate()
                print("👋 Backend stopped")
        else:
            print("❌ Invalid mode. Use: python main.py [backend|bot|all]")
    else:
        print("🚀 No mode provided. Starting full system by default...")
        sys.argv = [sys.argv[0], "all"]
        main()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 DoctorBot shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error starting DoctorBot: {str(e)}")
        sys.exit(1)