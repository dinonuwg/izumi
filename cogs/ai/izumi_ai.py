"""
Main AI Chat Cog for Izumi
Handles AI conversations, integrates learning engine and context builder
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import google.generativeai as genai
import os
import time
import asyncio
from typing import Dict, Optional

from .learning_engine import LearningEngine
from .context_builder_fixed import ContextBuilder
from utils.helpers import save_json, load_json

class IzumiAI(commands.Cog):
    """Main AI chat system with advanced learning capabilities"""
    
    def __init__(self, bot):
        self.bot = bot
        # Use the unified memory system instead of separate learning engine
        self.learning_engine = self.bot.unified_memory
        self.context_builder = ContextBuilder(bot, self.learning_engine)
        
        # Initialize Gemini AI
        self.gemini_model = None
        self.gemini_chat_sessions = {}  # {user_id: session_data}
        self.chat_history_limit = 250  # Messages per user
        
        # Setup Gemini
        self._setup_gemini()
        
        # Start background tasks
        self.save_learning_data_task.start()
        self.cleanup_learning_data_task.start()
    
    def _setup_gemini(self):
        """Initialize Gemini AI model"""
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
        
        if not GEMINI_API_KEY:
            print("Warning: GEMINI_API_KEY not found. AI chat features will be disabled.")
            return
        
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Safety settings
        self.safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        # Model hierarchy (best → fallback)
        MODEL_HIERARCHY = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite", 
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
        ]
        
        # Try to initialize model
        for model_name in MODEL_HIERARCHY:
            try:
                self.gemini_model = genai.GenerativeModel(
                    model_name=model_name,
                    safety_settings=self.safety_settings,
                    system_instruction=self.bot.system_prompt
                )
                print(f"Gemini AI model initialized with: {model_name}")
                break
            except Exception as e:
                print(f"Failed to init {model_name}, trying next... ({e})")
        
        if not self.gemini_model:
            print("⚠️ No Gemini models available.")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle all messages for learning and AI responses"""
        if message.author.bot or not message.guild:
            return
        
        # ALWAYS learn from messages (even when not mentioned)
        await self.learning_engine.learn_from_message(message)
        
        # Handle AI responses when mentioned
        if self.bot.user in message.mentions:
            await self._handle_ai_response(message)
    
    async def _handle_ai_response(self, message: discord.Message):
        """Generate and send AI response"""
        if not self.gemini_model:
            return
        
        # Check for emotional responses first (for users returning after absence)
        emotional_context = self.learning_engine.get_emotional_context(message.author.id, message.guild.id)
        
        # For strong emotional situations, use pre-generated response
        if emotional_context["type"] in ["completely_absent", "being_ignored"] and emotional_context.get("message"):
            await message.reply(emotional_context["message"])
            return
        
        # START TYPING INDICATOR - Shows "Izumi is typing..." in Discord
        async with message.channel.typing():
            try:
                # Remove bot mention from message for processing
                prompt = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
                prompt = message.content.replace(f'<@!{self.bot.user.id}>', '').strip()
                
                if not prompt:
                    prompt = "hello"
                
                # Process mentions for AI context
                processed_prompt = self.bot.process_mentions_for_ai(prompt, message.guild.id)
                
                # Build comprehensive context
                context = self.context_builder.build_smart_context(
                    user_id=message.author.id,
                    guild_id=message.guild.id,
                    current_message=processed_prompt,
                    channel_id=message.channel.id
                )
                
                # Create full prompt with context
                full_prompt = f"{context}\n\nUser message: {processed_prompt}"
                
                # Generate response with fallback system
                response_text = await self._generate_response_with_fallback(
                    user_id=message.author.id,
                    prompt=full_prompt,
                    original_message=processed_prompt
                )
                
                if not response_text:
                    response_text = "sorry, having technical issues rn"
                
                # Trim response if too long
                if len(response_text) > 2000:
                    response_text = response_text[:1990] + "... (trimmed)"
                
                # Send response
                await message.reply(response_text, mention_author=False)
                
                # Analyze the response for self-learning
                await self._analyze_own_response(message.author.id, processed_prompt, response_text)
                
            except Exception as e:
                print(f"Error in AI response: {e}")
                await message.reply("something went wrong, try again?", mention_author=False)
    
    async def _generate_response_with_fallback(self, user_id: int, prompt: str, original_message: str) -> Optional[str]:
        """Generate response with model fallback and error handling"""
        session_data = self._get_or_create_session(user_id)
        
        MODEL_HIERARCHY = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro", 
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
        ]
        
        for i, model_name in enumerate(MODEL_HIERARCHY):
            try:
                # Switch model if needed
                if session_data["model_index"] != i:
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        safety_settings=self.safety_settings,
                        system_instruction=self.bot.system_prompt
                    )
                    history = session_data["chat"].history if session_data["chat"] else []
                    session_data["chat"] = model.start_chat(history=history)
                    session_data["model_index"] = i
                
                chat = session_data["chat"]
                response = await chat.send_message_async(prompt)
                return response.text
                
            except Exception as e:
                error_str = str(e)
                
                if "PROHIBITED_CONTENT" in error_str:
                    return "Filtered."
                elif "429" in error_str or "quota" in error_str.lower():
                    print(f"⚠️ Rate limit on {model_name}, falling back...")
                    continue  # Try next model
                else:
                    print(f"Error with {model_name}: {e}")
                    continue
        
        # All models failed
        return None
    
    def _get_or_create_session(self, user_id: int) -> Dict:
        """Get or create chat session for user"""
        if user_id not in self.gemini_chat_sessions:
            self.gemini_chat_sessions[user_id] = {
                "chat": None,
                "model_index": 0,
                "message_count": 0,
                "created_at": time.time()
            }
        
        session = self.gemini_chat_sessions[user_id]
        
        # Create chat if doesn't exist
        if not session["chat"]:
            try:
                session["chat"] = self.gemini_model.start_chat()
            except Exception as e:
                print(f"Failed to create chat session: {e}")
        
        # Limit chat history
        session["message_count"] += 1
        if session["message_count"] > self.chat_history_limit:
            # Reset session to limit context length
            try:
                session["chat"] = self.gemini_model.start_chat()
                session["message_count"] = 1
                print(f"Reset chat session for user {user_id} (hit message limit)")
            except Exception as e:
                print(f"Failed to reset chat session: {e}")
        
        return session
    
    async def _analyze_own_response(self, user_id: int, user_message: str, ai_response: str):
        """Analyze AI's own responses to improve learning"""
        # This could be used to learn from successful interactions
        # For example, track what types of responses get positive reactions
        user_id_str = str(user_id)
        
        # Ensure user exists in memory system
        if user_id_str not in self.learning_engine.memory_data['users']:
            self.learning_engine.memory_data['users'][user_id_str] = self.learning_engine._create_empty_user_profile()
        
        # Store response patterns for analysis using unified memory structure
        if 'ai_response_patterns' not in self.learning_engine.memory_data['users'][user_id_str]['learning_data']:
            self.learning_engine.memory_data['users'][user_id_str]['learning_data']['ai_response_patterns'] = []
        
        self.learning_engine.memory_data['users'][user_id_str]['learning_data']['ai_response_patterns'].append({
            'user_message': user_message[:100],  # Truncate for storage
            'ai_response': ai_response[:100],
            'timestamp': int(time.time()),
            'response_length': len(ai_response.split())
        })
        
        # Keep only recent response patterns
        patterns = self.learning_engine.memory_data['users'][user_id_str]['learning_data']['ai_response_patterns']
        if len(patterns) > 50:
            self.learning_engine.memory_data['users'][user_id_str]['learning_data']['ai_response_patterns'] = patterns[-50:]
    
    @commands.command(name='ai_stats')
    @commands.has_permissions(administrator=True)
    async def ai_stats(self, ctx):
        """Show AI learning statistics"""
        # Get learning data from unified memory structure
        memory_data = self.learning_engine.memory_data
        users_data = memory_data.get('users', {})
        
        embed = discord.Embed(
            title="🤖 AI Learning Statistics",
            color=discord.Color.blue()
        )
        
        # General stats - count users with various data types
        vocab_users = sum(1 for user_data in users_data.values() 
                         if user_data.get('learning_data', {}).get('vocabulary_trends'))
        sentiment_users = sum(1 for user_data in users_data.values() 
                             if user_data.get('learning_data', {}).get('sentiment_patterns'))
        relationship_users = sum(1 for user_data in users_data.values() 
                                if user_data.get('learning_data', {}).get('relationship_networks'))
        
        embed.add_field(
            name="📊 Learning Coverage",
            value=f"👥 Total Users: {len(users_data)}\n"
                  f"📝 Vocabulary Tracking: {vocab_users}\n"
                  f"😊 Sentiment Analysis: {sentiment_users}\n"
                  f"🤝 Relationship Networks: {relationship_users}",
            inline=False
        )
        
        active_sessions = len(self.gemini_chat_sessions)
        
        embed.add_field(name="📱 Active Sessions", value=active_sessions, inline=True)
        
        # Server culture stats - not implemented in unified memory yet
        # This could be added later if needed
        
        # Recent activity
        recent_activity = 0
        current_time = time.time()
        for session in self.gemini_chat_sessions.values():
            if current_time - session.get('created_at', 0) < 3600:  # Last hour
                recent_activity += 1
        
        embed.add_field(name="Active in last hour", value=recent_activity, inline=True)
        
        await ctx.send(embed=embed)
    
    @app_commands.command(name="ai_stats", description="Show AI learning statistics (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def slash_ai_stats(self, interaction: discord.Interaction):
        """Show AI learning statistics (slash command version)"""
        # Get learning data from unified memory structure
        memory_data = self.learning_engine.memory_data
        users_data = memory_data.get('users', {})
        
        embed = discord.Embed(
            title="🤖 AI Learning Statistics",
            color=discord.Color.blue()
        )
        
        # General stats - count users with various data types
        vocab_users = sum(1 for user_data in users_data.values() 
                         if user_data.get('learning_data', {}).get('vocabulary_trends'))
        sentiment_users = sum(1 for user_data in users_data.values() 
                             if user_data.get('learning_data', {}).get('sentiment_patterns'))
        relationship_users = sum(1 for user_data in users_data.values() 
                                if user_data.get('learning_data', {}).get('relationship_networks'))
        
        embed.add_field(
            name="📊 Learning Coverage",
            value=f"👥 Total Users: {len(users_data)}\n"
                  f"📝 Vocabulary Tracking: {vocab_users}\n"
                  f"😊 Sentiment Analysis: {sentiment_users}\n"
                  f"🤝 Relationship Networks: {relationship_users}",
            inline=False
        )
        
        active_sessions = len(self.gemini_chat_sessions)
        
        embed.add_field(name="📱 Active Sessions", value=active_sessions, inline=True)
        
        # Recent activity
        recent_activity = 0
        current_time = time.time()
        for session in self.gemini_chat_sessions.values():
            if current_time - session.get('created_at', 0) < 3600:  # Last hour
                recent_activity += 1
        
        embed.add_field(name="Active in last hour", value=recent_activity, inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @commands.command(name='ai_context')
    @commands.has_permissions(administrator=True)
    async def ai_context(self, ctx, user: discord.Member = None):
        """Show context data available for a user"""
        if not user:
            user = ctx.author
        
        summary = self.context_builder.get_context_summary(user.id, ctx.guild.id)
        
        embed = discord.Embed(
            title=f"📊 Context Data for {user.display_name}",
            color=discord.Color.green()
        )
        
        # Data availability
        data_fields = {
            'vocabulary_data': 'Vocabulary Patterns',
            'relationship_data': 'Relationship Networks',
            'communication_style': 'Communication Style',
            'topic_interests': 'Topic Interests',
            'sentiment_data': 'Sentiment Patterns',
            'activity_patterns': 'Activity Patterns',
            'server_culture': 'Server Culture Data'
        }
        
        for key, name in data_fields.items():
            status = "✅" if summary.get(key, False) else "❌"
            embed.add_field(name=name, value=status, inline=True)
        
        # Detailed counts
        if summary.get('vocab_word_count'):
            embed.add_field(name="Words Tracked", value=summary['vocab_word_count'], inline=True)
        if summary.get('vocab_slang_count'):
            embed.add_field(name="Slang Terms", value=summary['vocab_slang_count'], inline=True)
        if summary.get('unique_mentions'):
            embed.add_field(name="Users Mentioned", value=summary['unique_mentions'], inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='reset_chat')
    async def reset_chat(self, ctx, user: discord.Member = None):
        """Reset chat session for a user"""
        if not user:
            user = ctx.author
        
        # Only allow users to reset their own session or admins to reset anyone's
        if user != ctx.author and not ctx.author.guild_permissions.administrator:
            await ctx.send("You can only reset your own chat session!")
            return
        
        if user.id in self.gemini_chat_sessions:
            del self.gemini_chat_sessions[user.id]
            await ctx.send(f"✅ Reset chat session for {user.display_name}")
        else:
            await ctx.send(f"No active chat session found for {user.display_name}")
    
    @tasks.loop(minutes=10)
    async def save_learning_data_task(self):
        """Periodically save unified memory data"""
        try:
            await self.learning_engine.auto_save()
            # print("🧠 Auto-saved unified memory data")
        except Exception as e:
            print(f"Error saving unified memory data: {e}")
    
    @tasks.loop(hours=6)
    async def cleanup_learning_data_task(self):
        """Clean up old learning data"""
        try:
            await self._cleanup_old_data()
            # print("🧹 Cleaned up old learning data")
        except Exception as e:
            print(f"Error cleaning up learning data: {e}")
    
    async def _cleanup_old_data(self):
        """Remove old and excessive learning data"""
        memory_data = self.learning_engine.memory_data
        current_time = time.time()
        cutoff_time = current_time - (30 * 24 * 60 * 60)  # 30 days
        
        # Clean up old chat sessions
        sessions_to_remove = []
        for user_id, session in self.gemini_chat_sessions.items():
            if current_time - session.get('created_at', 0) > 24 * 60 * 60:  # 24 hours
                sessions_to_remove.append(user_id)
        
        for user_id in sessions_to_remove:
            del self.gemini_chat_sessions[user_id]
        
        # Clean up learning data for inactive users in unified memory
        if 'users' in memory_data:
            for user_id_str in list(memory_data['users'].keys()):
                try:
                    user_id = int(user_id_str)
                    user_data = memory_data['users'][user_id_str]
                    last_interaction = user_data.get('activity', {}).get('last_interaction', 0)
                    
                    if last_interaction < cutoff_time:
                        # Trim learning data for inactive users
                        learning_data = user_data.get('learning_data', {})
                        
                        if 'vocabulary' in learning_data:
                            vocab = learning_data['vocabulary']
                            # Keep only top items
                            if len(vocab.get('word_frequency', {})) > 30:
                                sorted_words = sorted(vocab['word_frequency'].items(), key=lambda x: x[1], reverse=True)
                                vocab['word_frequency'] = dict(sorted_words[:30])
                            
                            vocab['message_lengths'] = vocab.get('message_lengths', [])[-50:]
                            vocab['question_patterns'] = vocab.get('question_patterns', [])[-10:]
                            vocab['exclamation_patterns'] = vocab.get('exclamation_patterns', [])[-10:]
                except:
                    continue
    
    def cog_unload(self):
        """Clean shutdown"""
        self.save_learning_data_task.cancel()
        self.cleanup_learning_data_task.cancel()
        
        # Save data before shutdown
        try:
            self.learning_engine.save_unified_data()
        except Exception as e:
            print(f"Error saving data during shutdown: {e}")

async def setup(bot):
    await bot.add_cog(IzumiAI(bot))
