"""
Image Generation System using Gemini 2.0 Flash
Handles image generation, editing, and vision capabilities
"""

import discord
from discord.ext import commands
from discord import app_commands
import google.generativeai as genai
import os
import aiohttp
import io
from PIL import Image
from utils.helpers import load_json, save_json
import time

class ImageGenerationCog(commands.Cog, name="ImageGen"):
    def __init__(self, bot):
        self.bot = bot
        
        # Initialize Gemini 2.0 Flash for image generation
        self.image_model = None
        self._setup_image_model()
        
        # Track daily usage
        self.usage_data = self._load_usage_data()
        self.daily_generations = self.usage_data.get('daily_generations', 0)
        self.last_reset = self.usage_data.get('last_reset', time.time())
        
    def _setup_image_model(self):
        """Initialize Gemini 2.0 Flash model for image generation"""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                print("❌ GEMINI_API_KEY not found in environment")
                return
            
            genai.configure(api_key=api_key)
            
            # Try different model names for image generation
            model_names = [
                'gemini-2.0-flash-exp',
                'gemini-exp-1206',
                'imagen-3.0-generate-001',
                'imagen-3.0-fast-generate-001'
            ]
            
            for model_name in model_names:
                try:
                    self.image_model = genai.GenerativeModel(model_name)
                    print(f"✅ Image model initialized: {model_name}")
                    return
                except Exception as e:
                    print(f"⚠️ Failed to load {model_name}: {e}")
                    continue
            
            print("❌ No suitable image generation model found")
            
        except Exception as e:
            print(f"❌ Failed to initialize image model: {e}")
    
    def _load_usage_data(self):
        """Load usage tracking data"""
        try:
            return load_json('data/image_generation_usage.json')
        except:
            return {"daily_generations": 0, "last_reset": time.time()}
    
    def _save_usage_data(self):
        """Save usage tracking data"""
        self.usage_data['daily_generations'] = self.daily_generations
        self.usage_data['last_reset'] = self.last_reset
        save_json('data/image_generation_usage.json', self.usage_data)
    
    def _check_and_reset_daily_limit(self):
        """Check if we need to reset the daily counter"""
        current_time = time.time()
        # Reset after 24 hours
        if current_time - self.last_reset > 86400:
            self.daily_generations = 0
            self.last_reset = current_time
            self._save_usage_data()
            print("🔄 Daily image generation limit reset")
    
    def can_generate_image(self) -> bool:
        """Check if we can generate an image (under 100/day limit)"""
        self._check_and_reset_daily_limit()
        return self.daily_generations < 100
    
    async def download_image(self, url: str) -> Image.Image:
        """Download an image from URL and return PIL Image"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    return Image.open(io.BytesIO(image_data))
        return None
    
    async def generate_image(self, prompt: str, reference_image: Image.Image = None) -> bytes:
        """Generate or edit an image using Gemini 2.0 Flash"""
        if not self.image_model:
            print("❌ Image model not initialized")
            return None
        
        if not self.can_generate_image():
            print("⚠️ Daily image generation limit reached (100/day)")
            return None
        
        try:
            print(f"🎨 Attempting image generation with prompt: {prompt[:100]}")
            
            # Gemini 2.0 Flash Experimental has image generation
            # The correct way to request image generation
            if reference_image:
                # Image editing mode - provide both prompt and reference
                full_prompt = f"Based on this image, {prompt}. Generate a new image that applies these changes."
                response = self.image_model.generate_content(
                    [full_prompt, reference_image],
                    generation_config=genai.GenerationConfig(
                        response_modalities=["image"]
                    )
                )
            else:
                # Pure generation mode
                response = self.image_model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_modalities=["image"]
                    )
                )
            
            print(f"📥 Response received, checking for image data...")
            print(f"Response parts: {len(response.parts) if response.parts else 0}")
            
            # Increment usage counter
            self.daily_generations += 1
            self._save_usage_data()
            
            # Extract image from response
            if response.parts:
                for i, part in enumerate(response.parts):
                    print(f"Part {i}: {type(part)}, has inline_data: {hasattr(part, 'inline_data')}")
                    if hasattr(part, 'inline_data') and part.inline_data:
                        if hasattr(part.inline_data, 'data'):
                            print(f"✅ Found image data in part {i}")
                            return part.inline_data.data
                        if hasattr(part.inline_data, 'mime_type'):
                            print(f"Mime type: {part.inline_data.mime_type}")
            
            print("❌ No image data found in response")
            return None
            
        except Exception as e:
            print(f"❌ Image generation error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def detect_image_request(self, message_content: str) -> dict:
        """Detect if user wants image generation/editing"""
        content_lower = message_content.lower()
        
        # Image generation keywords
        generation_keywords = [
            'generate', 'create', 'make', 'draw', 'show me',
            'can you make', 'can you create', 'can you draw',
            'generate an image', 'create an image', 'make an image'
        ]
        
        # Image editing keywords
        editing_keywords = [
            'edit', 'change', 'modify', 'transform', 'turn into',
            'make it', 'add', 'remove', 'replace', 'halloween theme',
            'christmas theme', 'anime style', 'cartoon style'
        ]
        
        # Profile picture keywords
        pfp_keywords = [
            'pfp', 'profile picture', 'avatar', 'profile pic',
            'my pfp', 'their pfp', 'his pfp', 'her pfp'
        ]
        
        is_generation = any(keyword in content_lower for keyword in generation_keywords)
        is_editing = any(keyword in content_lower for keyword in editing_keywords)
        wants_pfp = any(keyword in content_lower for keyword in pfp_keywords)
        
        if is_generation or is_editing:
            return {
                'type': 'edit' if is_editing else 'generate',
                'wants_pfp': wants_pfp,
                'detected': True
            }
        
        return {'detected': False}
    
    async def handle_image_request(self, message: discord.Message, prompt: str, image_url: str = None):
        """Handle an image generation/editing request"""
        if not self.can_generate_image():
            remaining = 100 - self.daily_generations
            await message.reply(
                f"sorry! i've hit my daily image generation limit (100/day) 😅\n"
                f"i'll be able to make more images tomorrow!",
                mention_author=False
            )
            return
        
        try:
            # Show typing indicator
            async with message.channel.typing():
                reference_image = None
                
                # Download reference image if provided
                if image_url:
                    reference_image = await self.download_image(image_url)
                
                # Generate the image
                image_data = await self.generate_image(prompt, reference_image)
                
                if image_data:
                    # Create Discord file from image data
                    file = discord.File(io.BytesIO(image_data), filename="generated_image.png")
                    
                    remaining = 100 - self.daily_generations
                    await message.reply(
                        f"here you go! ✨\n*({remaining} generations left today)*",
                        file=file,
                        mention_author=False
                    )
                else:
                    await message.reply(
                        "sorry, something went wrong generating that image 😅",
                        mention_author=False
                    )
        
        except Exception as e:
            print(f"❌ Error handling image request: {e}")
            await message.reply(
                "oops, had trouble making that image!",
                mention_author=False
            )
    
    @app_commands.command(name="generateimage", description="Generate an image using AI")
    @app_commands.describe(prompt="Description of the image you want to generate")
    async def generate_image_command(self, interaction: discord.Interaction, prompt: str):
        """Generate an image from a text prompt"""
        if not self.can_generate_image():
            remaining = 100 - self.daily_generations
            await interaction.response.send_message(
                f"❌ Daily limit reached! ({self.daily_generations}/100 used today)\n"
                f"Resets in {24 - ((time.time() - self.last_reset) / 3600):.1f} hours",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            image_data = await self.generate_image(prompt)
            
            if image_data:
                file = discord.File(io.BytesIO(image_data), filename="generated.png")
                remaining = 100 - self.daily_generations
                
                embed = discord.Embed(
                    title="🎨 Image Generated",
                    description=f"*{prompt[:200]}*",
                    color=discord.Color.purple()
                )
                embed.set_footer(text=f"{remaining} generations remaining today")
                
                await interaction.followup.send(embed=embed, file=file)
            else:
                await interaction.followup.send("❌ Failed to generate image")
        
        except Exception as e:
            print(f"Error in generate command: {e}")
            await interaction.followup.send("❌ Error generating image")
    
    @app_commands.command(name="imagestats", description="Check image generation usage stats")
    async def image_stats(self, interaction: discord.Interaction):
        """Show image generation statistics"""
        self._check_and_reset_daily_limit()
        
        remaining = 100 - self.daily_generations
        hours_until_reset = 24 - ((time.time() - self.last_reset) / 3600)
        
        embed = discord.Embed(
            title="📊 Image Generation Stats",
            color=discord.Color.blue()
        )
        embed.add_field(name="Used Today", value=f"{self.daily_generations}/100", inline=True)
        embed.add_field(name="Remaining", value=str(remaining), inline=True)
        embed.add_field(name="Resets In", value=f"{hours_until_reset:.1f} hours", inline=True)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ImageGenerationCog(bot))
