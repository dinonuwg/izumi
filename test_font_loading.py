#!/usr/bin/env python3
"""
Test script to verify cross-platform font loading
"""

import os
from PIL import Image, ImageDraw, ImageFont

def test_font_loading(font_name, size):
    """Test the cross-platform font loading logic"""
    print(f"\nTesting font: {font_name} (size {size})")
    
    # Mirror the logic from _get_cached_font
    font_options = []
    
    if font_name == "arialbd.ttf":  # Arial Bold
        if os.name == 'nt':  # Windows
            font_options = [
                "arialbd.ttf",
                "arial-bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
        else:  # Linux/Unix
            font_options = [
                "DejaVuSans-Bold.ttf",
                "LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/System/Library/Fonts/Arial Bold.ttf",  # macOS
            ]
    elif font_name == "arial.ttf":  # Arial Regular
        if os.name == 'nt':  # Windows
            font_options = [
                "arial.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
        else:  # Linux/Unix
            font_options = [
                "DejaVuSans.ttf",
                "LiberationSans-Regular.ttf", 
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/System/Library/Fonts/Arial.ttf",  # macOS
            ]
    else:
        font_options = [font_name]
    
    # Try each font option
    for i, font_option in enumerate(font_options):
        try:
            font = ImageFont.truetype(font_option, size)
            print(f"  ✅ SUCCESS: {font_option}")
            return font
        except Exception as e:
            print(f"  ❌ Failed: {font_option} - {type(e).__name__}")
    
    # Fall back to default
    try:
        font = ImageFont.load_default().font_variant(size=size)
        print(f"  ⚠️  Using default font with size variant")
        return font
    except:
        font = ImageFont.load_default()
        print(f"  ⚠️  Using basic default font (may be small)")
        return font

if __name__ == "__main__":
    print(f"Platform: {os.name} ({os.name == 'nt' and 'Windows' or 'Unix/Linux'})")
    
    # Test the fonts used in the gacha system
    test_fonts = [
        ("arialbd.ttf", 32),  # title_font
        ("arialbd.ttf", 20),  # text_font  
        ("arial.ttf", 16),    # small_font
        ("arialbd.ttf", 22),  # value_font
        ("arialbd.ttf", 24),  # icon_font
    ]
    
    for font_name, size in test_fonts:
        font = test_font_loading(font_name, size)
    
    print("\n✨ Font loading test completed!")
