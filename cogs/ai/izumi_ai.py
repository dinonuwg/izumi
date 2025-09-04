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
import random
from typing import Dict, Optional

from .learning_engine import LearningEngine
from .context_builder import ContextBuilder
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
        self.gemini_chat_sessions = {}  # {channel_id: session_data} - Shared per channel
        self.chat_history_limit = 250  # Messages per channel
        
        # Track Izumi's conversation participation
        self.participation_tracker = {}  # {channel_id: {"last_participation": timestamp, "is_active": bool}}
        
        # Track recent responses to prevent duplicates
        self.recent_responses = {}  # {user_id: timestamp} - Track last response time per user
        
        # API optimization features
        self.response_cache = {}  # Simple response caching
        self.daily_api_calls = 0
        self.daily_quick_responses = 0  # Track quick responses too
        self.last_cache_clear = time.time()
        
        # Detailed tracking
        self.api_call_log = []  # Store recent API calls for analysis
        
        # Python-based response patterns to reduce API calls
        self.quick_responses = self._init_quick_responses()
        
        # Setup Gemini
        self._setup_gemini()
        
        # Start background tasks
        self.save_learning_data_task.start()
        self.cleanup_learning_data_task.start()
    
    def _init_quick_responses(self):
        """Initialize Python-based quick responses to reduce API calls"""
        return {
            # Greetings (exact matches, case insensitive)
            'greetings': {
                'patterns': ['hi', 'hello', 'hey', 'sup', 'yo', 'hiya', 'heya'],
                'responses': [
                    'hey there!',
                    'hiya~',
                    'hello! ✨',
                    'hey hey!',
                    'hi! how\'s it going?',
                    'heyyy',
                    'wassup!',
                    'oh hai there'
                ]
            },
            
            # Simple questions
            'how_are_you': {
                'patterns': ['how are you', 'how r u', 'how are u', 'how you doing', 'how ya doing'],
                'responses': [
                    'doing great! thanks for asking ^^',
                    'pretty good! just vibing~',
                    'i\'m doing well! how about you?',
                    'all good here! what about you?',
                    'doing amazing! hope you are too',
                    'pretty chill today, thanks!',
                    'good! just hanging out in here'
                ]
            },
            
            # Thanks
            'thanks': {
                'patterns': ['thanks', 'thank you', 'thx', 'ty', 'tysm', 'thank u'],
                'responses': [
                    'you\'re welcome!',
                    'no problem!',
                    'anytime! ^^',
                    'happy to help!',
                    'of course!',
                    'np!',
                    'always here to help~'
                ]
            },
            
            # Simple affirmations
            'yes_no': {
                'patterns': ['yes', 'yeah', 'yep', 'yup', 'no', 'nope', 'nah'],
                'responses': [
                    'gotcha!',
                    'alright!',
                    'okay!',
                    'sounds good',
                    'cool cool',
                    'fair enough',
                    'makes sense'
                ]
            },
            
            # Good night/morning
            'time_greetings': {
                'patterns': ['good morning', 'good night', 'goodnight', 'gn', 'gm', 'good evening'],
                'responses': [
                    'good morning!',
                    'good night! sleep well~',
                    'sweet dreams!',
                    'have a great day!',
                    'good evening!',
                    'night night!',
                    'morning! hope you have a good day'
                ]
            },
            
            # Laughter responses
            'laughter': {
                'patterns': ['lol', 'lmao', 'haha', 'lmfao', 'rofl', 'xd'],
                'responses': [
                    'hehe',
                    'ikr!',
                    'lmao',
                    'haha nice',
                    'that\'s funny',
                    'lol',
                    '😄'
                ]
            }
        }

    def _check_quick_response(self, message_content: str) -> str:
        """Check if we can use a quick Python response instead of API call"""
        content_lower = message_content.lower().strip()
        
        # Remove common punctuation for matching
        content_clean = content_lower.replace('!', '').replace('?', '').replace('.', '').replace(',', '')
        
        for category, data in self.quick_responses.items():
            for pattern in data['patterns']:
                if pattern == content_clean or (len(content_clean.split()) <= 3 and pattern in content_clean):
                    # Use mood to influence response selection
                    try:
                        mood_data = self.bot.unified_memory.get_daily_mood()
                        current_mood = mood_data['current_mood']
                        
                        # Filter responses based on mood
                        responses = data['responses']
                        if current_mood == 'sleepy':
                            # Prefer shorter, more casual responses when sleepy
                            responses = [r for r in responses if len(r) < 15] or responses
                        elif current_mood == 'excited':
                            # Prefer more energetic responses when excited
                            responses = [r for r in responses if '!' in r or '~' in r] or responses
                        
                        return random.choice(responses)
                    except:
                        return random.choice(data['responses'])
        
        return None
    
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
            print(f"🤖 {message.author.display_name} mentioned Izumi: {message.content[:100]}...")
            await self._handle_ai_response(message)
        else:
            # Check if someone mentioned "izumi" and she recently participated
            if await self._should_continue_conversation(message):
                await self._continue_conversation(message)
            else:
                # Check for conversation participation opportunity
                await self._check_conversation_participation(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Handle message edits - respond to corrected messages that mention Izumi"""
        if after.author.bot or not after.guild:
            return
        
        # Only respond to edits if:
        # 1. The edited message now mentions Izumi (but didn't before)
        # 2. OR the message mentioned Izumi before but content significantly changed
        
        before_mentions_izumi = self.bot.user in before.mentions
        after_mentions_izumi = self.bot.user in after.mentions
        
        # Case 1: Now mentions Izumi (but didn't before)
        if after_mentions_izumi and not before_mentions_izumi:
            print(f"📝 Message edited to mention Izumi: {after.content[:50]}...")
            await self._handle_ai_response(after)
            return
        
        # Case 2: Already mentioned Izumi, but content changed significantly
        if before_mentions_izumi and after_mentions_izumi:
            # Check if the content changed significantly (more than just typo fixes)
            before_clean = before.content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()
            after_clean = after.content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()
            
            # Simple similarity check - if less than 70% similar, respond to the edit
            similarity = self._calculate_text_similarity(before_clean, after_clean)
            if similarity < 0.7:
                print(f"📝 Significant edit detected (similarity: {similarity:.2f}): {after.content[:50]}...")
                # Add a small delay to avoid instant responses to edits
                await asyncio.sleep(2)
                await self._handle_ai_response(after)
            else:
                print(f"📝 Minor edit detected (similarity: {similarity:.2f}), ignoring")

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity between two strings"""
        if not text1 or not text2:
            return 0.0
        
        # Simple word-based similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    async def _check_conversation_participation(self, message: discord.Message):
        """Check if Izumi should join an active conversation"""
        if not self.gemini_model:
            return
        
        conversation_analysis = self.learning_engine.detect_active_conversation(message.channel.id)
        
        if conversation_analysis["should_participate"]:
            print(f"🎭 Joining conversation in #{message.channel.name} - {conversation_analysis['message_count']} messages from {len(conversation_analysis['participants'])} users")
            
            # Generate contextual response to join the conversation
            context = conversation_analysis["conversation_context"]
            
            # Add a small delay to make it feel more natural
            import asyncio
            await asyncio.sleep(2)
            
            try:
                # Generate response with conversation context
                response_text = await self._generate_response_with_fallback(
                    user_id=message.author.id,
                    channel_id=message.channel.id,
                    prompt=context,
                    original_message="[joining conversation]",
                    username=message.author.display_name
                )
                
                if response_text and len(response_text.strip()) > 0:
                    # Split response into multiple messages if needed
                    message_parts = self._split_response_naturally(response_text)
                    
                    # Send each part with appropriate delays
                    for i, part in enumerate(message_parts):
                        # Show typing indicator with human-like delay
                        await self._type_with_delay(message.channel, part)
                        await message.channel.send(part)
                        
                        # Brief pause between multiple messages (if more than one part)
                        if len(message_parts) > 1 and i < len(message_parts) - 1:
                            await asyncio.sleep(random.uniform(2.0, 3.0))
                    
                    print(f"✅ Successfully joined conversation: {response_text[:50]}...")
                    
                    # Track that Izumi is now participating in this conversation
                    self.participation_tracker[message.channel.id] = {
                        "last_participation": time.time(),
                        "is_active": True
                    }
                
            except Exception as e:
                print(f"❌ Error joining conversation: {e}")

    async def _should_continue_conversation(self, message: discord.Message) -> bool:
        """Check if Izumi should continue participating in a conversation"""
        channel_id = message.channel.id
        
        # Check if we're tracking this channel
        if channel_id not in self.participation_tracker:
            return False
        
        tracker = self.participation_tracker[channel_id]
        
        # Check if Izumi is currently active in this conversation
        if not tracker.get("is_active", False):
            return False
        
        # Check if it's been less than 60 seconds since last participation
        time_since_last = time.time() - tracker.get("last_participation", 0)
        if time_since_last > 60:
            # Reset participation status if too much time has passed
            tracker["is_active"] = False
            return False
        
        # Check if message contains "izumi" (case insensitive)
        message_lower = message.content.lower()
        if "izumi" in message_lower:
            print(f"🎭 Continuing conversation in #{message.channel.name} - 'izumi' mentioned within 60s window")
            return True
        
        # Additional smart continuation triggers
        return await self._check_smart_continuation_triggers(message, tracker, time_since_last)

    async def _check_smart_continuation_triggers(self, message: discord.Message, tracker: dict, time_since_last: float) -> bool:
        """Check for intelligent conversation continuation triggers"""
        message_lower = message.content.lower()
        
        # 1. Direct questions to the group (30% chance within 30 seconds)
        question_words = ["what do you", "what does everyone", "anyone know", "does anyone", "what should", "which", "who thinks", "thoughts?", "opinions?"]
        if any(word in message_lower for word in question_words) and time_since_last <= 30:
            if self._random_chance(30):  # 30% chance
                print(f"🎭 Continuing conversation in #{message.channel.name} - question detected, 30% trigger")
                return True
        
        # 2. Controversial/opinion topics (20% chance within 45 seconds)
        opinion_triggers = ["i think", "i believe", "in my opinion", "personally", "i disagree", "i agree", "hot take", "unpopular opinion", "change my mind"]
        if any(trigger in message_lower for trigger in opinion_triggers) and time_since_last <= 45:
            if self._random_chance(20):  # 20% chance
                print(f"🎭 Continuing conversation in #{message.channel.name} - opinion topic detected, 20% trigger")
                return True
        
        # 3. When someone asks for help/advice (40% chance within 40 seconds)
        help_triggers = ["help", "how do i", "can someone", "need advice", "what's the best", "recommendations", "suggestions"]
        if any(trigger in message_lower for trigger in help_triggers) and time_since_last <= 40:
            if self._random_chance(40):  # 40% chance
                print(f"🎭 Continuing conversation in #{message.channel.name} - help request detected, 40% trigger")
                return True
        
        # 4. Emotional content (25% chance within 35 seconds)
        emotional_triggers = ["excited", "sad", "angry", "frustrated", "happy", "worried", "stressed", "amazing", "terrible", "love", "hate"]
        if any(trigger in message_lower for trigger in emotional_triggers) and time_since_last <= 35:
            if self._random_chance(25):  # 25% chance
                print(f"🎭 Continuing conversation in #{message.channel.name} - emotional content detected, 25% trigger")
                return True
        
        # 5. Follow-up to Izumi's last message (50% chance within 20 seconds)
        # This triggers when someone responds shortly after Izumi's message
        if time_since_last <= 20:
            # Check if this might be a response to Izumi
            response_indicators = ["yeah", "true", "exactly", "i agree", "disagree", "but", "however", "also", "plus", "additionally"]
            if any(indicator in message_lower for indicator in response_indicators):
                if self._random_chance(50):  # 50% chance
                    print(f"🎭 Continuing conversation in #{message.channel.name} - follow-up response detected, 50% trigger")
                    return True
        
        # 6. Gaming/tech topics that Izumi might be interested in (15% chance within 50 seconds)
        interest_triggers = ["osu", "anime", "gaming", "code", "programming", "discord", "bot", "ai", "technology", "computer"]
        if any(trigger in message_lower for trigger in interest_triggers) and time_since_last <= 50:
            if self._random_chance(15):  # 15% chance
                print(f"🎭 Continuing conversation in #{message.channel.name} - interest topic detected, 15% trigger")
                return True
        
        # 7. Conversation lull - proactively continue (10% chance if 15-25 seconds of silence)
        if 15 <= time_since_last <= 25:
            if self._random_chance(10):  # 10% chance to revive conversation
                print(f"🎭 Continuing conversation in #{message.channel.name} - conversation lull detected, 10% trigger")
                return True
        
        return False

    def _random_chance(self, percentage: int) -> bool:
        """Return True based on percentage chance"""
        import random
        return random.randint(1, 100) <= percentage

    async def _continue_conversation(self, message: discord.Message):
        """Continue participating in an ongoing conversation"""
        if not self.gemini_model:
            return
        
        try:
            # Build context from recent conversation
            context = self.context_builder.build_smart_context(
                user_id=message.author.id,
                guild_id=message.guild.id,
                current_message=message.content,
                channel_id=message.channel.id
            )
            
            # Determine the type of continuation and create appropriate prompt
            continuation_type = self._get_continuation_type(message)
            conversation_prompt = self._build_continuation_prompt(context, message, continuation_type)
            
            # Generate response
            response_text = await self._generate_response_with_fallback(
                user_id=message.author.id,
                channel_id=message.channel.id,
                prompt=conversation_prompt,
                original_message=message.content,
                username=message.author.display_name
            )
            
            if response_text and len(response_text.strip()) > 0:
                # Split response into multiple messages if needed
                message_parts = self._split_response_naturally(response_text)
                
                # Send each part with appropriate delays
                for i, part in enumerate(message_parts):
                    # Show typing indicator with human-like delay
                    await self._type_with_delay(message.channel, part)
                    await message.channel.send(part)
                    
                    # Brief pause between multiple messages (if more than one part)
                    if len(message_parts) > 1 and i < len(message_parts) - 1:
                        await asyncio.sleep(random.uniform(2.0, 3.0))
                
                print(f"✅ Continued conversation: {response_text[:50]}...")
                
                # Update participation tracker
                self.participation_tracker[message.channel.id]["last_participation"] = time.time()
            
        except Exception as e:
            print(f"❌ Error continuing conversation: {e}")

    def _get_continuation_type(self, message: discord.Message) -> str:
        """Determine what type of continuation this is"""
        message_lower = message.content.lower()
        
        if "izumi" in message_lower:
            return "name_mention"
        
        question_words = ["what do you", "what does everyone", "anyone know", "does anyone", "what should", "which", "who thinks", "thoughts?", "opinions?"]
        if any(word in message_lower for word in question_words):
            return "question"
        
        opinion_triggers = ["i think", "i believe", "in my opinion", "personally", "i disagree", "i agree", "hot take", "unpopular opinion"]
        if any(trigger in message_lower for trigger in opinion_triggers):
            return "opinion"
        
        help_triggers = ["help", "how do i", "can someone", "need advice", "what's the best", "recommendations", "suggestions"]
        if any(trigger in message_lower for trigger in help_triggers):
            return "help_request"
        
        emotional_triggers = ["excited", "sad", "angry", "frustrated", "happy", "worried", "stressed", "amazing", "terrible", "love", "hate"]
        if any(trigger in message_lower for trigger in emotional_triggers):
            return "emotional"
        
        response_indicators = ["yeah", "true", "exactly", "i agree", "disagree", "but", "however", "also", "plus", "additionally"]
        if any(indicator in message_lower for indicator in response_indicators):
            return "follow_up"
        
        interest_triggers = ["osu", "anime", "gaming", "code", "programming", "discord", "bot", "ai", "technology", "computer"]
        if any(trigger in message_lower for trigger in interest_triggers):
            return "interest_topic"
        
        # Check if this is a conversation lull (based on timing rather than content)
        channel_id = message.channel.id
        if channel_id in self.participation_tracker:
            time_since_last = time.time() - self.participation_tracker[channel_id].get("last_participation", 0)
            if 15 <= time_since_last <= 25:
                return "conversation_lull"
        
        return "general"

    def _build_continuation_prompt(self, context: str, message: discord.Message, continuation_type: str) -> str:
        """Build an appropriate prompt based on continuation type"""
        base_prompt = f"{context}\n\nUser message: {message.content}\n\n"
        
        instructions = {
            "name_mention": "Someone mentioned your name in the conversation. Respond naturally and appropriately to what they said.",
            
            "question": "Someone asked a question to the group. You can chime in with your thoughts or knowledge if you have something valuable to add. Keep it conversational and helpful.",
            
            "opinion": "Someone shared their opinion or belief. You can agree, disagree, or add your own perspective. Be respectful but feel free to have your own thoughts.",
            
            "help_request": "Someone is asking for help or advice. If you have useful knowledge or suggestions, share them in a helpful and supportive way.",
            
            "emotional": "Someone expressed emotions or feelings. Respond with appropriate empathy and support, or share in their excitement if it's positive.",
            
            "follow_up": "Someone seems to be responding or following up on the conversation. Continue the natural flow of discussion.",
            
            "interest_topic": "Someone mentioned a topic you might be interested in (gaming, tech, anime, etc.). Feel free to join in with your own thoughts or experiences.",
            
            "conversation_lull": "The conversation seems to be slowing down. You can ask a related question, make an observation, or share a thought to keep the discussion going naturally.",
            
            "general": "Continue participating in this ongoing conversation naturally."
        }
        
        instruction = instructions.get(continuation_type, instructions["general"])
        return f"{base_prompt}Instruction: {instruction}"
    
    async def _handle_ai_response(self, message: discord.Message):
        """Generate and send AI response with delay to catch follow-up messages"""
        if not self.gemini_model:
            return
        
        # Check if we recently responded to this user (prevent spam responses)
        user_id = message.author.id
        current_time = time.time()
        
        if user_id in self.recent_responses:
            time_since_last_response = current_time - self.recent_responses[user_id]
            if time_since_last_response < 15:  # Minimum 15 seconds between responses to same user
                print(f"⏳ Skipping response to {message.author.display_name} - responded {time_since_last_response:.1f}s ago")
                return
        
        # Mark that we're about to respond to this user
        self.recent_responses[user_id] = current_time
        
        # Wait 5 seconds to collect any follow-up messages from the same user
        await asyncio.sleep(5)
        
        # Collect recent messages from the same user in the last 10 seconds
        recent_messages = await self._collect_recent_user_messages(message)
        
        # Check for emotional responses first (for users returning after absence)
        emotional_context = self.learning_engine.get_emotional_context(message.author.id, message.guild.id)
        
        # For strong emotional situations, use pre-generated response
        if emotional_context["type"] in ["completely_absent", "being_ignored"] and emotional_context.get("message"):
            await message.reply(emotional_context["message"])
            return
        
        try:
            # Combine all recent messages from the user
            combined_prompt = self._combine_user_messages(recent_messages)
            
            if not combined_prompt:
                combined_prompt = "hello"
            
            # Check for quick Python responses first (saves API calls)
            quick_response = self._check_quick_response(combined_prompt)
            if quick_response:
                self.daily_quick_responses += 1
                print(f"🚀 Using quick response #{self.daily_quick_responses} (API saved): {quick_response}")
                
                # Split response if needed and send
                message_parts = self._split_response_naturally(quick_response)
                
                for i, part in enumerate(message_parts):
                    await self._type_with_delay(message.channel, part)
                    
                    if i == 0:
                        await message.reply(part, mention_author=False)
                    else:
                        await message.channel.send(part)
                    
                    # Brief pause between multiple messages (if more than one part)
                    if len(message_parts) > 1 and i < len(message_parts) - 1:
                        await asyncio.sleep(random.uniform(2.0, 3.0))
                
                # Track participation
                self.participation_tracker[message.channel.id] = {
                    "last_participation": time.time(),
                    "is_active": True
                }
                return
            
            # Process mentions for AI context
            processed_prompt = self.bot.process_mentions_for_ai(combined_prompt, message.guild.id)
            
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
                channel_id=message.channel.id,
                prompt=full_prompt,
                original_message=processed_prompt,
                username=message.author.display_name
            )
            
            if not response_text:
                response_text = "sorry, having technical issues rn"
            
            # Split response into multiple messages if needed
            message_parts = self._split_response_naturally(response_text)
            
            # Send each part with appropriate delays
            for i, part in enumerate(message_parts):
                # Show typing indicator with human-like delay
                await self._type_with_delay(message.channel, part)
                
                if i == 0:
                    # Reply to the original message for the first part
                    await message.reply(part, mention_author=False)
                else:
                    # Send follow-up messages normally
                    await message.channel.send(part)
                
                # Brief pause between multiple messages (if more than one part)
                if len(message_parts) > 1 and i < len(message_parts) - 1:
                    await asyncio.sleep(random.uniform(2.0, 3.0))
            
            # Track that Izumi is now participating in this conversation
            self.participation_tracker[message.channel.id] = {
                "last_participation": time.time(),
                "is_active": True
            }
            
        except Exception as e:
            print(f"Error in AI response: {e}")
            await message.reply("sorry, having technical issues rn", mention_author=False)

    async def _collect_recent_user_messages(self, original_message: discord.Message) -> list:
        """Collect recent conversation context from all users within 30 seconds"""
        messages = []
        
        try:
            # Get recent conversation context from ALL users, not just the original author
            async for msg in original_message.channel.history(limit=15, before=original_message.created_at):
                # Collect messages from anyone within 30 seconds for better conversation context
                time_diff = (original_message.created_at - msg.created_at).total_seconds()
                if time_diff <= 30 and not msg.author.bot:  # Don't include bot messages
                    messages.append(msg)
                elif time_diff > 30:
                    break
            
            # Add the original message
            messages.append(original_message)
            
            # Also get any messages that came AFTER (during the processing delay)
            async for msg in original_message.channel.history(limit=5, after=original_message.created_at):
                # Only collect messages from the original user within 10 seconds (for multi-part messages)
                time_diff = (msg.created_at - original_message.created_at).total_seconds()
                if msg.author == original_message.author and time_diff <= 10:
                    messages.append(msg)
                elif time_diff > 10:
                    break
                    
        except Exception as e:
            print(f"Error collecting recent messages: {e}")
            return [original_message]
        
        # Sort by timestamp to maintain order
        messages.sort(key=lambda m: m.created_at)
        print(f"📥 Collected {len(messages)} messages from conversation context (last 30s)")
        return messages

    def _combine_user_messages(self, messages: list) -> str:
        """Combine conversation context from multiple users into a natural prompt"""
        if not messages:
            return ""
        
        combined_parts = []
        for msg in messages:
            # Remove bot mentions from each message
            content = msg.content.replace(f'<@{self.bot.user.id}>', '').strip()
            content = content.replace(f'<@!{self.bot.user.id}>', '').strip()
            if content:
                # Include who said what for better context
                author_name = msg.author.display_name
                combined_parts.append(f"{author_name}: {content}")
        
        return '\n'.join(combined_parts)

    def _split_response_naturally(self, response: str) -> list:
        """Split response into natural message chunks with length-based probabilities"""
        import random
        
        # Debug logging
        print(f"🔧 Splitting response (length: {len(response)}): {response[:100]}...")
        
        # Always keep very short messages as single (under 30 characters)
        if len(response) < 30:
            print(f"🔧 Keeping short message as single")
            return [response]
        
        # 30-50 characters: 25% chance to split
        if 30 <= len(response) <= 50:
            if random.random() > 0.25:  # 75% chance to keep as single message
                print(f"🔧 Keeping 30-50 char message as single")
                return [response]
        
        # 50-100 characters: 50% chance to split
        elif 50 < len(response) <= 100:
            if random.random() > 0.50:  # 50% chance to keep as single message
                print(f"🔧 Keeping 50-100 char message as single")
                return [response]
        
        # 100-120 characters: 75% chance to split
        elif 100 < len(response) < 120:
            if random.random() > 0.75:  # 25% chance to keep as single message
                print(f"🔧 Keeping 100-120 char message as single (rare)")
                return [response]
        
        # 120+ characters: Always split somewhere
        print(f"🔧 Attempting to split message at punctuation...")
        
        # Split at natural punctuation marks in order of preference
        split_points = ['! ', '? ', '. ', ', and ', ', but ', ', so ', '; ', ': ', ', ']
        
        for split_point in split_points:
            if split_point in response:
                parts = []
                segments = response.split(split_point)
                current_part = ""
                
                for i, segment in enumerate(segments):
                    # Add the split point back (except for the last segment)
                    if i < len(segments) - 1:
                        segment += split_point.rstrip()
                    
                    # If adding this segment would make it too long, finalize current part
                    if len(current_part + segment) > 200 and current_part:
                        parts.append(current_part.strip())
                        current_part = segment
                    else:
                        current_part += segment
                
                # Add the final part
                if current_part:
                    parts.append(current_part.strip())
                
                # Only use this split if it actually created multiple meaningful parts
                if len(parts) > 1 and all(len(part.strip()) > 10 for part in parts):
                    # Limit to maximum 3 parts
                    if len(parts) > 3:
                        # Merge excess parts into the third part
                        merged_third = ' '.join(parts[2:])
                        parts = parts[:2] + [merged_third]
                    
                    print(f"🔧 Successfully split at '{split_point}' into {len(parts)} parts")
                    part_lengths = [len(part) for part in parts]
                    print(f"🔧 Split result: {len(parts)} parts - {part_lengths}")
                    return parts
        
        # If no good punctuation split point found but message is 120+, force split
        if len(response) >= 120:
            print(f"🔧 Force splitting long message at word boundaries...")
            words = response.split(' ')
            parts = []
            current_part = ""
            
            for word in words:
                if len(current_part + ' ' + word) > 200 and current_part:
                    parts.append(current_part.strip())
                    current_part = word
                else:
                    current_part += (' ' + word if current_part else word)
            
            if current_part:
                parts.append(current_part.strip())
            
            # Limit to maximum 3 parts
            if len(parts) > 3:
                merged_third = ' '.join(parts[2:])
                parts = parts[:2] + [merged_third]
            
            if len(parts) > 1:
                print(f"🔧 Force split by words into {len(parts)} parts")
                part_lengths = [len(part) for part in parts]
                print(f"🔧 Split result: {len(parts)} parts - {part_lengths}")
                return parts
        
        # If no good split point found, return as single message
        print(f"🔧 No good split point found, keeping as single message")
        return [response]

    async def _send_response_parts(self, message: discord.Message, response_parts: list, typing_delay: bool = True):
        """Send multiple response parts with human-like delays"""
        if not response_parts:
            return
        
        for i, part in enumerate(response_parts):
            if not part.strip():
                continue
            
            if typing_delay and i > 0:  # Add delay between parts (not for the first one)
                delay = await self._calculate_typing_delay(part)
                await asyncio.sleep(delay)
            
            try:
                await message.channel.send(part)
            except Exception as e:
                print(f"Error sending response part {i}: {e}")

    async def _calculate_typing_delay(self, text: str) -> float:
        import asyncio
        import random
        
        if not text:
            return 1.0
        
        # Base calculation: 80 WPM = ~400 characters per minute = ~6.67 characters per second
        base_chars_per_second = 6.67
        
        # Get Izumi's current mood and time personality from unified memory
        try:
            unified_memory = self.bot.unified_memory
            mood_data = unified_memory.get_daily_mood()
            time_personality = unified_memory.get_time_personality()
        except Exception:
            # Fallback to basic calculation if mood system unavailable
            base_delay = len(text) / base_chars_per_second
            variance = random.uniform(0.8, 1.2)
            return max(1.0, min(8.0, base_delay * variance))
        
        # Mood affects typing speed multiplier
        mood_multipliers = {
            "energetic": 0.75,    # 25% faster - quick energetic typing
            "excited": 0.70,      # 30% faster - very quick when excited
            "playful": 0.85,      # 15% faster - still quick but thoughtful
            "thoughtful": 1.25,   # 25% slower - pauses to think
            "sleepy": 1.50        # 50% slower - tired and sluggish
        }
        
        mood_multiplier = mood_multipliers.get(mood_data['current_mood'], 1.0)
        
        # Time of day affects typing speed
        time_multipliers = {
            "high": 0.85,         # Morning energy - faster typing
            "medium-high": 0.95,  # Afternoon - slightly faster
            "medium": 1.1,        # Evening - slightly slower
            "low": 1.4            # Late night - much slower, tired
        }
        
        time_multiplier = time_multipliers.get(time_personality['energy'], 1.0)
        
        # Energy level fine-tuning (0.0-1.0 scale affects speed)
        energy_level = mood_data.get('energy_level', 0.6)
        energy_multiplier = 1.4 - (energy_level * 0.6)  # High energy = faster, low energy = slower
        
        # Calculate adjusted typing speed
        final_multiplier = mood_multiplier * time_multiplier * energy_multiplier
        adjusted_chars_per_second = base_chars_per_second / final_multiplier
        
        # Calculate base delay
        base_delay = len(text) / adjusted_chars_per_second
        
        # Add human variance (±20%) but preserve mood influence
        variance = random.uniform(0.85, 1.15)
        
        # Apply bounds: minimum 0.5s for very short messages, maximum 12s for long tired responses
        if mood_data['current_mood'] == 'sleepy' and time_personality['energy'] == 'low':
            # Very tired Izumi can take longer
            delay = max(0.8, min(15.0, base_delay * variance))
        elif mood_data['current_mood'] in ['excited', 'energetic']:
            # Excited/energetic Izumi has tighter bounds
            delay = max(0.5, min(6.0, base_delay * variance))
        else:
            # Normal bounds
            delay = max(0.7, min(10.0, base_delay * variance))
        
        return delay
    
    async def _type_with_delay(self, channel, text: str):
        """Show typing indicator for human-like duration based on message length and mood"""
        import random
        
        delay = await self._calculate_typing_delay(text)
        
        # Get current mood for typing behavior variations
        try:
            mood_data = self.bot.unified_memory.get_daily_mood()
            current_mood = mood_data['current_mood']
        except Exception:
            current_mood = 'playful'  # Default fallback
        
        async with channel.typing():
            # Different typing patterns based on mood
            if current_mood == 'sleepy' and delay > 8:
                # Sleepy Izumi might pause mid-typing
                await asyncio.sleep(delay * 0.6)
                # Brief pause (like she dozed off for a second)
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await asyncio.sleep(delay * 0.4)
            elif current_mood == 'thoughtful' and delay > 5:
                # Thoughtful Izumi has deliberate pauses
                await asyncio.sleep(delay * 0.7)
                await asyncio.sleep(random.uniform(0.3, 0.8))  # Thinking pause
                await asyncio.sleep(delay * 0.3)
            elif current_mood in ['excited', 'energetic'] and len(text) > 50:
                # Excited typing - quick bursts
                await asyncio.sleep(delay * 0.8)
                await asyncio.sleep(random.uniform(0.1, 0.3))  # Quick breath
                await asyncio.sleep(delay * 0.2)
            else:
                # Normal steady typing
                await asyncio.sleep(delay)
    
    async def _generate_response_with_fallback(self, user_id: int, channel_id: int, prompt: str, original_message: str, username: str = None) -> Optional[str]:
        """Generate response with model fallback and error handling using shared channel context"""
        
        # Track API usage
        self.daily_api_calls += 1
        
        # Clear cache daily to prevent memory buildup
        current_time = time.time()
        if current_time - self.last_cache_clear > 86400:  # 24 hours
            self.response_cache.clear()
            self.api_call_log.clear()
            self.daily_api_calls = 0
            self.daily_quick_responses = 0
            self.last_cache_clear = current_time
            print(f"🔄 Daily cache cleared. API calls and quick responses reset.")
        
        # Log this API call
        self.api_call_log.append({
            'timestamp': current_time,
            'user_id': user_id,
            'channel_id': channel_id,
            'prompt_length': len(prompt)
        })
        
        # Keep only last 1000 API calls in log to prevent memory issues
        if len(self.api_call_log) > 1000:
            self.api_call_log = self.api_call_log[-1000:]
        
        print(f"📊 API Call #{self.daily_api_calls} | Quick Responses: {self.daily_quick_responses}")
        
        session_data = self._get_or_create_session(channel_id)
        
        # Get personality enhancements
        mood_data = self.learning_engine.get_daily_mood()
        time_personality = self.learning_engine.get_time_personality()
        
        # Create enhanced user-aware prompt for shared conversation
        enhanced_prompt = self._enhance_prompt_with_personality(prompt, original_message, username, mood_data, time_personality)
        
        if username:
            user_aware_prompt = f"[User: {username}] {enhanced_prompt}"
        else:
            user_aware_prompt = f"[User ID: {user_id}] {enhanced_prompt}"
        
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
                response = await chat.send_message_async(user_aware_prompt)
                raw_response = response.text
                
                # Apply personality quirks and enhancements
                context_type = self._determine_context_type(original_message, raw_response)
                enhanced_response = self._apply_personality_quirks(raw_response, mood_data, context_type)
                
                return enhanced_response
                
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
    
    def _get_or_create_session(self, channel_id: int) -> Dict:
        """Get or create chat session for channel (shared by all users)"""
        if channel_id not in self.gemini_chat_sessions:
            self.gemini_chat_sessions[channel_id] = {
                "chat": None,
                "model_index": 0,
                "message_count": 0,
                "created_at": time.time()
            }
        
        session = self.gemini_chat_sessions[channel_id]
        
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
                print(f"Reset chat session for channel {channel_id} (hit message limit)")
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
    
    def _enhance_prompt_with_personality(self, prompt: str, original_message: str, username: str, mood_data: dict, time_personality: dict) -> str:
        """Enhance the prompt with current personality state and behavioral guidance"""
        enhancement_parts = []
        
        # Add mood context
        mood_desc = mood_data.get('mood_description', 'feeling normal')
        energy_level = mood_data.get('energy_level', 0.5)
        enhancement_parts.append(f"You are currently {mood_desc}")
        
        # Add time-based personality guidance
        time_style = time_personality.get('style', 'casual')
        greeting_options = time_personality.get('greeting_style', ['hey!'])
        enhancement_parts.append(f"Your current style should be {time_style}")
        
        # Add energy-based response guidance
        if energy_level > 0.8:
            enhancement_parts.append("Respond with high energy and enthusiasm")
        elif energy_level > 0.6:
            enhancement_parts.append("Respond with moderate energy and friendliness")
        elif energy_level > 0.3:
            enhancement_parts.append("Respond calmly and thoughtfully")
        else:
            enhancement_parts.append("Respond quietly and more subdued")
        
        # Add behavioral personality context
        enhancement_parts.append("Remember to use your natural speech patterns and occasional personality quirks")
        
        enhanced_prompt = f"{prompt}\n\nPERSONALITY CONTEXT: {' | '.join(enhancement_parts)}"
        return enhanced_prompt
    
    def _apply_personality_quirks(self, response_text: str, mood_data: dict, context_type: str = "general") -> str:
        """Apply personality quirks and speech patterns to the response"""
        if not response_text:
            return response_text
        
        # Get quirk decision
        quirk_decision = self.learning_engine.should_use_quirk(context_type, mood_data)
        
        if quirk_decision.get("use_quirk", False):
            quirk_content = quirk_decision.get("quirk_content", "")
            quirk_type = quirk_decision.get("quirk_type", "")
            
            if quirk_content and quirk_type:
                # Apply quirk based on type
                if quirk_type == "thinking":
                    response_text = f"{quirk_content} {response_text}"
                elif quirk_type == "enthusiasm":
                    response_text = f"{response_text} {quirk_content}"
                elif quirk_type == "agreement":
                    response_text = f"{quirk_content} {response_text}"
                elif quirk_type == "favorite_phrase":
                    # Sometimes add to end, sometimes replace simple acknowledgments
                    if len(response_text.split()) <= 3:
                        response_text = quirk_content
                    else:
                        response_text = f"{response_text} {quirk_content}"
        
        # Apply occasional typos (very rarely)
        import random
        if random.random() < 0.05:  # 5% chance
            response_text = self._apply_occasional_typo(response_text)
        
        return response_text
    
    def _apply_occasional_typo(self, text: str) -> str:
        """Occasionally add realistic typos that get corrected"""
        quirks = self.learning_engine.get_personality_quirks()
        typos = quirks.get("typing_habits", {}).get("occasional_typos", {})
        
        import random
        if typos and random.random() < 0.3:  # 30% chance when this method is called
            typo_word = random.choice(list(typos.keys()))
            correct_word = typos[typo_word]
            
            if correct_word.lower() in text.lower():
                # Make the typo then correct it
                text_with_typo = text.replace(correct_word, typo_word)
                return f"{text_with_typo}\\n*{correct_word}"
        
        return text
    
    def _determine_context_type(self, original_message: str, response_text: str) -> str:
        """Determine the context type for quirk selection"""
        message_lower = original_message.lower()
        response_lower = response_text.lower()
        
        # Check for agreement context
        if any(word in response_lower for word in ["yes", "yeah", "exactly", "true", "agree", "right"]):
            return "agreement"
        
        # Check for enthusiasm context
        if any(word in message_lower for word in ["awesome", "cool", "amazing", "wow", "excited"]):
            return "enthusiasm"
        
        # Check for thinking context
        if any(word in message_lower for word in ["think", "opinion", "what do you", "how do you"]):
            return "thinking"
        
        return "general"
    
    @commands.command(name='api_usage')
    @commands.has_permissions(administrator=True)
    async def api_usage(self, ctx):
        """Show API usage statistics and optimization info"""
        embed = discord.Embed(
            title="📊 API Usage & Optimization Stats",
            color=discord.Color.green()
        )
        
        # Calculate time since last reset
        time_since_reset = time.time() - self.last_cache_clear
        hours_since_reset = time_since_reset / 3600
        
        # API Usage Stats
        total_interactions = self.daily_api_calls + self.daily_quick_responses
        if total_interactions > 0:
            api_percentage = (self.daily_api_calls / total_interactions) * 100
            quick_percentage = (self.daily_quick_responses / total_interactions) * 100
        else:
            api_percentage = quick_percentage = 0
        
        embed.add_field(
            name="🔢 Daily Interactions",
            value=f"**{self.daily_api_calls}** API calls ({api_percentage:.1f}%)\n"
                  f"**{self.daily_quick_responses}** Quick responses ({quick_percentage:.1f}%)\n"
                  f"**{total_interactions}** Total interactions\n"
                  f"⏰ {hours_since_reset:.1f} hours since reset",
            inline=False
        )
        
        # Efficiency Stats
        if total_interactions > 0:
            api_savings = (self.daily_quick_responses / total_interactions) * 100
            embed.add_field(
                name="💰 API Savings",
                value=f"**{api_savings:.1f}%** of calls saved\n"
                      f"🎯 Quick responses working effectively",
                inline=True
            )
        
        # Cache Stats
        cache_size = len(self.response_cache)
        log_size = len(self.api_call_log)
        embed.add_field(
            name="💾 Cache & Logs",
            value=f"**{cache_size}** cached responses\n"
                  f"📝 **{log_size}** recent API calls logged\n"
                  f"🔄 Resets every 24 hours",
            inline=True
        )
        
        # Quick Response Stats (estimate based on patterns)
        quick_patterns = sum(len(data['patterns']) for data in self.quick_responses.values())
        embed.add_field(
            name="🚀 Quick Responses",
            value=f"**{quick_patterns}** patterns available\n"
                  f"💡 Saves ~60-80% API calls",
            inline=True
        )
        
        # Performance Info
        if self.daily_api_calls > 0:
            avg_calls_per_hour = self.daily_api_calls / max(hours_since_reset, 0.1)
            projected_daily = avg_calls_per_hour * 24
            
            embed.add_field(
                name="📈 Projections",
                value=f"**{avg_calls_per_hour:.1f}** calls/hour\n"
                      f"📊 ~{projected_daily:.0f} projected daily",
                inline=True
            )
        
        # Cache efficiency
        embed.add_field(
            name="⚡ Efficiency",
            value=f"🎯 Pattern matching: **Instant**\n"
                  f"🤖 API responses: **~2-5s**\n"
                  f"💰 Cost savings: **High**",
            inline=True
        )
        
        # Next reset time
        next_reset = self.last_cache_clear + 86400  # 24 hours
        next_reset_str = f"<t:{int(next_reset)}:R>"
        embed.add_field(
            name="🔄 Next Reset",
            value=f"{next_reset_str}",
            inline=True
        )
        
        embed.set_footer(text="Use this to monitor API usage and optimization effectiveness")
        await ctx.send(embed=embed)

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

    # Slash command versions of all prefix commands
    @app_commands.command(name="api_usage", description="Show API usage statistics and optimization info")
    @app_commands.describe()
    async def slash_api_usage(self, interaction: discord.Interaction):
        """Slash command version of api_usage"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command requires administrator permissions.", ephemeral=True)
            return
        
        # Use the same logic as the prefix command
        embed = discord.Embed(
            title="📊 API Usage & Optimization Stats",
            color=discord.Color.green()
        )
        
        # Calculate time since last reset
        time_since_reset = time.time() - self.last_cache_clear
        hours_since_reset = time_since_reset / 3600
        
        # API Usage Stats
        total_interactions = self.daily_api_calls + self.daily_quick_responses
        if total_interactions > 0:
            api_percentage = (self.daily_api_calls / total_interactions) * 100
            quick_percentage = (self.daily_quick_responses / total_interactions) * 100
        else:
            api_percentage = quick_percentage = 0
        
        embed.add_field(
            name="🔢 Daily Interactions",
            value=f"**{self.daily_api_calls}** API calls ({api_percentage:.1f}%)\n"
                  f"**{self.daily_quick_responses}** Quick responses ({quick_percentage:.1f}%)\n"
                  f"**{total_interactions}** Total interactions\n"
                  f"⏰ {hours_since_reset:.1f} hours since reset",
            inline=False
        )
        
        # Efficiency Stats
        if total_interactions > 0:
            api_savings = (self.daily_quick_responses / total_interactions) * 100
            embed.add_field(
                name="💰 API Savings",
                value=f"**{api_savings:.1f}%** of calls saved\n"
                      f"🎯 Quick responses working effectively",
                inline=True
            )
        
        # Cache Stats
        cache_size = len(self.response_cache)
        log_size = len(self.api_call_log)
        embed.add_field(
            name="💾 Cache & Logs",
            value=f"**{cache_size}** cached responses\n"
                  f"📝 **{log_size}** recent API calls logged\n"
                  f"🔄 Resets every 24 hours",
            inline=True
        )
        
        # Quick Response Stats
        quick_patterns = sum(len(data['patterns']) for data in self.quick_responses.values())
        embed.add_field(
            name="🚀 Quick Responses",
            value=f"**{quick_patterns}** patterns available\n"
                  f"💡 Saves ~60-80% API calls",
            inline=True
        )
        
        # Performance Info
        if self.daily_api_calls > 0:
            avg_calls_per_hour = self.daily_api_calls / max(hours_since_reset, 0.1)
            projected_daily = avg_calls_per_hour * 24
            
            embed.add_field(
                name="📈 Projections",
                value=f"**{avg_calls_per_hour:.1f}** calls/hour\n"
                      f"📊 ~{projected_daily:.0f} projected daily",
                inline=True
            )
        
        # Cache efficiency
        embed.add_field(
            name="⚡ Efficiency",
            value=f"🎯 Pattern matching: **Instant**\n"
                  f"🤖 API responses: **~2-5s**\n"
                  f"💰 Cost savings: **High**",
            inline=True
        )
        
        # Next reset time
        next_reset = self.last_cache_clear + 86400  # 24 hours
        next_reset_str = f"<t:{int(next_reset)}:R>"
        embed.add_field(
            name="🔄 Next Reset",
            value=f"{next_reset_str}",
            inline=True
        )
        
        embed.set_footer(text="Use this to monitor API usage and optimization effectiveness")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ai_stats", description="Show AI learning statistics")
    @app_commands.describe()
    async def slash_ai_stats(self, interaction: discord.Interaction):
        """Slash command version of ai_stats"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command requires administrator permissions.", ephemeral=True)
            return
        
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
            value=f"**{len(users_data)}** total users tracked\n"
                  f"**{vocab_users}** users with vocabulary data\n"
                  f"**{sentiment_users}** users with sentiment data\n"
                  f"**{relationship_users}** users with relationship data",
            inline=True
        )
        
        # Memory stats
        total_memories = memory_data.get('daily_memories', {})
        recent_memories = len([m for m in total_memories.values() if m.get('timestamp', 0) > time.time() - 604800])  # Last week
        
        embed.add_field(
            name="🧠 Memory System",
            value=f"**{len(total_memories)}** total daily memories\n"
                  f"**{recent_memories}** memories from last week\n"
                  f"**Active** unified memory system",
            inline=True
        )
        
        # Current mood
        try:
            current_mood = self.learning_engine.get_daily_mood()
            time_personality = self.learning_engine.get_time_personality()
            
            embed.add_field(
                name="🎭 Current State",
                value=f"**Mood:** {current_mood['current_mood'].title()}\n"
                      f"**Energy:** {time_personality['energy'].title()}\n"
                      f"**Time:** {time_personality['time_period']}\n"
                      f"**Level:** {current_mood.get('energy_level', 0.5):.1f}/1.0",
                inline=True
            )
        except Exception as e:
            embed.add_field(
                name="🎭 Current State",
                value="Unable to retrieve mood data",
                inline=True
            )
        
        embed.set_footer(text="Learning system continuously adapts to user interactions")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ai_context", description="Show context building information")
    @app_commands.describe()
    async def slash_ai_context(self, interaction: discord.Interaction):
        """Slash command version of ai_context"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command requires administrator permissions.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🧠 AI Context System",
            color=discord.Color.purple()
        )
        
        # Context builder stats
        try:
            context = self.context_builder.build_smart_context(
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                current_message="test context",
                channel_id=interaction.channel.id
            )
            
            context_length = len(context)
            
            embed.add_field(
                name="📝 Context Building",
                value=f"**{context_length}** characters in current context\n"
                      f"**Active** smart context system\n"
                      f"**Dynamic** personality integration",
                inline=True
            )
        except Exception as e:
            embed.add_field(
                name="📝 Context Building",
                value="Context system active but unable to generate sample",
                inline=True
            )
        
        # Session info
        active_sessions = len(self.gemini_chat_sessions)
        embed.add_field(
            name="💬 Active Sessions",
            value=f"**{active_sessions}** active chat sessions\n"
                  f"**{self.chat_history_limit}** message history limit per channel",
            inline=True
        )
        
        # Participation tracking
        active_channels = len(self.participation_tracker)
        embed.add_field(
            name="🎭 Conversation Tracking",
            value=f"**{active_channels}** channels being tracked\n"
                  f"**Smart** conversation participation\n"
                  f"**Context-aware** responses",
            inline=True
        )
        
        embed.set_footer(text="Context system builds comprehensive understanding for each interaction")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reset_chat", description="Reset chat session for a user")
    @app_commands.describe(user="The user whose chat session to reset (leave empty for yourself)")
    async def slash_reset_chat(self, interaction: discord.Interaction, user: discord.Member = None):
        """Slash command version of reset_chat"""
        if not user:
            user = interaction.user
        
        # Only allow users to reset their own session or admins to reset anyone's
        if user != interaction.user and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You can only reset your own chat session!", ephemeral=True)
            return
        
        if user.id in self.gemini_chat_sessions:
            del self.gemini_chat_sessions[user.id]
            await interaction.response.send_message(f"✅ Reset chat session for {user.display_name}")
        else:
            await interaction.response.send_message(f"No active chat session found for {user.display_name}")

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
