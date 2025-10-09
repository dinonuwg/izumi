"""
Quick script to list all available Gemini models
"""
import google.generativeai as genai
import os
import sys
from dotenv import load_dotenv

# Force UTF-8 encoding for output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Configure API
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print("GEMINI_API_KEY not found in environment")
    exit(1)

genai.configure(api_key=api_key)

print("Listing all available models:\n")
print("=" * 80)

image_models = []

for model in genai.list_models():
    # Check if it's an image generation model
    is_image_model = (
        'image' in model.name.lower() or 
        'imagen' in model.name.lower() or
        'nano banana' in model.display_name.lower()
    )
    
    if is_image_model:
        image_models.append(model)
    
    print(f"\nModel: {model.name}")
    print(f"   Display Name: {model.display_name}")
    print(f"   Description: {model.description}")
    print(f"   Supported Methods: {model.supported_generation_methods}")
    if hasattr(model, 'input_token_limit'):
        print(f"   Input Token Limit: {model.input_token_limit:,}")
    if hasattr(model, 'output_token_limit'):
        print(f"   Output Token Limit: {model.output_token_limit:,}")

print("\n" + "=" * 80)
print("\nIMAGE GENERATION MODELS FOUND:")
print("=" * 80)
for model in image_models:
    print(f"\n{model.name}")
    print(f"   Display: {model.display_name}")
    print(f"   Methods: {model.supported_generation_methods}")

print("\n" + "=" * 80)
print("\nDone! Check the image models above")
