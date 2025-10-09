"""
Quick script to list all available Gemini models
"""
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure API
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print("❌ GEMINI_API_KEY not found in environment")
    exit(1)

genai.configure(api_key=api_key)

print("📋 Listing all available models:\n")
print("=" * 80)

for model in genai.list_models():
    print(f"\n🔹 Model: {model.name}")
    print(f"   Display Name: {model.display_name}")
    print(f"   Description: {model.description}")
    print(f"   Supported Methods: {model.supported_generation_methods}")
    if hasattr(model, 'input_token_limit'):
        print(f"   Input Token Limit: {model.input_token_limit:,}")
    if hasattr(model, 'output_token_limit'):
        print(f"   Output Token Limit: {model.output_token_limit:,}")

print("\n" + "=" * 80)
print("\n✅ Done! Check if any model supports image generation methods")
