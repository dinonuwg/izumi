"""
Unified Memory System for Izumi AI
Combines user memories, self-memories, and learning data into a single cohesive system
"""

import time
import re
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple, Any
from utils.helpers import save_json, load_json
from utils.config import DATA_FOLDER
import os

class UnifiedMemorySystem:
    """Unified memory system that handles all memory-related functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.unified_data_file = os.path.join(DATA_FOLDER, "unified_memory.json")
        
        # Load or migrate data
        self.memory_data = self.load_or_migrate_data()
        
        # Recent message context storage
        self.recent_messages = {}  # {channel_id: [recent_messages]}
        self.context_message_limit = 50  # Last 50 messages for context
        
        # Auto-save tracking
        self.pending_saves = False
        
    def load_or_migrate_data(self) -> Dict:
        """Load unified data or migrate from old files"""
        unified_file = self.unified_data_file
        
        # Check if unified file exists
        if os.path.exists(unified_file):
            try:
                data = load_json(unified_file)
                if data and self._validate_unified_structure(data):
                    print("✅ Loaded unified memory system")
                    return data
            except Exception as e:
                print(f"Error loading unified memory: {e}")
        
        # Migrate from old files
        print("🔄 Migrating to unified memory system...")
        return self._migrate_old_data()
    
    def _validate_unified_structure(self, data: Dict) -> bool:
        """Validate that unified data has the correct structure"""
        required_keys = ['users', 'izumi_self', 'server_culture', 'system_info']
        return all(key in data for key in required_keys)
    
    def _migrate_old_data(self) -> Dict:
        """Migrate data from old separate files"""
        unified_data = {
            'users': {},  # All user-related data
            'izumi_self': {},  # Izumi's self-memories
            'server_culture': {},  # Server-wide learning data
            'system_info': {
                'version': '1.0',
                'migrated_at': int(time.time()),
                'last_updated': int(time.time())
            }
        }
        
        # Migrate user memories
        try:
            old_memories = load_json(os.path.join(DATA_FOLDER, "izumi_memories.json"))
            for user_id_str, user_data in old_memories.items():
                unified_data['users'][user_id_str] = {
                    'basic_info': {
                        'name': user_data.get('name', ''),
                        'nickname': user_data.get('nickname', ''),
                        'age': user_data.get('age', ''),
                        'birthday': user_data.get('birthday', ''),
                        'relationship_status': user_data.get('relationship_status', ''),
                    },
                    'personality': {
                        'interests': user_data.get('interests', []),
                        'dislikes': user_data.get('dislikes', []),
                        'personality_notes': user_data.get('personality_notes', []),
                        'conversation_style': user_data.get('conversation_style', ''),
                    },
                    'social': {
                        'trust_level': user_data.get('trust_level', 0),
                        'relationships': user_data.get('relationships', {}),
                        'shared_experiences': user_data.get('shared_experiences', {}),
                    },
                    'activity': {
                        'important_events': user_data.get('important_events', []),
                        'custom_notes': user_data.get('custom_notes', []),
                        'last_interaction': user_data.get('last_interaction', 0),
                    },
                    'learning_data': {
                        'vocabulary_trends': {},
                        'communication_style': {},
                        'sentiment_patterns': {},
                        'topic_interests': {},
                        'activity_patterns': {},
                        'relationship_networks': {},
                    }
                }
            print(f"✅ Migrated {len(old_memories)} user memories")
        except FileNotFoundError:
            print("📝 No existing user memories to migrate")
        except Exception as e:
            print(f"⚠️ Error migrating user memories: {e}")
        
        # Migrate Izumi's self-memories
        try:
            old_self = load_json(os.path.join(DATA_FOLDER, "izumi_self.json"))
            unified_data['izumi_self'] = {
                'personality_traits': old_self.get('personality_traits', []),
                'likes': old_self.get('likes', []),
                'dislikes': old_self.get('dislikes', []),
                'backstory': old_self.get('backstory', []),
                'goals': old_self.get('goals', []),
                'fears': old_self.get('fears', []),
                'hobbies': old_self.get('hobbies', []),
                'favorite_things': old_self.get('favorite_things', []),
                'pet_peeves': old_self.get('pet_peeves', []),
                'life_philosophy': old_self.get('life_philosophy', []),
                'memories': old_self.get('memories', []),
                'relationships': old_self.get('relationships', []),
                'skills': old_self.get('skills', []),
                'dreams': old_self.get('dreams', []),
                'quirks': old_self.get('quirks', []),
                'knowledge': old_self.get('knowledge', []),
            }
            print("✅ Migrated Izumi's self-memories")
        except FileNotFoundError:
            print("📝 No existing self-memories to migrate")
        except Exception as e:
            print(f"⚠️ Error migrating self-memories: {e}")
        
        # Migrate learning data
        try:
            old_learning = load_json(os.path.join(DATA_FOLDER, "learning_data.json"))
            
            # Merge learning data into user profiles
            for data_type in ['vocabulary_trends', 'communication_styles', 'message_sentiment', 'topic_interests', 'activity_patterns', 'relationship_networks']:
                if data_type in old_learning:
                    for user_id_str, user_learning_data in old_learning[data_type].items():
                        if user_id_str not in unified_data['users']:
                            unified_data['users'][user_id_str] = self._create_empty_user_profile()
                        
                        # Map learning data to unified structure
                        learning_key = data_type.replace('_styles', '_style').replace('_trends', '')
                        unified_data['users'][user_id_str]['learning_data'][learning_key] = user_learning_data
            
            # Server culture data
            unified_data['server_culture'] = old_learning.get('server_culture', {})
            
            print("✅ Migrated learning data")
        except FileNotFoundError:
            print("📝 No existing learning data to migrate")
        except Exception as e:
            print(f"⚠️ Error migrating learning data: {e}")
        
        # Save unified data
        self.save_unified_data(unified_data)
        print("🎉 Migration to unified memory system complete!")
        
        return unified_data
    
    def _create_empty_user_profile(self) -> Dict:
        """Create an empty user profile structure"""
        return {
            'basic_info': {
                'name': '', 'nickname': '', 'age': '', 'birthday': '', 'relationship_status': ''
            },
            'personality': {
                'interests': [], 'dislikes': [], 'personality_notes': [], 'conversation_style': ''
            },
            'social': {
                'trust_level': 0, 'relationships': {}, 'shared_experiences': {}
            },
            'activity': {
                'important_events': [], 'custom_notes': [], 'last_interaction': 0
            },
            'learning_data': {
                'vocabulary': {}, 'communication_style': {}, 'sentiment_patterns': {},
                'topic_interests': {}, 'activity_patterns': {}, 'relationship_networks': {}
            }
        }
    
    async def _update_dynamic_trust_level(self, user_id_str: str, content: str, timestamp):
        """Update trust level dynamically based on user behavior patterns"""
        import time
        
        user_data = self.memory_data['users'][user_id_str]
        current_trust = user_data['social']['trust_level']
        last_interaction = user_data['activity']['last_interaction']
        current_time = int(timestamp.timestamp())
        
        # Initialize trust change
        trust_change = 0
        
        # 1. TIME DECAY - Trust decreases over time without interaction
        if last_interaction > 0:
            days_since_last = (current_time - last_interaction) / 86400  # seconds to days
            
            if days_since_last > 30:  # More than 30 days
                trust_change -= 2
            elif days_since_last > 14:  # More than 2 weeks
                trust_change -= 1
            elif days_since_last > 7:  # More than 1 week
                trust_change -= 0.5
        
        # 2. MESSAGE ENGAGEMENT - Longer, thoughtful messages = more trust
        message_length = len(content.strip())
        if message_length > 100:  # Long thoughtful message
            trust_change += 0.3
        elif message_length > 50:  # Medium message
            trust_change += 0.2
        elif message_length > 10:  # Short but substantial
            trust_change += 0.1
        elif message_length <= 3:  # Very short message (like "ok", "lol")
            trust_change -= 0.1
        
        # 3. SENTIMENT ANALYSIS - Positive messages increase trust
        content_lower = content.lower()
        
        # Positive indicators
        positive_words = ['thanks', 'thank you', 'appreciate', 'love', 'great', 'awesome', 
                         'good', 'nice', 'please', 'sorry', 'help', 'wonderful', 'amazing']
        negative_words = ['hate', 'stupid', 'dumb', 'shut up', 'annoying', 'bad', 'terrible',
                         'awful', 'suck', 'worst', 'fuck', 'shit', 'damn']
        
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        if positive_count > negative_count:
            trust_change += 0.2 * positive_count
        elif negative_count > positive_count:
            trust_change -= 0.3 * negative_count
        
        # 4. CONSISTENCY BONUS - Regular interaction patterns
        learning_data = user_data.get('learning_data', {})
        activity_patterns = learning_data.get('activity_patterns', {})
        
        if activity_patterns.get('message_count', 0) > 10:  # Has history
            # Small bonus for consistent users
            trust_change += 0.1
        
        # 5. APPLY TRUST CHANGE with bounds checking
        new_trust = current_trust + trust_change
        new_trust = max(0, min(10, new_trust))  # Clamp between 0 and 10
        
        # Only update if there's a meaningful change
        if abs(new_trust - current_trust) >= 0.1:
            user_data['social']['trust_level'] = round(new_trust * 10) / 10  # Round to 1 decimal
            
            # Log significant trust changes for debugging
            if abs(trust_change) >= 0.5:
                print(f"Trust level change for {user_id_str}: {current_trust:.1f} → {new_trust:.1f} (Δ{trust_change:+.1f})")
    
    async def decay_inactive_trust_levels(self):
        """Decay trust levels for users who haven't been active recently"""
        import time
        current_time = int(time.time())
        decay_count = 0
        
        for user_id_str, user_data in self.memory_data['users'].items():
            last_interaction = user_data['activity']['last_interaction']
            current_trust = user_data['social']['trust_level']
            
            if last_interaction > 0 and current_trust > 0:
                days_inactive = (current_time - last_interaction) / 86400
                
                # Decay trust for long-term inactive users
                trust_decay = 0
                if days_inactive > 60:  # 2 months
                    trust_decay = 1.0
                elif days_inactive > 30:  # 1 month  
                    trust_decay = 0.5
                elif days_inactive > 14:  # 2 weeks
                    trust_decay = 0.2
                
                if trust_decay > 0:
                    new_trust = max(0, current_trust - trust_decay)
                    user_data['social']['trust_level'] = round(new_trust * 10) / 10
                    decay_count += 1
                    print(f"Decayed trust for inactive user {user_id_str}: {current_trust:.1f} → {new_trust:.1f} ({days_inactive:.0f} days inactive)")
        
        if decay_count > 0:
            self.pending_saves = True
            print(f"Decayed trust levels for {decay_count} inactive users")
    
    def is_conversation_participation_enabled(self, channel_id: int) -> bool:
        """Check if conversation participation is enabled for this channel"""
        channel_id_str = str(channel_id)
        return channel_id_str in self.memory_data.get('conversation_channels', {})
    
    def add_conversation_channel(self, channel_id: int, settings: dict = None):
        """Add a channel for conversation participation"""
        if 'conversation_channels' not in self.memory_data:
            self.memory_data['conversation_channels'] = {}
        
        default_settings = {
            'min_messages': 5,  # Minimum messages to trigger participation
            'time_window': 300,  # 5 minutes
            'min_users': 2,  # Minimum different users
            'participation_chance': 0.3,  # 30% chance to join
            'cooldown': 600,  # 10 minute cooldown between participations
            'last_participation': 0
        }
        
        if settings:
            default_settings.update(settings)
        
        self.memory_data['conversation_channels'][str(channel_id)] = default_settings
        self.pending_saves = True
    
    def remove_conversation_channel(self, channel_id: int):
        """Remove a channel from conversation participation"""
        channel_id_str = str(channel_id)
        if 'conversation_channels' in self.memory_data and channel_id_str in self.memory_data['conversation_channels']:
            del self.memory_data['conversation_channels'][channel_id_str]
            self.pending_saves = True
            return True
        return False
    
    def detect_active_conversation(self, channel_id: int) -> dict:
        """Detect if there's an active conversation Izumi should join"""
        import time
        
        channel_id_str = str(channel_id)
        
        # Check if channel is enabled for participation
        if not self.is_conversation_participation_enabled(channel_id):
            return {"should_participate": False, "reason": "channel_not_enabled"}
        
        settings = self.memory_data['conversation_channels'][channel_id_str]
        current_time = time.time()
        
        # Check cooldown
        if current_time - settings['last_participation'] < settings['cooldown']:
            return {"should_participate": False, "reason": "cooldown_active"}
        
        # Get recent messages from this channel
        recent_messages = []
        if hasattr(self, 'recent_messages') and channel_id in self.recent_messages:
            cutoff_time = current_time - settings['time_window']
            recent_messages = [
                msg for msg in self.recent_messages[channel_id]
                if msg.get('timestamp', 0) > cutoff_time and not msg.get('is_bot', False)
            ]
        
        # Analyze conversation activity
        if len(recent_messages) < settings['min_messages']:
            return {"should_participate": False, "reason": "not_enough_messages"}
        
        # Count unique users
        unique_users = set(msg.get('user_id') for msg in recent_messages)
        if len(unique_users) < settings['min_users']:
            return {"should_participate": False, "reason": "not_enough_users"}
        
        # Check if Izumi recently participated
        izumi_recent = any(
            msg.get('user_id') == self.bot.user.id 
            for msg in recent_messages[-3:]  # Last 3 messages
        )
        if izumi_recent:
            return {"should_participate": False, "reason": "recently_participated"}
        
        # Determine if should participate based on chance
        import random
        if random.random() < settings['participation_chance']:
            # Update last participation time
            settings['last_participation'] = current_time
            self.pending_saves = True
            
            return {
                "should_participate": True,
                "conversation_context": self._build_conversation_context(recent_messages),
                "participants": list(unique_users),
                "message_count": len(recent_messages)
            }
        
        return {"should_participate": False, "reason": "random_chance"}
    
    def _build_conversation_context(self, recent_messages: list) -> str:
        """Build context from recent conversation for Izumi to understand and join"""
        if not recent_messages:
            return ""
        
        # Sort messages by timestamp
        sorted_messages = sorted(recent_messages, key=lambda x: x.get('timestamp', 0))
        
        # Build conversation summary
        context_parts = ["[ACTIVE CONVERSATION CONTEXT]"]
        context_parts.append("Recent conversation flow:")
        
        for msg in sorted_messages[-20:]:  # Last 20 messages for better context
            user_name = msg.get('display_name', f"User{msg.get('user_id', 'Unknown')}")
            content = msg.get('content', '')[:150]  # Truncate long messages
            context_parts.append(f"{user_name}: {content}")
        
        context_parts.append("\n[INSTRUCTION] Join this conversation naturally. Reference what people are talking about and add meaningful input. Be casual and friendly.")
        
        return "\n".join(context_parts)
    
    def get_emotional_context(self, user_id: int, guild_id: int) -> dict:
        """Analyze user interaction patterns to generate emotional context for responses"""
        import time
        
        user_id_str = str(user_id)
        guild_id_str = str(guild_id)
        
        # Get Izumi's memory of last interaction
        if user_id_str not in self.memory_data['users']:
            return {"type": "new_user", "message": ""}
        
        user_data = self.memory_data['users'][user_id_str]
        last_izumi_interaction = user_data['activity']['last_interaction']
        current_time = int(time.time())
        
        # Get server activity from XP data
        xp_data = self.bot.xp_data
        guild_xp_data = xp_data.get(guild_id_str, {})
        user_xp_data = guild_xp_data.get(user_id_str, {})
        last_server_activity = user_xp_data.get('last_message_timestamp', 0)
        
        # Calculate time differences (in days)
        days_since_izumi = (current_time - last_izumi_interaction) / 86400 if last_izumi_interaction > 0 else 999
        days_since_server = (current_time - last_server_activity) / 86400 if last_server_activity > 0 else 999
        
        # Determine interaction pattern and emotional response
        if days_since_izumi > 30 and days_since_server > 30:
            # Both inactive - user completely gone
            return {
                "type": "completely_absent",
                "message": f"*eyes light up with excitement* {user_data['basic_info'].get('display_name', 'You')}!! You're back! I missed you so much... where have you been? It's been over a month! 🥺💕",
                "days_absent": int(min(days_since_izumi, days_since_server))
            }
        
        elif days_since_izumi > 14 and days_since_server < 3:
            # Active in server but ignoring Izumi
            return {
                "type": "being_ignored", 
                "message": f"Hmph! {user_data['basic_info'].get('display_name', 'You')}... I can see you chatting with others but you never talk to me anymore! 😤 It's been {int(days_since_izumi)} days... do you not like me? 🥺",
                "days_ignored": int(days_since_izumi)
            }
        
        elif days_since_izumi > 7 and days_since_server > 7:
            # Both somewhat inactive
            return {
                "type": "worried",
                "message": f"Oh! {user_data['basic_info'].get('display_name', 'You')}! I was getting worried about you... I haven't seen you around much lately. Are you okay? 😟💙",
                "days_absent": int(max(days_since_izumi, days_since_server))
            }
        
        elif days_since_izumi > 3 and days_since_server < 1:
            # Recently active but not talking to Izumi
            return {
                "type": "pouty",
                "message": f"{user_data['basic_info'].get('display_name', 'You')}! I saw you were here yesterday but you didn't say hi to me... 😞 Don't forget about me! 💔",
                "days_ignored": int(days_since_izumi)
            }
        
        elif days_since_izumi > 1 and days_since_izumi <= 3:
            # Short absence
            return {
                "type": "happy_return",
                "message": f"*perks up* Oh hi {user_data['basic_info'].get('display_name', 'You')}! Good to see you again~ 😊✨",
                "days_absent": int(days_since_izumi)
            }
        
        else:
            # Regular interaction
            return {"type": "normal", "message": ""}
    
    
    
    
    def save_memory(self):
        """Alias for save_unified_data for compatibility"""
        self.save_unified_data()

    def save_unified_data(self, data: Dict = None):
        """Save unified memory data"""
        if data is None:
            data = self.memory_data
        
        data['system_info']['last_updated'] = int(time.time())
        save_json(self.unified_data_file, data)
        self.pending_saves = False

    # ==================== BIRTHDAY PING SYSTEM ====================
    
    async def send_random_birthday_ping(self, bot):
        """Send random birthday pings throughout the 24-hour birthday period"""
        from datetime import datetime, timezone
        from utils.helpers import is_birthday_today_extended
        import random
        
        utc_now = datetime.now(timezone.utc)
        current_date = utc_now.strftime('%m-%d')
        
        # Check if we've sent a ping in the last 2 hours to avoid spam
        last_ping_key = f'last_birthday_ping_{current_date}'
        last_ping = self.memory_data.get(last_ping_key, 0)
        if last_ping and (utc_now.timestamp() - last_ping) < 7200:  # 2 hours cooldown
            return None
        
        birthday_users = []
        
        # Check bot's birthday data (primary source)
        if hasattr(bot, 'birthdays'):
            for user_id_str, birthday_data in bot.birthdays.items():
                if isinstance(birthday_data, dict):
                    month = birthday_data.get('month')
                    day = birthday_data.get('day')
                    year = birthday_data.get('year')
                    
                    if month and day and is_birthday_today_extended(month, day, year):
                        birthday_users.append({
                            'user_id': user_id_str,
                            'month': month,
                            'day': day,
                            'year': year
                        })
        
        # Also check unified memory (backup source)
        for user_id_str, user_data in self.memory_data.get('users', {}).items():
            basic_info = user_data.get('basic_info', {})
            if basic_info.get('birthday'):
                birthday_date = basic_info['birthday']
                if birthday_date == current_date:
                    # Add if not already found
                    if not any(u['user_id'] == user_id_str for u in birthday_users):
                        birthday_users.append({
                            'user_id': user_id_str,
                            'month': int(birthday_date.split('-')[0]),
                            'day': int(birthday_date.split('-')[1]),
                            'year': None
                        })
        
        if not birthday_users:
            return None
            
        # Pick a random birthday user
        chosen_user = random.choice(birthday_users)
        chosen_user_id = int(chosen_user['user_id'])
        
        # Find an appropriate channel (preferably where they're active)
        target_channel = await self._find_birthday_ping_channel(bot, chosen_user_id)
        if not target_channel:
            return None
            
        # Generate age-aware birthday messages
        user = bot.get_user(chosen_user_id)
        if not user:
            return None
            
        age_context = ""
        if chosen_user['year']:
            current_year = utc_now.year
            age = current_year - chosen_user['year']
            if age > 0:
                age_context = f" (turning {age})" if age < 100 else ""
        
        # Birthday messages with optional age context
        birthday_messages = [
            f"🎂 Hey {user.mention}! Hope you're having an amazing birthday{age_context}! ✨",
            f"🎉 Happy birthday {user.mention}! 🥳 Hope your special day is wonderful{age_context}!",
            f"✨ {user.mention}! It's your birthday{age_context}! 🎂 Hope you're celebrating properly! 🎉",
            f"🎈 Birthday vibes for {user.mention}! 🎂 Hope you're having the best day ever{age_context}!",
            f"🥳 {user.mention}! Another year older, another year more awesome{age_context}! Happy birthday! 🎂",
            f"🎊 {user.mention}! Hope your birthday{age_context} is filled with cake, fun, and everything you love! 🎂",
            f"🌟 Happy birthday {user.mention}! 🎂 May this year bring you lots of happiness{age_context}! ✨",
            f"🎂 {user.mention}! Sending you birthday wishes and virtual cake! 🍰 Hope it's amazing{age_context}!",
            f"🎉 It's {user.mention}'s special day{age_context}! 🎂 Hope you're surrounded by friends and cake! 🥳",
            f"🎈 {user.mention}! Another trip around the sun{age_context}! 🌟 Happy birthday! 🎂"
        ]
        
        try:
            message = random.choice(birthday_messages)
            await target_channel.send(message)
            
            # Log the ping time
            self.memory_data[last_ping_key] = utc_now.timestamp()
            self.pending_saves = True
            
            age_info = f" (age {age})" if chosen_user['year'] else ""
            return f"Sent birthday ping to {user.display_name}{age_info} in {target_channel.name}"
            
        except Exception as e:
            print(f"Error sending birthday ping: {e}")
            
        return None
    
    async def _find_birthday_ping_channel(self, bot, user_id):
        """Find the best channel to send a birthday ping"""
        # Priority 1: Channel where user has been recently active
        if hasattr(self, 'recent_messages'):
            for channel_id, messages in self.recent_messages.items():
                for msg in reversed(messages[-20:]):  # Recent messages
                    if msg.get('user_id') == user_id:
                        channel = bot.get_channel(channel_id)
                        if channel:
                            return channel
        
        # Priority 2: General/main channels
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:
                for channel in guild.text_channels:
                    if channel.name.lower() in ['general', 'main', 'chat', 'lounge', 'birthday']:
                        if channel.permissions_for(guild.me).send_messages:
                            return channel
                
                # Priority 3: First available channel with send permissions
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        return channel
        
        return None
    
    # ==================== USER MEMORY METHODS ====================
    
    def get_user_memories(self, user_id: int) -> Dict:
        """Get user memories in legacy format for compatibility"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.memory_data['users']:
            self.memory_data['users'][user_id_str] = self._create_empty_user_profile()
        
        user_data = self.memory_data['users'][user_id_str]
        
        # Return in legacy format for compatibility
        return {
            'name': user_data['basic_info']['name'],
            'nickname': user_data['basic_info']['nickname'],
            'age': user_data['basic_info']['age'],
            'birthday': user_data['basic_info']['birthday'],
            'relationship_status': user_data['basic_info']['relationship_status'],
            'interests': user_data['personality']['interests'].copy() if isinstance(user_data['personality']['interests'], list) else [],
            'dislikes': user_data['personality']['dislikes'].copy() if isinstance(user_data['personality']['dislikes'], list) else [],
            'personality_notes': user_data['personality']['personality_notes'].copy() if isinstance(user_data['personality']['personality_notes'], list) else [],
            'conversation_style': user_data['personality']['conversation_style'],
            'trust_level': user_data['social']['trust_level'],
            'relationships': user_data['social']['relationships'].copy() if isinstance(user_data['social']['relationships'], dict) else {},
            'shared_experiences': user_data['social']['shared_experiences'].copy() if isinstance(user_data['social']['shared_experiences'], dict) else {},
            'important_events': user_data['activity']['important_events'].copy() if isinstance(user_data['activity']['important_events'], list) else [],
            'custom_notes': user_data['activity']['custom_notes'].copy() if isinstance(user_data['activity']['custom_notes'], list) else [],
            'last_interaction': user_data['activity']['last_interaction'],
        }
    
    def update_user_memory(self, user_id: int, key: str, value, append: bool = False):
        """Update user memory"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.memory_data['users']:
            self.memory_data['users'][user_id_str] = self._create_empty_user_profile()
        
        user_data = self.memory_data['users'][user_id_str]
        
        # Map legacy keys to new structure
        key_mapping = {
            'name': ('basic_info', 'name'),
            'nickname': ('basic_info', 'nickname'),
            'age': ('basic_info', 'age'),
            'birthday': ('basic_info', 'birthday'),
            'relationship_status': ('basic_info', 'relationship_status'),
            'interests': ('personality', 'interests'),
            'dislikes': ('personality', 'dislikes'),
            'personality_notes': ('personality', 'personality_notes'),
            'conversation_style': ('personality', 'conversation_style'),
            'trust_level': ('social', 'trust_level'),
            'relationships': ('social', 'relationships'),
            'shared_experiences': ('social', 'shared_experiences'),
            'important_events': ('activity', 'important_events'),
            'custom_notes': ('activity', 'custom_notes'),
        }
        
        if key in key_mapping:
            section, field = key_mapping[key]
            
            if append and field in user_data[section]:
                if isinstance(user_data[section][field], list):
                    if value not in user_data[section][field]:
                        user_data[section][field].append(value)
                else:
                    user_data[section][field] = [user_data[section][field], value]
            else:
                user_data[section][field] = value
        
        # Update timestamp
        user_data['activity']['last_interaction'] = int(time.time())
        self.pending_saves = True
    
    def update_user_relationship(self, user1_id: int, user2_id: int, relationship: str):
        """Update relationship between two users"""
        user1_str = str(user1_id)
        user2_str = str(user2_id)
        
        if user1_str not in self.memory_data['users']:
            self.memory_data['users'][user1_str] = self._create_empty_user_profile()
        
        self.memory_data['users'][user1_str]['social']['relationships'][user2_str] = relationship
        self.memory_data['users'][user1_str]['activity']['last_interaction'] = int(time.time())
        
        # Also update in learning data
        if 'relationship_networks' not in self.memory_data['users'][user1_str]['learning_data']:
            self.memory_data['users'][user1_str]['learning_data']['relationship_networks'] = {}
        
        if 'relationship_strength' not in self.memory_data['users'][user1_str]['learning_data']['relationship_networks']:
            self.memory_data['users'][user1_str]['learning_data']['relationship_networks']['relationship_strength'] = {}
        
        # Set relationship strength based on type
        strength_map = {
            'friend': 8, 'best friend': 10, 'close friend': 9,
            'family': 10, 'sibling': 9, 'parent': 10, 'child': 10,
            'teammate': 6, 'colleague': 5, 'acquaintance': 3,
            'enemy': -5, 'rival': -2, 'ex': -3, 'crush': 8
        }
        strength = strength_map.get(relationship.lower(), 5)
        self.memory_data['users'][user1_str]['learning_data']['relationship_networks']['relationship_strength'][user2_str] = strength
        
        self.pending_saves = True
    
    def add_shared_experience(self, user1_id: int, user2_id: int, experience: str):
        """Add shared experience between two users"""
        user1_str = str(user1_id)
        user2_str = str(user2_id)
        
        for user_str in [user1_str, user2_str]:
            if user_str not in self.memory_data['users']:
                self.memory_data['users'][user_str] = self._create_empty_user_profile()
            
            other_str = user2_str if user_str == user1_str else user1_str
            if other_str not in self.memory_data['users'][user_str]['social']['shared_experiences']:
                self.memory_data['users'][user_str]['social']['shared_experiences'][other_str] = []
            
            self.memory_data['users'][user_str]['social']['shared_experiences'][other_str].append(experience)
            self.memory_data['users'][user_str]['activity']['last_interaction'] = int(time.time())
        
        self.pending_saves = True
    
    # ==================== IZUMI SELF MEMORY METHODS ====================
    
    def get_izumi_self_memories(self) -> Dict:
        """Get Izumi's self memories"""
        return self.memory_data['izumi_self']
    
    def update_izumi_self_memory(self, category: str, value: str, append: bool = False):
        """Update Izumi's self memory"""
        if category not in self.memory_data['izumi_self']:
            self.memory_data['izumi_self'][category] = []
        
        if append:
            if value not in self.memory_data['izumi_self'][category]:
                self.memory_data['izumi_self'][category].append(value)
        else:
            self.memory_data['izumi_self'][category] = value
        
        self.pending_saves = True
    
    # ==================== LEARNING SYSTEM METHODS ====================
    
    async def learn_from_message(self, message):
        """Extract maximum information from a single message"""
        if message.author.bot or not message.guild:
            return
            
        user_id = message.author.id
        user_id_str = str(user_id)
        guild_id = message.guild.id
        content = message.content
        timestamp = message.created_at
        
        # Ensure user exists in unified system
        if user_id_str not in self.memory_data['users']:
            self.memory_data['users'][user_id_str] = self._create_empty_user_profile()
        
        # Update basic Discord info (username/display name) for better recognition
        basic_info = self.memory_data['users'][user_id_str]['basic_info']
        if not basic_info.get('display_name') or basic_info.get('display_name') != message.author.display_name:
            basic_info['display_name'] = message.author.display_name
            basic_info['username'] = message.author.name
            self.pending_saves = True
        
        # Update last interaction time
        self.memory_data['users'][user_id_str]['activity']['last_interaction'] = int(timestamp.timestamp())
        
        # Dynamic trust level calculation
        await self._update_dynamic_trust_level(user_id_str, content, timestamp)
        
        self.pending_saves = True
        
        user_data = self.memory_data['users'][user_id_str]['learning_data']
        
        # Learn vocabulary and language patterns
        await self.learn_vocabulary_advanced(user_id_str, content, timestamp, user_data)
        
        # Learn relationships and interactions
        await self.learn_relationships_advanced(message, user_data)
        
        # Learn sentiment and emotional patterns
        await self.learn_sentiment_patterns(user_id_str, content, timestamp, user_data)
        
        # Learn communication style and personality
        await self.learn_communication_style(user_id_str, content, message, user_data)
        
        # Learn topic interests and preferences
        await self.learn_topic_interests(user_id_str, content, message.channel.id, user_data)
        
        # Learn activity and temporal patterns
        await self.learn_activity_patterns(user_id_str, guild_id, timestamp, user_data)
        
        # Learn server culture and dynamics
        await self.learn_server_culture_advanced(guild_id, content, user_id_str, timestamp)
        
        # Update user memories with learned insights
        await self.update_user_memories_from_learning(user_id_str)
        
        # Store recent messages for chat context (only non-bot messages)
        if not message.author.bot:
            await self.store_recent_message(message)
        
        self.pending_saves = True
    
    async def learn_vocabulary_advanced(self, user_id_str: str, content: str, timestamp: datetime, user_data: Dict):
        """Learn advanced vocabulary patterns"""
        if 'vocabulary' not in user_data:
            user_data['vocabulary'] = {}
        
        vocab = user_data['vocabulary']
        
        # Initialize all required keys if they don't exist
        if 'word_frequency' not in vocab:
            vocab['word_frequency'] = {}
        if 'phrase_patterns' not in vocab:
            vocab['phrase_patterns'] = {}
        if 'slang_evolution' not in vocab:
            vocab['slang_evolution'] = []
        if 'emoji_usage' not in vocab:
            vocab['emoji_usage'] = {}
        if 'message_lengths' not in vocab:
            vocab['message_lengths'] = []
        if 'punctuation_style' not in vocab:
            vocab['punctuation_style'] = {}
        if 'capitalization_patterns' not in vocab:
            vocab['capitalization_patterns'] = {}
        if 'question_patterns' not in vocab:
            vocab['question_patterns'] = []
        if 'exclamation_patterns' not in vocab:
            vocab['exclamation_patterns'] = []
        if 'unique_expressions' not in vocab:
            vocab['unique_expressions'] = []
        
        content_lower = content.lower()
        
        # Advanced word frequency with context
        words = re.findall(r'\b\w+\b', content_lower)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        
        for word in words:
            if len(word) > 2 and word not in stop_words:
                vocab['word_frequency'][word] = vocab['word_frequency'].get(word, 0) + 1
        
        # Emoji analysis
        emoji_pattern = r'[😀-🿿]|:[a-zA-Z0-9_+-]+:'
        emojis = re.findall(emoji_pattern, content)
        for emoji in emojis:
            vocab['emoji_usage'][emoji] = vocab['emoji_usage'].get(emoji, 0) + 1
        
        # Message length tracking
        vocab['message_lengths'].append(len(content))
        vocab['message_lengths'] = vocab['message_lengths'][-100:]  # Keep recent
        
        # Question and exclamation patterns
        if '?' in content:
            vocab['question_patterns'].append(content[:100])
            vocab['question_patterns'] = vocab['question_patterns'][-20:]
        if '!' in content:
            vocab['exclamation_patterns'].append(content[:100])
            vocab['exclamation_patterns'] = vocab['exclamation_patterns'][-20:]
        
        # Keep data manageable
        self._trim_vocabulary_data(vocab)
    
    async def learn_relationships_advanced(self, message, user_data: Dict):
        """Learn complex relationship patterns"""
        if 'relationship_networks' not in user_data:
            user_data['relationship_networks'] = {}
        
        relations = user_data['relationship_networks']
        
        # Initialize all required keys if they don't exist
        if 'mention_frequency' not in relations:
            relations['mention_frequency'] = {}
        if 'reply_frequency' not in relations:
            relations['reply_frequency'] = {}
        if 'shared_channels' not in relations:
            relations['shared_channels'] = {}
        if 'interaction_times' not in relations:
            relations['interaction_times'] = {}
        if 'relationship_strength' not in relations:
            relations['relationship_strength'] = {}
        
        # Mention analysis
        for mentioned_user in message.mentions:
            if mentioned_user.id != message.author.id and not mentioned_user.bot:
                mentioned_id_str = str(mentioned_user.id)
                relations['mention_frequency'][mentioned_id_str] = relations['mention_frequency'].get(mentioned_id_str, 0) + 1
        
        # Channel sharing analysis
        channel_id_str = str(message.channel.id)
        relations['shared_channels'][channel_id_str] = relations['shared_channels'].get(channel_id_str, 0) + 1
        
        # Interaction timing
        hour = message.created_at.hour
        relations['interaction_times'][str(hour)] = relations['interaction_times'].get(str(hour), 0) + 1
    
    async def learn_sentiment_patterns(self, user_id_str: str, content: str, timestamp: datetime, user_data: Dict):
        """Learn emotional patterns and sentiment"""
        if 'sentiment_patterns' not in user_data:
            user_data['sentiment_patterns'] = {}
        
        sentiment = user_data['sentiment_patterns']
        
        # Initialize all required keys if they don't exist
        if 'positive_indicators' not in sentiment:
            sentiment['positive_indicators'] = 0
        if 'negative_indicators' not in sentiment:
            sentiment['negative_indicators'] = 0
        if 'humor_usage' not in sentiment:
            sentiment['humor_usage'] = 0
        if 'excitement_level' not in sentiment:
            sentiment['excitement_level'] = []
        if 'mood_patterns' not in sentiment:
            sentiment['mood_patterns'] = []
        
        content_lower = content.lower()
        
        # Sentiment analysis
        positive_words = ['great', 'awesome', 'love', 'amazing', 'good', 'nice', 'cool', 'best', 'happy', 'excited', 'thank', 'thanks']
        negative_words = ['bad', 'hate', 'worst', 'awful', 'terrible', 'annoying', 'frustrated', 'angry', 'sad', 'disappointed']
        humor_words = ['lol', 'lmao', 'haha', 'funny', 'joke', 'meme']
        
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        humor_count = sum(1 for word in humor_words if word in content_lower)
        
        sentiment['positive_indicators'] += positive_count
        sentiment['negative_indicators'] += negative_count
        sentiment['humor_usage'] += humor_count
        
        # Excitement detection
        excitement_score = 0
        if content.isupper() and len(content) > 3:
            excitement_score += 2
        excitement_score += content.count('!') * 0.5
        excitement_score += len(re.findall(r'[😀-🿿]', content)) * 0.3
        
        sentiment['excitement_level'].append(excitement_score)
        sentiment['excitement_level'] = sentiment['excitement_level'][-50:]  # Keep recent
        
        # Mood tracking
        current_time = int(timestamp.timestamp())
        sentiment['mood_patterns'].append({
            'timestamp': current_time,
            'positive': positive_count,
            'negative': negative_count,
            'excitement': excitement_score
        })
        sentiment['mood_patterns'] = sentiment['mood_patterns'][-50:]  # Keep recent
    
    async def learn_communication_style(self, user_id_str: str, content: str, message, user_data: Dict):
        """Learn individual communication styles"""
        if 'communication_style' not in user_data:
            user_data['communication_style'] = {}
        
        style = user_data['communication_style']
        
        # Initialize all required keys if they don't exist
        if 'formality_level' not in style:
            style['formality_level'] = 0
        if 'verbosity_preference' not in style:
            style['verbosity_preference'] = []
        if 'emoji_frequency' not in style:
            style['emoji_frequency'] = 0
        if 'greeting_style' not in style:
            style['greeting_style'] = []
        if 'farewell_style' not in style:
            style['farewell_style'] = []
        
        content_lower = content.lower()
        
        # Formality detection
        formal_indicators = ['please', 'thank you', 'could you', 'would you', 'excuse me']
        informal_indicators = ['yo', 'hey', 'sup', 'gonna', 'wanna', 'yeah', 'nah']
        
        formal_count = sum(1 for indicator in formal_indicators if indicator in content_lower)
        informal_count = sum(1 for indicator in informal_indicators if indicator in content_lower)
        
        if formal_count > informal_count:
            style['formality_level'] += 1
        elif informal_count > formal_count:
            style['formality_level'] -= 1
        
        # Verbosity tracking
        word_count = len(content.split())
        style['verbosity_preference'].append(word_count)
        style['verbosity_preference'] = style['verbosity_preference'][-50:]  # Keep recent
        
        # Emoji usage
        emoji_count = len(re.findall(r'[😀-🿿]|:[a-zA-Z0-9_+-]+:', content))
        style['emoji_frequency'] += emoji_count
        
        # Greeting detection
        greetings = ['hello', 'hi', 'hey', 'yo', 'sup', 'good morning', 'good evening']
        for greeting in greetings:
            if greeting in content_lower:
                style['greeting_style'].append(greeting)
                style['greeting_style'] = style['greeting_style'][-10:]  # Keep recent
    
    async def learn_topic_interests(self, user_id_str: str, content: str, channel_id: int, user_data: Dict):
        """Learn what topics users are interested in"""
        if 'topic_interests' not in user_data:
            user_data['topic_interests'] = {}
        
        interests = user_data['topic_interests']
        
        # Initialize all required keys if they don't exist
        if 'gaming_interests' not in interests:
            interests['gaming_interests'] = {}
        if 'tech_interests' not in interests:
            interests['tech_interests'] = {}
        if 'entertainment_interests' not in interests:
            interests['entertainment_interests'] = {}
        if 'channel_preferences' not in interests:
            interests['channel_preferences'] = {}
        
        content_lower = content.lower()
        
        # Gaming interest detection
        gaming_keywords = ['osu', 'rhythm', 'fps', 'moba', 'mmo', 'indie', 'game', 'gaming']
        for keyword in gaming_keywords:
            if keyword in content_lower:
                interests['gaming_interests'][keyword] = interests['gaming_interests'].get(keyword, 0) + 1
        
        # Technology interests
        tech_keywords = ['programming', 'coding', 'python', 'javascript', 'ai', 'tech', 'software']
        for keyword in tech_keywords:
            if keyword in content_lower:
                interests['tech_interests'][keyword] = interests['tech_interests'].get(keyword, 0) + 1
        
        # Entertainment interests
        entertainment_keywords = ['anime', 'manga', 'movie', 'music', 'show', 'series']
        for keyword in entertainment_keywords:
            if keyword in content_lower:
                interests['entertainment_interests'][keyword] = interests['entertainment_interests'].get(keyword, 0) + 1
        
        # Channel preferences
        channel_id_str = str(channel_id)
        interests['channel_preferences'][channel_id_str] = interests['channel_preferences'].get(channel_id_str, 0) + 1
    
    async def learn_activity_patterns(self, user_id_str: str, guild_id: int, timestamp: datetime, user_data: Dict):
        """Learn when and how often users are active"""
        if 'activity_patterns' not in user_data:
            user_data['activity_patterns'] = {}
        
        activity = user_data['activity_patterns']
        
        # Initialize all required keys if they don't exist
        if 'hourly_activity' not in activity:
            activity['hourly_activity'] = [0] * 24
        if 'daily_activity' not in activity:
            activity['daily_activity'] = [0] * 7
        if 'monthly_activity' not in activity:
            activity['monthly_activity'] = [0] * 12
        if 'message_frequency' not in activity:
            activity['message_frequency'] = []
        
        # Record activity by hour, day, month
        activity['hourly_activity'][timestamp.hour] += 1
        activity['daily_activity'][timestamp.weekday()] += 1
        activity['monthly_activity'][timestamp.month - 1] += 1
        
        # Track message frequency over time
        current_time = int(timestamp.timestamp())
        activity['message_frequency'].append(current_time)
        
        # Keep only recent message timestamps (last 30 days)
        thirty_days_ago = current_time - (30 * 24 * 60 * 60)
        activity['message_frequency'] = [ts for ts in activity['message_frequency'] if ts > thirty_days_ago]
    
    async def learn_server_culture_advanced(self, guild_id: int, content: str, user_id_str: str, timestamp: datetime):
        """Learn comprehensive server culture"""
        guild_id_str = str(guild_id)
        
        if guild_id_str not in self.memory_data['server_culture']:
            self.memory_data['server_culture'][guild_id_str] = {
                'common_phrases': {}, 'recurring_topics': {}, 'trending_topics': {}
            }
        
        culture = self.memory_data['server_culture'][guild_id_str]
        content_lower = content.lower()
        
        # Track phrases that become popular
        if len(content.split()) <= 6:  # Short phrases only
            culture['common_phrases'][content_lower] = culture['common_phrases'].get(content_lower, 0) + 1
        
        # Simple topic extraction
        words = content_lower.split()
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            if len(phrase) > 5:
                culture['recurring_topics'][phrase] = culture['recurring_topics'].get(phrase, 0) + 1
        
        # Keep data manageable
        self._trim_culture_data(culture)
    
    async def update_user_memories_from_learning(self, user_id_str: str):
        """Update user memories with learned insights"""
        user_data = self.memory_data['users'][user_id_str]
        learning_data = user_data['learning_data']
        
        # Update interests from learning
        if 'topic_interests' in learning_data:
            interests = learning_data['topic_interests']
            current_interests = user_data['personality']['interests']
            
            # Add gaming interests
            if interests.get('gaming_interests'):
                for game_type, count in interests['gaming_interests'].items():
                    if count > 3 and game_type not in current_interests:
                        current_interests.append(f"{game_type} games")
            
            # Add tech interests
            if interests.get('tech_interests'):
                for tech, count in interests['tech_interests'].items():
                    if count > 3 and tech not in current_interests:
                        current_interests.append(tech)
        
        # Update personality notes from communication style
        if 'communication_style' in learning_data:
            style = learning_data['communication_style']
            personality_notes = user_data['personality']['personality_notes']
            
            # Formality assessment
            if style.get('formality_level', 0) > 5:
                if "speaks formally" not in personality_notes:
                    personality_notes.append("speaks formally")
            elif style.get('formality_level', 0) < -5:
                if "speaks casually" not in personality_notes:
                    personality_notes.append("speaks casually")
            
            # Verbosity assessment
            if style.get('verbosity_preference'):
                avg_length = sum(style['verbosity_preference']) / len(style['verbosity_preference'])
                if avg_length > 50 and "tends to write long messages" not in personality_notes:
                    personality_notes.append("tends to write long messages")
                elif avg_length < 10 and "prefers short messages" not in personality_notes:
                    personality_notes.append("prefers short messages")
        
        # Update personality from sentiment
        if 'sentiment_patterns' in learning_data:
            sentiment = learning_data['sentiment_patterns']
            personality_notes = user_data['personality']['personality_notes']
            
            total_sentiment = sentiment.get('positive_indicators', 0) + sentiment.get('negative_indicators', 0)
            if total_sentiment > 20:  # Enough data
                positive_ratio = sentiment.get('positive_indicators', 0) / total_sentiment
                if positive_ratio > 0.7 and "generally positive and upbeat" not in personality_notes:
                    personality_notes.append("generally positive and upbeat")
                elif positive_ratio < 0.3 and "tends to be critical or negative" not in personality_notes:
                    personality_notes.append("tends to be critical or negative")
    
    def _trim_vocabulary_data(self, vocab: Dict):
        """Keep vocabulary data manageable"""
        # Trim word frequency to top 50
        if len(vocab['word_frequency']) > 50:
            sorted_words = sorted(vocab['word_frequency'].items(), key=lambda x: x[1], reverse=True)
            vocab['word_frequency'] = dict(sorted_words[:50])
        
        # Trim emoji usage to top 20
        if len(vocab['emoji_usage']) > 20:
            sorted_emojis = sorted(vocab['emoji_usage'].items(), key=lambda x: x[1], reverse=True)
            vocab['emoji_usage'] = dict(sorted_emojis[:20])
    
    def _trim_culture_data(self, culture: Dict):
        """Keep server culture data manageable"""
        # Keep top common phrases
        if len(culture['common_phrases']) > 30:
            sorted_phrases = sorted(culture['common_phrases'].items(), key=lambda x: x[1], reverse=True)
            culture['common_phrases'] = dict(sorted_phrases[:30])
        
        # Keep top recurring topics
        if len(culture['recurring_topics']) > 50:
            sorted_topics = sorted(culture['recurring_topics'].items(), key=lambda x: x[1], reverse=True)
            culture['recurring_topics'] = dict(sorted_topics[:50])
    
    # ==================== CONTEXT METHODS ====================
    
    def get_shared_context(self, user_id: int, guild_id: int = None, channel_id: int = None) -> str:
        """Get shared context for a user"""
        user_id_str = str(user_id)
        context_parts = []
        
        if user_id_str not in self.memory_data['users']:
            return ""
        
        user_data = self.memory_data['users'][user_id_str]
        
        # Get relationship data
        if 'relationship_networks' in user_data['learning_data']:
            relations = user_data['learning_data']['relationship_networks']
            
            # Most mentioned users
            if relations.get('mention_frequency'):
                top_mentions = sorted(relations['mention_frequency'].items(), key=lambda x: x[1], reverse=True)[:3]
                mention_users = []
                for mentioned_id_str, count in top_mentions:
                    try:
                        if guild_id:
                            guild = self.bot.get_guild(guild_id)
                            if guild:
                                user = guild.get_member(int(mentioned_id_str))
                                if user:
                                    mention_users.append(f"{user.display_name} ({count})")
                    except:
                        pass
                if mention_users:
                    context_parts.append(f"🗣️ Often mentions: {', '.join(mention_users)}")
        
        # Get social relationships
        if user_data['social']['relationships']:
            relationship_info = []
            for other_user_id_str, relationship in user_data['social']['relationships'].items():
                try:
                    if guild_id:
                        guild = self.bot.get_guild(guild_id)
                        if guild:
                            other_user = guild.get_member(int(other_user_id_str))
                            if other_user:
                                relationship_info.append(f"{other_user.display_name} ({relationship})")
                except:
                    continue
            
            if relationship_info:
                context_parts.append(f"👥 Relationships: {', '.join(relationship_info[:3])}")
        
        return "OTHER USERS CONTEXT: " + " | ".join(context_parts) if context_parts else ""
    
    # ==================== RECENT MESSAGE CONTEXT ====================
    
    async def store_recent_message(self, message):
        """Store recent messages for chat context and conversation detection"""
        channel_id = message.channel.id
        
        if not hasattr(self, 'recent_messages'):
            self.recent_messages = {}
        
        if channel_id not in self.recent_messages:
            self.recent_messages[channel_id] = []
        
        # Create message data for context and conversation detection
        message_data = {
            'user_id': message.author.id,
            'display_name': message.author.display_name,
            'content': message.content[:300],  # Limit content length
            'timestamp': message.created_at.timestamp(),
            'is_bot': message.author.bot,
            'mentions_bot': hasattr(self.bot, 'user') and self.bot.user in message.mentions,
            'has_attachments': len(message.attachments) > 0,
            'channel_id': channel_id,
            # Legacy fields for backwards compatibility
            'author_id': message.author.id,
            'author_name': message.author.display_name
        }
        
        self.recent_messages[channel_id].append(message_data)
        
        # Keep only the most recent messages (50 per channel)
        if len(self.recent_messages[channel_id]) > 50:
            self.recent_messages[channel_id] = self.recent_messages[channel_id][-50:]
        if len(self.recent_messages[channel_id]) > self.context_message_limit:
            self.recent_messages[channel_id] = self.recent_messages[channel_id][-self.context_message_limit:]
    
    def get_recent_chat_context(self, channel_id: int, exclude_mentions: bool = True) -> str:
        """Get recent chat context for AI understanding"""
        if channel_id not in self.recent_messages:
            return ""
        
        messages = self.recent_messages[channel_id]
        
        # Filter out bot mentions if requested
        if exclude_mentions:
            messages = [msg for msg in messages if not msg['mentions_bot']]
        
        if not messages:
            return ""
        
        # Format context
        context_lines = []
        for msg in messages:
            author = msg['author_name']
            content = msg['content']
            
            # Clean up the content for context
            content = self._clean_message_for_context(content)
            
            if msg['has_attachments']:
                content += " [shared image/file]"
            
            context_lines.append(f"{author}: {content}")
        
        return "RECENT CHAT CONTEXT (what people were talking about before mentioning you):\n" + "\n".join(context_lines)
    
    def _clean_message_for_context(self, content: str) -> str:
        """Clean message content for context display"""
        import re
        
        # Remove bot mentions but keep user mentions readable
        content = re.sub(f'<@!?{self.bot.user.id}>', '[bot]', content)
        content = re.sub(r'<@!?(\d+)>', r'[user]', content)
        
        # Clean up excessive whitespace
        content = ' '.join(content.split())
        
        # Shorten URLs
        content = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '[link]', content)
        
        # Limit length
        if len(content) > 150:
            content = content[:147] + "..."
        
        return content
    
    # ==================== AUTO-SAVE ====================
    
    async def auto_save(self):
        """Auto-save if there are pending changes"""
        if self.pending_saves:
            self.save_unified_data()
            # print("💾 Auto-saved unified memory data")
    
    def search_users_by_name(self, search_name: str) -> Dict:
        """Search for users by name across all stored memories"""
        search_name_lower = search_name.lower().strip()
        matches = {}
        
        for user_id_str, user_data in self.memory_data.get('users', {}).items():
            # Check basic info for name matches
            basic_info = user_data.get('basic_info', {})
            
            # Check various name fields
            name_fields = ['name', 'nickname', 'display_name', 'username']
            for field in name_fields:
                stored_name = basic_info.get(field, '')
                if stored_name and search_name_lower in stored_name.lower():
                    if user_id_str not in matches:
                        matches[user_id_str] = {
                            'user_id': user_id_str,
                            'matched_field': field,
                            'matched_value': stored_name,
                            'basic_info': basic_info,
                            'personality': user_data.get('personality', {}),
                            'social': user_data.get('social', {}),
                            'last_interaction': user_data.get('activity', {}).get('last_interaction', 'Unknown')
                        }
                    break
        
        return matches
    
    def get_user_info_for_ai(self, user_id: int, guild_id: int = None) -> str:
        """Get comprehensive user information formatted for AI context"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.memory_data.get('users', {}):
            return f"No stored information about user {user_id}"
        
        user_data = self.memory_data['users'][user_id_str]
        memories = user_data.get('memories', {})
        learning_data = user_data.get('learning_data', {})
        
        info_parts = []
        
        # Basic information from memories
        if memories.get('name'):
            name_value = memories['name']
            if isinstance(name_value, list):
                info_parts.append(f"Name: {', '.join(name_value)}")
            else:
                info_parts.append(f"Name: {name_value}")
                
        if memories.get('personality'):
            personality_value = memories['personality']
            if isinstance(personality_value, list):
                info_parts.append(f"Personality: {', '.join(personality_value)}")
            else:
                info_parts.append(f"Personality: {personality_value}")
                
        if memories.get('interests'):
            interests_value = memories['interests']
            if isinstance(interests_value, list):
                info_parts.append(f"Interests: {', '.join(interests_value)}")
            else:
                info_parts.append(f"Interests: {interests_value}")
        
        # Add other memory categories
        for category, value in memories.items():
            if category not in ['name', 'personality', 'interests'] and value:
                if isinstance(value, list):
                    info_parts.append(f"{category.title()}: {', '.join(map(str, value))}")
                else:
                    info_parts.append(f"{category.title()}: {value}")
        
        # Get XP/level data from bot
        if guild_id and hasattr(self.bot, 'xp_data'):
            guild_id_str = str(guild_id)
            if guild_id_str in self.bot.xp_data and user_id_str in self.bot.xp_data[guild_id_str]:
                user_xp_data = self.bot.xp_data[guild_id_str][user_id_str]
                if isinstance(user_xp_data, dict):
                    if 'level' in user_xp_data:
                        info_parts.append(f"Level: {user_xp_data['level']}")
                    if 'xp' in user_xp_data:
                        info_parts.append(f"XP: {user_xp_data['xp']}")
                elif isinstance(user_xp_data, (int, float)):
                    level = user_xp_data // 100
                    info_parts.append(f"Level: {level}")
                    info_parts.append(f"XP: {user_xp_data}")
        
        # Get gacha data from bot (if available)
        if hasattr(self.bot, 'osu_gacha_data'):
            try:
                user_gacha = self.bot.osu_gacha_data.get(user_id_str, {})
                if user_gacha:
                    if 'coins' in user_gacha:
                        info_parts.append(f"Gacha Coins: {user_gacha['coins']}")
                    if 'cards' in user_gacha:
                        total_cards = len(user_gacha['cards'])
                        info_parts.append(f"Gacha Cards: {total_cards}")
                    if 'pack_count' in user_gacha:
                        info_parts.append(f"Packs Opened: {user_gacha['pack_count']}")
            except:
                pass  # Gacha data not available
        
        # Add learning data insights
        if learning_data:
            activity = learning_data.get('activity_patterns', {})
            if activity.get('message_count'):
                info_parts.append(f"Messages Sent: {activity['message_count']}")
            
            sentiment = learning_data.get('sentiment_patterns', {})
            if sentiment:
                total_msgs = sentiment.get('positive_count', 0) + sentiment.get('negative_count', 0) + sentiment.get('neutral_count', 0)
                if total_msgs > 0:
                    pos_pct = round((sentiment.get('positive_count', 0) / total_msgs) * 100)
                    info_parts.append(f"Positive Sentiment: {pos_pct}%")
        
        return " | ".join(info_parts) if info_parts else f"User {user_id} is known but no detailed information stored"

    # ===== PERSONALITY & MOOD SYSTEMS =====
    
    def get_daily_mood(self) -> dict:
        """Get Izumi's current mood based on interactions, time, and randomness"""
        import random
        from datetime import datetime, timezone
        
        # Use UTC time for consistency across timezones
        current_time = datetime.now(timezone.utc)
        hour = current_time.hour
        
        # Get recent interaction data
        recent_interactions = self._get_recent_interaction_count()
        daily_messages = self._get_daily_message_count()
        
        # Base mood probabilities
        mood_weights = {
            "energetic": 0.3,
            "playful": 0.25,
            "thoughtful": 0.2,
            "sleepy": 0.15,
            "excited": 0.1
        }
        
        # Time-based adjustments
        if 6 <= hour <= 10:  # Morning
            mood_weights["energetic"] += 0.3
            mood_weights["sleepy"] -= 0.1
        elif 11 <= hour <= 17:  # Afternoon
            mood_weights["playful"] += 0.2
            mood_weights["thoughtful"] += 0.1
        elif 18 <= hour <= 22:  # Evening
            mood_weights["thoughtful"] += 0.2
            mood_weights["playful"] += 0.1
        else:  # Late night
            mood_weights["sleepy"] += 0.4
            mood_weights["energetic"] -= 0.3
        
        # Interaction-based adjustments
        if recent_interactions > 10:
            mood_weights["excited"] += 0.2
            mood_weights["energetic"] += 0.1
        elif recent_interactions < 3:
            mood_weights["thoughtful"] += 0.15
            mood_weights["sleepy"] += 0.1
        
        # Normalize weights
        total_weight = sum(mood_weights.values())
        mood_weights = {k: max(0, v/total_weight) for k, v in mood_weights.items()}
        
        # Select mood based on weights
        rand = random.random()
        cumulative = 0
        selected_mood = "playful"  # default
        
        for mood, weight in mood_weights.items():
            cumulative += weight
            if rand <= cumulative:
                selected_mood = mood
                break
        
        # Calculate energy level (0.0 - 1.0)
        energy_base = {"energetic": 0.9, "playful": 0.7, "excited": 0.8, "thoughtful": 0.5, "sleepy": 0.2}
        energy_level = energy_base.get(selected_mood, 0.6)
        
        # Time adjustments for energy
        if hour < 6 or hour > 23:
            energy_level *= 0.3
        elif 6 <= hour <= 10:
            energy_level *= 1.2
        elif 18 <= hour <= 22:
            energy_level *= 0.8
        
        energy_level = min(1.0, max(0.1, energy_level))
        
        return {
            "current_mood": selected_mood,
            "energy_level": energy_level,
            "mood_description": self._get_mood_description(selected_mood, energy_level),
            "time_context": self._get_time_context(hour)
        }
    
    def _get_mood_description(self, mood: str, energy: float) -> str:
        """Get description of current mood for AI context"""
        descriptions = {
            "energetic": f"feeling very energetic and upbeat (energy: {energy:.1f})",
            "playful": f"in a playful, fun mood (energy: {energy:.1f})",
            "thoughtful": f"feeling contemplative and thoughtful (energy: {energy:.1f})",
            "sleepy": f"feeling a bit sleepy and relaxed (energy: {energy:.1f})",
            "excited": f"feeling excited and enthusiastic (energy: {energy:.1f})"
        }
        return descriptions.get(mood, f"in a {mood} mood (energy: {energy:.1f})")
    
    def get_time_personality(self) -> dict:
        """Get time-aware personality adjustments"""
        from datetime import datetime, timezone
        # Use UTC time for consistency
        hour = datetime.now(timezone.utc).hour
        
        if 6 <= hour <= 10:    # Morning
            return {
                "energy": "high",
                "style": "cheerful and bright",
                "greeting_style": ["morning!", "good morning!", "hey there!", "rise and shine!"],
                "personality_note": "naturally energetic and optimistic (it's morning in UTC)"
            }
        elif 11 <= hour <= 17: # Afternoon  
            return {
                "energy": "medium-high",
                "style": "casual and friendly",
                "greeting_style": ["hey!", "hey there!", "sup!", "hi!"],
                "personality_note": "relaxed and sociable (afternoon UTC time)"
            }
        elif 18 <= hour <= 22: # Evening
            return {
                "energy": "medium",
                "style": "cozy and warm",
                "greeting_style": ["good evening~", "evening!", "hey~", "hi there~"],
                "personality_note": "more relaxed and cozy (evening UTC time)"
            }
        else:                  # Late night
            return {
                "energy": "low",
                "style": "quiet and sleepy",
                "greeting_style": ["*yawn* hey...", "oh hi...", "hey there... *tired*", "sup... kinda tired"],
                "personality_note": "sleepy and more subdued (late night UTC)"
            }
    
    def _get_time_context(self, hour: int) -> str:
        """Get time context description"""
        if 6 <= hour <= 10:
            return "early morning energy"
        elif 11 <= hour <= 17:
            return "afternoon casual vibes"
        elif 18 <= hour <= 22:
            return "evening relaxation"
        else:
            return "late night sleepiness"
    
    def _get_recent_interaction_count(self) -> int:
        """Count interactions in the last 2 hours"""
        current_time = time.time()
        cutoff_time = current_time - (2 * 3600)  # 2 hours ago
        
        count = 0
        for user_data in self.memory_data.get('users', {}).values():
            last_interaction = user_data.get('activity', {}).get('last_interaction', 0)
            if last_interaction > cutoff_time:
                count += 1
        
        return count
    
    def _get_daily_message_count(self) -> int:
        """Count messages Izumi has seen today"""
        # This would need to be tracked separately, for now return estimate
        return self._get_recent_interaction_count() * 3
    
    def get_memory_recall_opportunities(self, user_id: int, current_topic: str = None) -> list:
        """Find past conversations to reference naturally"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.memory_data.get('users', {}):
            return []
        
        user_data = self.memory_data['users'][user_id_str]
        learning_data = user_data.get('learning_data', {})
        
        callbacks = []
        current_time = time.time()
        
        # Check for unfinished topics from recent conversations
        topic_interests = learning_data.get('topic_interests', {})
        for topic, data in topic_interests.items():
            last_mention = data.get('last_mentioned', 0)
            days_ago = (current_time - last_mention) / 86400
            
            if 1 <= days_ago <= 14:  # 1-14 days ago
                if days_ago <= 3:
                    callbacks.append(f"oh btw, how did that {topic} thing go that you mentioned?")
                elif days_ago <= 7:
                    callbacks.append(f"speaking of {topic}, didn't you say you were working on something with that?")
                else:
                    callbacks.append(f"this reminds me of when we talked about {topic} last week!")
        
        # Check for emotional follow-ups
        sentiment_data = learning_data.get('sentiment_patterns', {})
        recent_sentiments = sentiment_data.get('recent_emotions', [])
        
        for emotion_entry in recent_sentiments[-3:]:  # Last 3 emotional moments
            emotion_time = emotion_entry.get('timestamp', 0)
            emotion_type = emotion_entry.get('emotion', '')
            days_ago = (current_time - emotion_time) / 86400
            
            if 1 <= days_ago <= 7:  # Follow up within a week
                if emotion_type in ['stressed', 'worried', 'sad']:
                    callbacks.append("hey, how are you feeling today? you seemed stressed yesterday 💙")
                elif emotion_type in ['excited', 'happy']:
                    callbacks.append("you seemed really excited about something yesterday! how's it going?")
        
        # Check for milestone acknowledgments
        activity = user_data.get('activity', {})
        message_count = learning_data.get('activity_patterns', {}).get('message_count', 0)
        
        if message_count > 0 and message_count % 100 == 0:  # Every 100 messages
            callbacks.append(f"wow you've sent {message_count} messages! you're really active here!")
        
        return callbacks[:2]  # Return max 2 callbacks to avoid overwhelming
    
    def get_emotional_followups(self, user_id: int) -> list:
        """Generate follow-ups based on past emotional interactions"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.memory_data.get('users', {}):
            return []
        
        user_data = self.memory_data['users'][user_id_str]
        learning_data = user_data.get('learning_data', {})
        sentiment_data = learning_data.get('sentiment_patterns', {})
        recent_emotions = sentiment_data.get('recent_emotions', [])
        
        followups = []
        current_time = time.time()
        
        for emotion_entry in recent_emotions[-5:]:  # Check last 5 emotional interactions
            emotion_time = emotion_entry.get('timestamp', 0)
            emotion_type = emotion_entry.get('emotion', '')
            emotion_context = emotion_entry.get('context', '')
            hours_ago = (current_time - emotion_time) / 3600
            
            if 12 <= hours_ago <= 72:  # 12 hours to 3 days ago
                if emotion_type == 'stressed':
                    followups.append("how are you feeling today? you seemed really stressed before")
                elif emotion_type == 'excited' and 'project' in emotion_context.lower():
                    followups.append("how's that project going that you were excited about? 😊")
                elif emotion_type == 'sad':
                    followups.append("hope you're feeling better today 💙")
                elif emotion_type == 'worried':
                    followups.append("hey, how did that thing you were worried about turn out?")
        
        return followups[:1]  # Return max 1 followup to be subtle
    
    def check_server_events(self, guild_id: int) -> list:
        """Notice and celebrate server events"""
        events = []
        
        # Check for server activity milestones
        total_users = len(self.memory_data.get('users', {}))
        if total_users > 0 and total_users % 10 == 0:
            events.append(f"wow we have {total_users} people in our memory now! the server is growing! 🎉")
        
        # Check for high activity day
        recent_count = self._get_recent_interaction_count()
        if recent_count > 15:
            events.append("wow everyone's really active today! i love when the server is buzzing ✨")
        
        return events
    
    def generate_curiosity_questions(self, context: str, user_id: int = None) -> list:
        """Generate natural follow-up questions to keep conversations going"""
        questions = []
        context_lower = context.lower()
        
        # Topic-specific curiosity
        if any(word in context_lower for word in ['like', 'love', 'enjoy', 'favorite']):
            questions.extend([
                "ooh that's really interesting! how did you get into that?",
                "what's your favorite part about it?",
                "have you always been interested in that?",
                "tell me more about that!"
            ])
        
        if any(word in context_lower for word in ['working on', 'building', 'making', 'creating']):
            questions.extend([
                "that sounds so cool! what's it like working on that?",
                "how long have you been working on it?",
                "can you tell me more about the process?"
            ])
        
        if any(word in context_lower for word in ['learned', 'studying', 'school', 'class']):
            questions.extend([
                "that's awesome! is it hard to learn?",
                "what's the most interesting thing you've learned so far?",
                "are you enjoying it?"
            ])
        
        # General conversation extenders
        general_questions = [
            "that sounds really fun!",
            "i'd love to hear more about that!",
            "what made you decide to try that?",
            "that's so cool!",
            "how's that been going for you?"
        ]
        
        questions.extend(general_questions)
        
        return questions[:3]  # Return max 3 options
    
    def analyze_conversation_energy(self, recent_messages: list) -> dict:
        """Determine conversation energy and tone for appropriate responses"""
        if not recent_messages:
            return {"energy": "neutral", "tone": "casual", "recommendation": "normal"}
        
        # Analyze message content and frequency
        message_texts = [msg.get('content', '') for msg in recent_messages[-10:]]  # Last 10 messages
        combined_text = ' '.join(message_texts).lower()
        
        # Check for serious/heavy topics
        serious_keywords = ['problem', 'issue', 'worried', 'stressed', 'help', 'difficult', 'serious', 'important']
        if any(keyword in combined_text for keyword in serious_keywords):
            return {
                "energy": "low",
                "tone": "serious",
                "recommendation": "be thoughtful and supportive"
            }
        
        # Check for playful/fun energy
        playful_keywords = ['lol', 'haha', 'funny', 'joke', 'lmao', '😂', '🤣', 'fun', 'awesome', 'cool']
        playful_count = sum(1 for keyword in playful_keywords if keyword in combined_text)
        
        if playful_count >= 3:
            return {
                "energy": "high",
                "tone": "playful",
                "recommendation": "be energetic and join the fun"
            }
        
        # Check for argument/tension
        tension_keywords = ['disagree', 'wrong', 'actually', 'but', 'however', 'no way', "that's not"]
        if sum(1 for keyword in tension_keywords if keyword in combined_text) >= 2:
            return {
                "energy": "medium",
                "tone": "tense",
                "recommendation": "stay neutral or try to lighten mood"
            }
        
        # Default to casual
        return {
            "energy": "medium",
            "tone": "casual",
            "recommendation": "normal conversation"
        }
    
    def get_personality_quirks(self) -> dict:
        """Get Izumi's personality quirks and habits for consistent behavior"""
        return {
            "favorite_phrases": [
                "that's so cool!",
                "ooh interesting!",
                "wait really?",
                "no way!",
                "omg yes!",
                "fr fr",
                "that's awesome!",
                "i love that!",
                "yesss!"
            ],
            "typing_habits": {
                "occasional_typos": {"recieve": "receive", "definately": "definitely", "seperate": "separate"},
                "thinking_indicators": ["hmm...", "let me think...", "..."],
                "excitement_expressions": ["!!", "omg", "yess", "wooo"],
                "confusion_expressions": ["??", "wait what", "huh?", "confused"]
            },
            "topic_preferences": {
                "anime": {"excitement_level": 0.9, "emoji": "✨"},
                "gaming": {"excitement_level": 0.8, "emoji": "🎮"},
                "osu": {"excitement_level": 1.0, "emoji": "🎵"},
                "programming": {"excitement_level": 0.7, "emoji": "💻"},
                "art": {"excitement_level": 0.8, "emoji": "🎨"},
                "music": {"excitement_level": 0.9, "emoji": "🎶"}
            },
            "speech_patterns": {
                "agreement": ["exactly!", "yes!", "so true!", "fr!", "this!"],
                "disagreement": ["hmm not sure about that", "i think differently", "interesting perspective but..."],
                "thinking": ["lemme think...", "hmm...", "that's a good question..."],
                "enthusiasm": ["omg!", "yess!", "that's amazing!", "so cool!"]
            }
        }
    
    def should_use_quirk(self, context_type: str, mood: dict) -> dict:
        """Determine if and which personality quirk to use based on context and mood"""
        quirks = self.get_personality_quirks()
        energy_level = mood.get('energy_level', 0.5)
        current_mood = mood.get('current_mood', 'neutral')
        
        import random
        
        result = {"use_quirk": False, "quirk_type": None, "quirk_content": None}
        
        # Higher energy = more likely to use quirks
        quirk_chance = energy_level * 0.7  # 0-70% chance based on energy
        
        if random.random() < quirk_chance:
            result["use_quirk"] = True
            
            # Select quirk type based on context
            if context_type == "agreement" and random.random() < 0.8:
                result["quirk_type"] = "agreement"
                result["quirk_content"] = random.choice(quirks["speech_patterns"]["agreement"])
            elif context_type == "enthusiasm" and energy_level > 0.6:
                result["quirk_type"] = "enthusiasm" 
                result["quirk_content"] = random.choice(quirks["speech_patterns"]["enthusiasm"])
            elif context_type == "thinking" and random.random() < 0.3:
                result["quirk_type"] = "thinking"
                result["quirk_content"] = random.choice(quirks["speech_patterns"]["thinking"])
            elif context_type == "general" and random.random() < 0.4:
                result["quirk_type"] = "favorite_phrase"
                result["quirk_content"] = random.choice(quirks["favorite_phrases"])
        
        return result

    # --- PROACTIVE MESSAGE DELIVERY ---
    
    async def send_unprompted_message(self, bot, guild_id=None, channel_id=None):
        """Send proactive/unprompted messages to users"""
        try:
            # Find an appropriate channel to send to
            target_channel = None
            
            if channel_id:
                target_channel = bot.get_channel(channel_id)
            elif guild_id:
                guild = bot.get_guild(guild_id)
                if guild:
                    # Find a general chat channel
                    for channel in guild.text_channels:
                        if channel.name in ['general', 'chat', 'main', 'lounge']:
                            target_channel = channel
                            break
                    if not target_channel:
                        target_channel = guild.text_channels[0] if guild.text_channels else None
            else:
                # Find any available channel from recent activity
                if hasattr(self, 'recent_messages') and self.recent_messages:
                    recent_channel_id = list(self.recent_messages.keys())[0]
                    target_channel = bot.get_channel(int(recent_channel_id))
            
            if not target_channel:
                return None
                
            # Check if we should send an unprompted message
            should_send, message_type = self._should_send_unprompted_message(target_channel.id)
            if not should_send:
                return None
                
            # Generate the appropriate message
            message_content = None
            if message_type == "emotional_followup":
                # Get users we have emotional followups for
                for user_id in self.memory_data.get('users', {}):
                    followups = self.get_emotional_followups(int(user_id))
                    if followups:
                        user = bot.get_user(int(user_id))
                        if user:
                            message_content = f"*thinking about earlier* {followups[0]}"
                            break
                            
            elif message_type == "server_event":
                events = self.check_server_events(target_channel.guild.id if target_channel.guild else 0)
                if events:
                    message_content = f"*notices* {events[0]} 🎉"
                    
            elif message_type == "curiosity":
                # Generate a general curiosity question
                questions = self.generate_curiosity_questions("", 0)  # General context
                if questions:
                    message_content = f"*wonders* {questions[0]}"
                    
            elif message_type == "mood_share":
                mood_data = self.get_daily_mood()
                if mood_data['energy'] >= 7:
                    message_content = f"*{mood_data['mood_description']}* {mood_data['time_context']} ✨"
                    
            if message_content:
                await target_channel.send(message_content)
                self._log_unprompted_message(target_channel.id, message_type)
                return message_content
                
        except Exception as e:
            print(f"Error sending unprompted message: {e}")
            
        return None
    
    def _should_send_unprompted_message(self, channel_id):
        """Determine if and what type of unprompted message to send"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        # Check last unprompted message time to avoid spam
        last_unprompted = self.memory_data.get('last_unprompted', {}).get(str(channel_id), 0)
        if last_unprompted and (now.timestamp() - last_unprompted) < 3600:  # 1 hour cooldown
            return False, None
            
        # Check if there are emotional followups pending
        for user_id in self.memory_data.get('users', {}):
            if self.get_emotional_followups(int(user_id)):
                return True, "emotional_followup"
        
        # Check for server events
        if self.check_server_events(0):  # General check
            return True, "server_event"
            
        # Random curiosity (low chance)
        import random
        if random.random() < 0.1:  # 10% chance
            return True, "curiosity"
            
        # Mood sharing if very energetic
        mood_data = self.get_daily_mood()
        if mood_data['energy'] >= 8 and random.random() < 0.2:  # 20% chance when very energetic
            return True, "mood_share"
            
        return False, None
    
    def _log_unprompted_message(self, channel_id, message_type):
        """Log that we sent an unprompted message"""
        from datetime import datetime, timezone
        
        if 'last_unprompted' not in self.memory_data:
            self.memory_data['last_unprompted'] = {}
            
        self.memory_data['last_unprompted'][str(channel_id)] = datetime.now(timezone.utc).timestamp()
        self.save_memory()
