#!/usr/bin/env python3
"""
Debug the bot image processing issue
"""

import asyncio
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

async def test_image_upload():
    """Test uploading an image to the backend API"""
    print("🧪 Testing Image Upload to Backend...")
    
    # Create a simple test image (1x1 pixel PNG)
    test_image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": ("test.png", test_image_data, "image/png")}
            
            print("📤 Sending test image to backend...")
            response = await client.post(
                "http://localhost:8000/process-prescription",
                files=files
            )
            
            print(f"📡 Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Backend processed image successfully!")
                print(f"📋 Result: {result}")
            else:
                print(f"❌ Backend error: {response.text}")
                
    except Exception as e:
        print(f"❌ Error testing image upload: {str(e)}")

async def test_bot_api_call():
    """Test the exact same API call the bot makes"""
    print("\n🤖 Testing Bot-style API Call...")
    
    # Simulate what the bot does
    photo_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    
    try:
        api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": ("prescription.jpg", photo_data, "image/jpeg")}
            response = await client.post(
                f"{api_base_url}/process-prescription",
                files=files
            )
            
            print(f"📡 Bot-style response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Bot-style API call successful!")
                print(f"📋 Success: {result.get('success', False)}")
            else:
                print(f"❌ Bot-style API call failed: {response.text}")
                
    except Exception as e:
        print(f"❌ Error in bot-style API call: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_image_upload())
    asyncio.run(test_bot_api_call())