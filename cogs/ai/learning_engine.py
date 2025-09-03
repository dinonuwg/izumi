"""
Advanced Learning Engine for Izumi AI
Learns from all server messages to build comprehensive user profiles
"""

import time
import re
import json
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple, Any
from utils.helpers import save_json, load_json

class LearningEngine:
    """Advanced learning system that extracts maximum data from messages"""
    
    def __init__(self, bot):
        self.bot = bot
        self.learning_data = self.load_learning_data()
        
        # Recent message context storage
        self.recent_messages = {}  # {channel_id: [recent_messages]}
        self.context_message_limit = 50  # Last 50 messages for context
        
    def load_learning_data(self) -> Dict:
        """Load persistent learning data"""
        try:
            data = load_json('data/learning_data.json')
            # If file exists but is empty or missing keys, initialize with defaults
            if not data:
                data = {}
            
            # Ensure all required keys exist
            default_structure = {
                'server_culture': {},
                'conversation_patterns': {},
                'relationship_networks': {},
                'activity_patterns': {},
                'vocabulary_trends': {},
                'topic_interests': {},
                'user_interactions': {},
                'message_sentiment': {},
                'communication_styles': {},
                # Legacy compatibility keys
                'vocabulary': {},
                'sentiment_analysis': {}
            }
            
            for key, value in default_structure.items():
                if key not in data:
                    data[key] = value
                    
            return data
        except FileNotFoundError:
            return {
                'server_culture': {},
                'conversation_patterns': {},
                'relationship_networks': {},
                'activity_patterns': {},
                'vocabulary_trends': {},
                'topic_interests': {},
                'user_interactions': {},
                'message_sentiment': {},
                'communication_styles': {},
                # Legacy compatibility keys
                'vocabulary': {},
                'sentiment_analysis': {}
            }
    
    def save_learning_data(self):
        """Save learning data to file"""
        save_json('data/learning_data.json', self.learning_data)
        
    async def learn_from_message(self, message):
        """Extract maximum information from a single message"""
        if message.author.bot or not message.guild:
            return
            
        user_id = message.author.id
        guild_id = message.guild.id
        content = message.content
        timestamp = message.created_at
        
        # Learn vocabulary and language patterns
        await self.learn_vocabulary_advanced(user_id, content, timestamp)
        
        # Learn relationships and interactions
        await self.learn_relationships_advanced(message)
        
        # Learn conversation patterns and context
        await self.learn_conversation_patterns(message)
        
        # Learn activity and temporal patterns
        await self.learn_activity_patterns(user_id, guild_id, timestamp)
        
        # Learn topic interests and preferences
        await self.learn_topic_interests(user_id, content, message.channel.id)
        
        # Learn sentiment and emotional patterns
        await self.learn_sentiment_patterns(user_id, content, timestamp)
        
        # Learn communication style and personality
        await self.learn_communication_style(user_id, content, message)
        
        # Learn server culture and dynamics
        await self.learn_server_culture_advanced(guild_id, content, user_id, timestamp)
        
        # Track cross-user influences and mimicking
        await self.learn_influence_patterns(message)
        
        # Update user memories with learned data
        await self.update_user_memories_from_learning(user_id)
        
        # Store recent messages for chat context (only non-bot messages)
        if not message.author.bot:
            await self.store_recent_message(message)
        
    async def learn_vocabulary_advanced(self, user_id: int, content: str, timestamp: datetime):
        """Learn advanced vocabulary patterns"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.learning_data['vocabulary_trends']:
            self.learning_data['vocabulary_trends'][user_id_str] = {
                'word_frequency': {},
                'phrase_patterns': {},
                'slang_evolution': [],
                'emoji_usage': {},
                'typing_quirks': {},
                'message_lengths': [],
                'punctuation_style': {},
                'capitalization_patterns': {},
                'abbreviation_usage': {},
                'question_patterns': [],
                'exclamation_patterns': [],
                'unique_expressions': [],
                'repetitive_words': {},
                'vocabulary_growth': []
            }
        
        vocab = self.learning_data['vocabulary_trends'][user_id_str]
        content_lower = content.lower()
        
        # Advanced word frequency with context
        words = re.findall(r'\b\w+\b', content_lower)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'i', 'you', 'it', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
        
        for word in words:
            if len(word) > 2 and word not in stop_words:
                vocab['word_frequency'][word] = vocab['word_frequency'].get(word, 0) + 1
        
        # Phrase patterns (2-4 word combinations)
        for length in [2, 3, 4]:
            for i in range(len(words) - length + 1):
                phrase = ' '.join(words[i:i+length])
                if all(w not in stop_words for w in words[i:i+length]):
                    vocab['phrase_patterns'][phrase] = vocab['phrase_patterns'].get(phrase, 0) + 1
        
        # Slang and internet speak detection
        slang_patterns = {
            'gen_z': ['fr', 'no cap', 'bet', 'slaps', 'bussin', 'periodt', 'slay', 'mid', 'sus', 'based', 'cringe', 'vibe', 'mood', 'stan', 'simp', 'karen', 'ok boomer'],
            'gaming': ['gg', 'ez', 'rekt', 'noob', 'pro', 'clutch', 'meta', 'nerf', 'buff', 'op', 'broken', 'carry', 'feed', 'throw'],
            'internet': ['lol', 'lmao', 'rofl', 'wtf', 'omg', 'tbh', 'ngl', 'imo', 'smh', 'fml', 'yolo', 'fomo', 'irl', 'afk', 'brb'],
            'regional': ['y\'all', 'hella', 'wicked', 'mad', 'lowkey', 'highkey', 'deadass', 'facts', 'cap', 'no cap']
        }
        
        current_time = int(timestamp.timestamp())
        for category, terms in slang_patterns.items():
            for term in terms:
                if term in content_lower:
                    vocab['slang_evolution'].append({
                        'term': term,
                        'category': category,
                        'timestamp': current_time,
                        'context': content[:50] + '...' if len(content) > 50 else content
                    })
        
        # Emoji analysis
        emoji_pattern = r'[😀-🿿]|:[a-zA-Z0-9_+-]+:'
        emojis = re.findall(emoji_pattern, content)
        for emoji in emojis:
            vocab['emoji_usage'][emoji] = vocab['emoji_usage'].get(emoji, 0) + 1
        
        # Typing quirks and style
        vocab['message_lengths'].append(len(content))
        
        # Punctuation analysis
        punctuation_counts = {
            'periods': content.count('.'),
            'exclamations': content.count('!'),
            'questions': content.count('?'),
            'ellipsis': content.count('...'),
            'commas': content.count(','),
            'semicolons': content.count(';'),
            'colons': content.count(':'),
        }
        
        for punct, count in punctuation_counts.items():
            vocab['punctuation_style'][punct] = vocab['punctuation_style'].get(punct, 0) + count
        
        # Capitalization patterns
        if content.isupper():
            vocab['capitalization_patterns']['all_caps'] = vocab['capitalization_patterns'].get('all_caps', 0) + 1
        elif content.islower():
            vocab['capitalization_patterns']['all_lower'] = vocab['capitalization_patterns'].get('all_lower', 0) + 1
        elif content[0].isupper() if content else False:
            vocab['capitalization_patterns']['proper'] = vocab['capitalization_patterns'].get('proper', 0) + 1
        
        # Abbreviation usage
        abbreviations = re.findall(r'\b[a-zA-Z]{1,5}\b', content)
        for abbr in abbreviations:
            if abbr.isupper() and len(abbr) <= 5:
                vocab['abbreviation_usage'][abbr] = vocab['abbreviation_usage'].get(abbr, 0) + 1
        
        # Question and exclamation patterns
        if '?' in content:
            vocab['question_patterns'].append(content)
        if '!' in content:
            vocab['exclamation_patterns'].append(content)
        
        # Unique expressions (phrases they use that others don't)
        unique_phrases = re.findall(r'\b\w+\s+\w+\b', content_lower)
        for phrase in unique_phrases:
            if phrase not in vocab['unique_expressions']:
                vocab['unique_expressions'].append(phrase)
        
        # Repetitive word usage within message
        word_counts = Counter(words)
        for word, count in word_counts.items():
            if count > 1:
                vocab['repetitive_words'][word] = vocab['repetitive_words'].get(word, 0) + count
        
        # Keep data manageable
        self._trim_vocabulary_data(vocab)
        
    async def learn_relationships_advanced(self, message):
        """Learn complex relationship patterns"""
        user_id = message.author.id
        user_id_str = str(user_id)
        guild_id_str = str(message.guild.id)
        
        if user_id_str not in self.learning_data['relationship_networks']:
            self.learning_data['relationship_networks'][user_id_str] = {
                'mention_frequency': {},
                'reply_frequency': {},
                'conversation_starters': {},
                'response_patterns': {},
                'shared_channels': {},
                'interaction_times': {},
                'relationship_strength': {},
                'communication_style_with_others': {},
                'group_dynamics': {},
                'conflict_patterns': {},
                'support_patterns': {},
                'humor_interactions': {}
            }
        
        relations = self.learning_data['relationship_networks'][user_id_str]
        timestamp = int(message.created_at.timestamp())
        
        # Mention analysis
        for mentioned_user in message.mentions:
            if mentioned_user.id != user_id and not mentioned_user.bot:
                mentioned_id_str = str(mentioned_user.id)
                
                relations['mention_frequency'][mentioned_id_str] = relations['mention_frequency'].get(mentioned_id_str, 0) + 1
                
                # Analyze mention context
                mention_context = message.content.lower()
                context_indicators = {
                    'positive': ['thanks', 'awesome', 'great', 'love', 'amazing', 'cool', 'nice', 'good', 'best', 'friend'],
                    'negative': ['annoying', 'stupid', 'hate', 'bad', 'worst', 'shut up', 'stop'],
                    'questioning': ['why', 'what', 'how', 'when', 'where', '?'],
                    'requesting': ['please', 'can you', 'could you', 'help', 'need'],
                    'casual': ['hey', 'yo', 'sup', 'hi', 'hello'],
                    'gaming': ['play', 'game', 'match', 'team', 'squad', 'duo', 'ranked'],
                    'supportive': ['you got this', 'good luck', 'hope', 'sorry', 'feel better']
                }
                
                for context_type, keywords in context_indicators.items():
                    if any(keyword in mention_context for keyword in keywords):
                        if mentioned_id_str not in relations['communication_style_with_others']:
                            relations['communication_style_with_others'][mentioned_id_str] = {}
                        relations['communication_style_with_others'][mentioned_id_str][context_type] = relations['communication_style_with_others'][mentioned_id_str].get(context_type, 0) + 1
        
        # Reply pattern analysis
        if message.reference and message.reference.message_id:
            try:
                replied_message = await message.channel.fetch_message(message.reference.message_id)
                if not replied_message.author.bot:
                    replied_user_id_str = str(replied_message.author.id)
                    relations['reply_frequency'][replied_user_id_str] = relations['reply_frequency'].get(replied_user_id_str, 0) + 1
                    
                    # Analyze response time
                    response_time = (message.created_at - replied_message.created_at).total_seconds()
                    if replied_user_id_str not in relations['response_patterns']:
                        relations['response_patterns'][replied_user_id_str] = []
                    relations['response_patterns'][replied_user_id_str].append(response_time)
                    
                    # Keep only recent response times
                    relations['response_patterns'][replied_user_id_str] = relations['response_patterns'][replied_user_id_str][-20:]
            except:
                pass
        
        # Channel sharing analysis
        channel_id_str = str(message.channel.id)
        if channel_id_str not in relations['shared_channels']:
            relations['shared_channels'][channel_id_str] = 0
        relations['shared_channels'][channel_id_str] += 1
        
        # Interaction timing
        hour = message.created_at.hour
        relations['interaction_times'][str(hour)] = relations['interaction_times'].get(str(hour), 0) + 1
        
    async def learn_conversation_patterns(self, message):
        """Learn how users engage in conversations"""
        user_id_str = str(message.author.id)
        
        if user_id_str not in self.learning_data['conversation_patterns']:
            self.learning_data['conversation_patterns'][user_id_str] = {
                'conversation_starters': [],
                'typical_responses': [],
                'topic_transitions': [],
                'message_frequency_patterns': [],
                'conversation_length_preference': [],
                'initiation_vs_response': {'initiates': 0, 'responds': 0},
                'question_asking_patterns': [],
                'storytelling_patterns': [],
                'reaction_patterns': {},
                'continuation_patterns': [],
                'conversation_enders': []
            }
        
        patterns = self.learning_data['conversation_patterns'][user_id_str]
        content = message.content
        
        # Detect conversation starters
        starter_indicators = ['hey', 'hi', 'hello', 'yo', 'sup', 'good morning', 'good night', 'anyone', 'does anyone', 'quick question']
        if any(indicator in content.lower() for indicator in starter_indicators):
            patterns['conversation_starters'].append(content[:100])
            patterns['initiation_vs_response']['initiates'] += 1
        
        # Check if it's a response (has message reference or mentions)
        if message.reference or message.mentions:
            patterns['initiation_vs_response']['responds'] += 1
            patterns['typical_responses'].append(content[:100])
        
        # Question patterns
        if '?' in content:
            patterns['question_asking_patterns'].append(content)
        
        # Storytelling detection (longer messages with narrative elements)
        narrative_indicators = ['so', 'then', 'after that', 'meanwhile', 'suddenly', 'finally', 'first', 'next', 'later']
        if len(content.split()) > 20 and any(indicator in content.lower() for indicator in narrative_indicators):
            patterns['storytelling_patterns'].append(content[:200])
        
        # Keep lists manageable
        for key in ['conversation_starters', 'typical_responses', 'question_asking_patterns', 'storytelling_patterns']:
            patterns[key] = patterns[key][-50:]  # Keep last 50 entries
        
    async def learn_activity_patterns(self, user_id: int, guild_id: int, timestamp: datetime):
        """Learn when and how often users are active"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.learning_data['activity_patterns']:
            self.learning_data['activity_patterns'][user_id_str] = {
                'hourly_activity': [0] * 24,
                'daily_activity': [0] * 7,  # Monday = 0
                'monthly_activity': [0] * 12,
                'message_frequency': [],
                'active_periods': [],
                'timezone_hints': [],
                'activity_streaks': [],
                'peak_hours': [],
                'inactive_periods': []
            }
        
        activity = self.learning_data['activity_patterns'][user_id_str]
        
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
        
    async def learn_topic_interests(self, user_id: int, content: str, channel_id: int):
        """Learn what topics users are interested in"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.learning_data['topic_interests']:
            self.learning_data['topic_interests'][user_id_str] = {
                'gaming_interests': {},
                'hobby_interests': {},
                'tech_interests': {},
                'entertainment_interests': {},
                'personal_interests': {},
                'channel_preferences': {},
                'topic_expertise': {},
                'question_topics': {},
                'discussion_topics': {},
                'sharing_topics': {}
            }
        
        interests = self.learning_data['topic_interests'][user_id_str]
        content_lower = content.lower()
        
        # Gaming interest detection
        gaming_keywords = {
            'fps': ['fps', 'shooting', 'csgo', 'valorant', 'cod', 'battlefield', 'apex'],
            'moba': ['moba', 'league', 'dota', 'heroes'],
            'mmo': ['mmo', 'wow', 'ffxiv', 'guild wars', 'eso'],
            'rhythm': ['osu', 'rhythm', 'beat saber', 'guitar hero'],
            'indie': ['indie', 'hollow knight', 'celeste', 'hades'],
            'aaa': ['aaa', 'cyberpunk', 'witcher', 'gta', 'red dead']
        }
        
        for category, keywords in gaming_keywords.items():
            for keyword in keywords:
                if keyword in content_lower:
                    interests['gaming_interests'][category] = interests['gaming_interests'].get(category, 0) + 1
        
        # Technology interests
        tech_keywords = ['programming', 'coding', 'python', 'javascript', 'ai', 'machine learning', 'blockchain', 'crypto', 'nft', 'tech', 'software', 'hardware', 'pc', 'build']
        for keyword in tech_keywords:
            if keyword in content_lower:
                interests['tech_interests'][keyword] = interests['tech_interests'].get(keyword, 0) + 1
        
        # Entertainment interests
        entertainment_keywords = ['anime', 'manga', 'movie', 'netflix', 'show', 'series', 'music', 'song', 'artist', 'band', 'concert']
        for keyword in entertainment_keywords:
            if keyword in content_lower:
                interests['entertainment_interests'][keyword] = interests['entertainment_interests'].get(keyword, 0) + 1
        
        # Channel preferences
        channel_id_str = str(channel_id)
        interests['channel_preferences'][channel_id_str] = interests['channel_preferences'].get(channel_id_str, 0) + 1
        
    async def learn_sentiment_patterns(self, user_id: int, content: str, timestamp: datetime):
        """Learn emotional patterns and sentiment"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.learning_data['message_sentiment']:
            self.learning_data['message_sentiment'][user_id_str] = {
                'positive_indicators': 0,
                'negative_indicators': 0,
                'neutral_indicators': 0,
                'excitement_level': [],
                'frustration_level': [],
                'humor_usage': 0,
                'support_giving': 0,
                'complaint_frequency': 0,
                'gratitude_expressions': 0,
                'mood_patterns': [],
                'emotional_vocabulary': {}
            }
        
        sentiment = self.learning_data['message_sentiment'][user_id_str]
        content_lower = content.lower()
        
        # Sentiment analysis
        positive_words = ['great', 'awesome', 'love', 'amazing', 'good', 'nice', 'cool', 'best', 'happy', 'excited', 'thank', 'thanks', 'appreciate']
        negative_words = ['bad', 'hate', 'worst', 'awful', 'terrible', 'annoying', 'frustrated', 'angry', 'sad', 'disappointed']
        humor_words = ['lol', 'lmao', 'haha', 'funny', 'joke', 'meme', 'comedy']
        
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        humor_count = sum(1 for word in humor_words if word in content_lower)
        
        sentiment['positive_indicators'] += positive_count
        sentiment['negative_indicators'] += negative_count
        sentiment['humor_usage'] += humor_count
        
        # Excitement detection (caps, multiple exclamation marks)
        excitement_score = 0
        if content.isupper() and len(content) > 3:
            excitement_score += 2
        excitement_score += content.count('!') * 0.5
        excitement_score += len(re.findall(r'[😀-🿿]', content)) * 0.3
        
        sentiment['excitement_level'].append(excitement_score)
        
        # Frustration detection
        frustration_indicators = ['ugh', 'wtf', 'seriously', 'come on', 'why', 'how is', 'this is ridiculous']
        frustration_score = sum(1 for indicator in frustration_indicators if indicator in content_lower)
        sentiment['frustration_level'].append(frustration_score)
        
        # Keep recent mood data
        current_time = int(timestamp.timestamp())
        sentiment['mood_patterns'].append({
            'timestamp': current_time,
            'positive': positive_count,
            'negative': negative_count,
            'excitement': excitement_score,
            'frustration': frustration_score
        })
        
        # Keep only recent mood data (last 100 messages)
        sentiment['mood_patterns'] = sentiment['mood_patterns'][-100:]
        sentiment['excitement_level'] = sentiment['excitement_level'][-100:]
        sentiment['frustration_level'] = sentiment['frustration_level'][-100:]
        
    async def learn_communication_style(self, user_id: int, content: str, message):
        """Learn individual communication styles"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.learning_data['communication_styles']:
            self.learning_data['communication_styles'][user_id_str] = {
                'formality_level': 0,
                'verbosity_preference': [],
                'emoji_frequency': 0,
                'punctuation_habits': {},
                'greeting_style': [],
                'farewell_style': [],
                'help_requesting_style': [],
                'information_sharing_style': [],
                'reaction_style': {},
                'authority_interaction': {},
                'peer_interaction': {},
                'newcomer_interaction': {}
            }
        
        style = self.learning_data['communication_styles'][user_id_str]
        content_lower = content.lower()
        
        # Formality detection
        formal_indicators = ['please', 'thank you', 'could you', 'would you', 'excuse me', 'pardon', 'sir', 'madam']
        informal_indicators = ['yo', 'hey', 'sup', 'gonna', 'wanna', 'dunno', 'yeah', 'nah']
        
        formal_count = sum(1 for indicator in formal_indicators if indicator in content_lower)
        informal_count = sum(1 for indicator in informal_indicators if indicator in content_lower)
        
        if formal_count > informal_count:
            style['formality_level'] += 1
        elif informal_count > formal_count:
            style['formality_level'] -= 1
        
        # Verbosity tracking
        word_count = len(content.split())
        style['verbosity_preference'].append(word_count)
        style['verbosity_preference'] = style['verbosity_preference'][-50:]  # Keep recent data
        
        # Emoji usage
        emoji_count = len(re.findall(r'[😀-🿿]|:[a-zA-Z0-9_+-]+:', content))
        style['emoji_frequency'] += emoji_count
        
        # Greeting and farewell detection
        greetings = ['hello', 'hi', 'hey', 'yo', 'sup', 'good morning', 'good evening']
        farewells = ['bye', 'goodbye', 'see you', 'later', 'good night', 'cya', 'ttyl']
        
        for greeting in greetings:
            if greeting in content_lower:
                style['greeting_style'].append(greeting)
        
        for farewell in farewells:
            if farewell in content_lower:
                style['farewell_style'].append(farewell)
        
        # Keep recent greetings/farewells
        style['greeting_style'] = style['greeting_style'][-20:]
        style['farewell_style'] = style['farewell_style'][-20:]
        
    async def learn_server_culture_advanced(self, guild_id: int, content: str, user_id: int, timestamp: datetime):
        """Learn comprehensive server culture"""
        guild_id_str = str(guild_id)
        
        if guild_id_str not in self.learning_data['server_culture']:
            self.learning_data['server_culture'][guild_id_str] = {
                'common_phrases': {},
                'inside_jokes': {},
                'recurring_topics': {},
                'server_memes': {},
                'cultural_references': {},
                'shared_vocabulary': {},
                'community_events': [],
                'server_traditions': [],
                'popular_opinions': {},
                'controversial_topics': {},
                'trending_topics': {},
                'influential_users': {},
                'cultural_evolution': []
            }
        
        culture = self.learning_data['server_culture'][guild_id_str]
        content_lower = content.lower()
        current_time = int(timestamp.timestamp())
        
        # Track phrases that become popular
        if len(content.split()) <= 8:  # Short phrases only
            culture['common_phrases'][content_lower] = culture['common_phrases'].get(content_lower, 0) + 1
        
        # Detect potential memes or inside jokes
        # Look for phrases that suddenly become popular
        words = content_lower.split()
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            if len(phrase) > 5:
                culture['recurring_topics'][phrase] = culture['recurring_topics'].get(phrase, 0) + 1
        
        # Track trending topics over time
        hour_key = str(timestamp.hour)
        day_key = str(timestamp.date())
        
        if day_key not in culture['trending_topics']:
            culture['trending_topics'][day_key] = {}
        
        # Simple topic extraction (words used frequently in a day)
        for word in words:
            if len(word) > 4:  # Ignore short words
                culture['trending_topics'][day_key][word] = culture['trending_topics'][day_key].get(word, 0) + 1
        
        # Track influential users (those whose phrases get repeated)
        user_phrases = culture.get('user_phrases', {})
        user_id_str = str(user_id)
        if user_id_str not in user_phrases:
            user_phrases[user_id_str] = []
        user_phrases[user_id_str].append(content_lower)
        culture['user_phrases'] = user_phrases
        
        # Keep data manageable
        self._trim_culture_data(culture)
        
    async def learn_influence_patterns(self, message):
        """Learn how users influence each other's speech patterns"""
        # This would track when users start using phrases/words after seeing others use them
        # Implementation would involve comparing user vocabulary over time
        pass
        
    async def update_user_memories_from_learning(self, user_id: int):
        """Update bot's user memories with learned insights"""
        user_id_str = str(user_id)
        memories = self.bot.get_user_memories(user_id)
        
        # Update personality notes from learning data
        if user_id_str in self.learning_data['communication_styles']:
            style = self.learning_data['communication_styles'][user_id_str]
            
            # Get current personality notes to avoid duplicates
            current_memories = self.bot.get_user_memories(user_id)
            current_notes = current_memories.get('personality_notes', [])
            
            # Determine if formal or informal (only add if not already present)
            if style['formality_level'] > 5 and "speaks formally" not in current_notes:
                self.bot.update_user_memory(user_id, "personality_notes", "speaks formally", append=True)
            elif style['formality_level'] < -5 and "speaks casually" not in current_notes:
                self.bot.update_user_memory(user_id, "personality_notes", "speaks casually", append=True)
            
            # Average message length preference (only add if not already present)
            if style['verbosity_preference']:
                avg_length = sum(style['verbosity_preference']) / len(style['verbosity_preference'])
                if avg_length > 50 and "tends to write long messages" not in current_notes:
                    self.bot.update_user_memory(user_id, "personality_notes", "tends to write long messages", append=True)
                elif avg_length < 10 and "prefers short messages" not in current_notes:
                    self.bot.update_user_memory(user_id, "personality_notes", "prefers short messages", append=True)
        
        # Update interests from topic learning (check for duplicates)
        if user_id_str in self.learning_data['topic_interests']:
            interests = self.learning_data['topic_interests'][user_id_str]
            current_interests = current_memories.get('interests', [])
            
            # Gaming interests (only add if not already present)
            if interests['gaming_interests']:
                top_gaming = max(interests['gaming_interests'], key=interests['gaming_interests'].get)
                gaming_interest = f"{top_gaming} games"
                if gaming_interest not in current_interests:
                    self.bot.update_user_memory(user_id, "interests", gaming_interest, append=True)
            
            # Tech interests (only add if not already present)
            if interests['tech_interests']:
                tech_terms = [term for term, count in interests['tech_interests'].items() if count > 2]
                for term in tech_terms[:3]:  # Top 3
                    if term not in current_interests:
                        self.bot.update_user_memory(user_id, "interests", term, append=True)
        
        # Update sentiment patterns (check for duplicates)
        if user_id_str in self.learning_data['message_sentiment']:
            sentiment = self.learning_data['message_sentiment'][user_id_str]
            
            total_messages = sentiment['positive_indicators'] + sentiment['negative_indicators'] + sentiment.get('neutral_indicators', 0)
            if total_messages > 20:  # Enough data to make judgments
                positive_ratio = sentiment['positive_indicators'] / total_messages
                if positive_ratio > 0.7 and "generally positive and upbeat" not in current_notes:
                    self.bot.update_user_memory(user_id, "personality_notes", "generally positive and upbeat", append=True)
                elif positive_ratio < 0.3 and "tends to be more critical or negative" not in current_notes:
                    self.bot.update_user_memory(user_id, "personality_notes", "tends to be more critical or negative", append=True)
    
    def _trim_vocabulary_data(self, vocab: Dict):
        """Keep vocabulary data manageable"""
        # Trim word frequency to top 100
        if len(vocab['word_frequency']) > 100:
            sorted_words = sorted(vocab['word_frequency'].items(), key=lambda x: x[1], reverse=True)
            vocab['word_frequency'] = dict(sorted_words[:100])
        
        # Trim phrase patterns to top 50
        if len(vocab['phrase_patterns']) > 50:
            sorted_phrases = sorted(vocab['phrase_patterns'].items(), key=lambda x: x[1], reverse=True)
            vocab['phrase_patterns'] = dict(sorted_phrases[:50])
        
        # Keep recent slang evolution entries
        vocab['slang_evolution'] = vocab['slang_evolution'][-100:]
        
        # Trim emoji usage to top 30
        if len(vocab['emoji_usage']) > 30:
            sorted_emojis = sorted(vocab['emoji_usage'].items(), key=lambda x: x[1], reverse=True)
            vocab['emoji_usage'] = dict(sorted_emojis[:30])
        
        # Keep recent message lengths
        vocab['message_lengths'] = vocab['message_lengths'][-200:]
        
        # Trim unique expressions
        vocab['unique_expressions'] = vocab['unique_expressions'][-50:]
        
        # Trim question and exclamation patterns
        vocab['question_patterns'] = vocab['question_patterns'][-30:]
        vocab['exclamation_patterns'] = vocab['exclamation_patterns'][-30:]
    
    def _trim_culture_data(self, culture: Dict):
        """Keep server culture data manageable"""
        # Keep top common phrases
        if len(culture['common_phrases']) > 50:
            sorted_phrases = sorted(culture['common_phrases'].items(), key=lambda x: x[1], reverse=True)
            culture['common_phrases'] = dict(sorted_phrases[:50])
        
        # Keep top recurring topics
        if len(culture['recurring_topics']) > 100:
            sorted_topics = sorted(culture['recurring_topics'].items(), key=lambda x: x[1], reverse=True)
            culture['recurring_topics'] = dict(sorted_topics[:100])
        
        # Keep recent trending topics (last 7 days)
        if 'trending_topics' in culture:
            current_time = datetime.now()
            week_ago = current_time - timedelta(days=7)
            
            filtered_topics = {}
            for date_str, topics in culture['trending_topics'].items():
                try:
                    date_obj = datetime.fromisoformat(date_str)
                    if date_obj >= week_ago:
                        filtered_topics[date_str] = topics
                except:
                    continue
            
            culture['trending_topics'] = filtered_topics
        
        # Trim user phrases
        if 'user_phrases' in culture:
            for user_id, phrases in culture['user_phrases'].items():
                culture['user_phrases'][user_id] = phrases[-50:]  # Keep recent phrases
    
    # ==================== LEGACY MEMORY SYSTEM COMPATIBILITY ====================
    
    def get_user_memories(self, user_id: int) -> dict:
        """Get user memories in the old format for compatibility"""
        user_id_str = str(user_id)
        
        # Get data from old memory system FIRST (this is the main source)
        old_memories = self.bot.izumi_memories.get(user_id_str, {})
        
        # Create structure based on old memories
        memories = {
            "name": old_memories.get("name", ""),
            "nickname": old_memories.get("nickname", ""),
            "age": old_memories.get("age", ""),
            "birthday": old_memories.get("birthday", ""),
            "relationship_status": old_memories.get("relationship_status", ""),
            "interests": old_memories.get("interests", []).copy() if old_memories.get("interests") else [],
            "dislikes": old_memories.get("dislikes", []).copy() if old_memories.get("dislikes") else [],
            "personality_notes": old_memories.get("personality_notes", []).copy() if old_memories.get("personality_notes") else [],
            "trust_level": old_memories.get("trust_level", 0),
            "conversation_style": old_memories.get("conversation_style", ""),
            "important_events": old_memories.get("important_events", []).copy() if old_memories.get("important_events") else [],
            "custom_notes": old_memories.get("custom_notes", []).copy() if old_memories.get("custom_notes") else [],
            "relationships": old_memories.get("relationships", {}).copy() if old_memories.get("relationships") else {},
            "shared_experiences": old_memories.get("shared_experiences", {}).copy() if old_memories.get("shared_experiences") else {},
            "last_interaction": old_memories.get("last_interaction", 0)
        }
        
        # Enhance with NEW learning data (but don't override old data)
        try:
            # Get data from new learning system
            vocab_data = self.learning_data.get('vocabulary_trends', {}).get(user_id_str, {})
            relation_data = self.learning_data.get('relationship_networks', {}).get(user_id_str, {})
            sentiment_data = self.learning_data.get('message_sentiment', {}).get(user_id_str, {})
            
            # Add learned interests (but don't override existing ones)
            if vocab_data and vocab_data.get('word_frequency'):
                frequent_words = []
                for word, count in vocab_data['word_frequency'].items():
                    if count > 5 and len(word) > 3:  # Words used more than 5 times
                        frequent_words.append(word)
                if frequent_words:
                    # Add only new interests
                    for word in frequent_words[:3]:  # Top 3
                        if word not in memories["interests"]:
                            memories["interests"].append(word)
            
            # Add learned personality notes (but don't override existing ones)
            if sentiment_data:
                total_positive = sentiment_data.get('positive_indicators', 0)
                total_negative = sentiment_data.get('negative_indicators', 0)
                total_messages = total_positive + total_negative + sentiment_data.get('neutral_indicators', 0)
                
                if total_messages > 20:  # Enough data to make judgments
                    positive_ratio = total_positive / total_messages
                    if positive_ratio > 0.7:
                        if "generally positive and upbeat" not in memories["personality_notes"]:
                            memories["personality_notes"].append("generally positive and upbeat")
                    elif positive_ratio < 0.3:
                        if "tends to be more critical or negative" not in memories["personality_notes"]:
                            memories["personality_notes"].append("tends to be more critical or negative")
        except Exception as e:
            # If there's any error with learning data, just use old memories
            print(f"Error enhancing memories with learning data: {e}")
        
        return memories
    
    def update_user_memory(self, user_id: int, key: str, value, append: bool = False):
        """Update user memory in the old format"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.bot.izumi_memories:
            self.bot.izumi_memories[user_id_str] = {}
        
        if append and key in self.bot.izumi_memories[user_id_str]:
            if isinstance(self.bot.izumi_memories[user_id_str][key], list):
                if value not in self.bot.izumi_memories[user_id_str][key]:
                    self.bot.izumi_memories[user_id_str][key].append(value)
            else:
                # Convert to list
                self.bot.izumi_memories[user_id_str][key] = [self.bot.izumi_memories[user_id_str][key], value]
        else:
            self.bot.izumi_memories[user_id_str][key] = value
        
        # Update timestamp
        self.bot.izumi_memories[user_id_str]["last_interaction"] = int(time.time())
        self.bot.pending_saves = True
    
    def update_user_relationship(self, user1_id: int, user2_id: int, relationship: str):
        """Update relationship between two users"""
        user1_str = str(user1_id)
        user2_str = str(user2_id)
        
        # Update in old memory system
        if user1_str not in self.bot.izumi_memories:
            self.bot.izumi_memories[user1_str] = {}
        if "relationships" not in self.bot.izumi_memories[user1_str]:
            self.bot.izumi_memories[user1_str]["relationships"] = {}
        
        self.bot.izumi_memories[user1_str]["relationships"][user2_str] = relationship
        self.bot.izumi_memories[user1_str]["last_interaction"] = int(time.time())
        
        # Also update in new learning system
        if user1_str not in self.learning_data['relationship_networks']:
            self.learning_data['relationship_networks'][user1_str] = {
                'mention_frequency': {}, 'reply_frequency': {}, 'conversation_starters': {},
                'response_patterns': {}, 'shared_channels': {}, 'interaction_times': {},
                'relationship_strength': {}, 'communication_style_with_others': {},
                'group_dynamics': {}, 'conflict_patterns': {}, 'support_patterns': {},
                'humor_interactions': {}
            }
        
        # Set relationship strength based on type
        strength_map = {
            'friend': 8, 'best friend': 10, 'close friend': 9,
            'family': 10, 'sibling': 9, 'parent': 10, 'child': 10,
            'teammate': 6, 'colleague': 5, 'acquaintance': 3,
            'enemy': -5, 'rival': -2, 'ex': -3, 'crush': 8
        }
        strength = strength_map.get(relationship.lower(), 5)
        self.learning_data['relationship_networks'][user1_str]['relationship_strength'][user2_str] = strength
        
        self.bot.pending_saves = True
    
    def add_shared_experience(self, user1_id: int, user2_id: int, experience: str):
        """Add shared experience between two users"""
        user1_str = str(user1_id)
        user2_str = str(user2_id)
        
        # Update both users in old memory system
        for user_str in [user1_str, user2_str]:
            if user_str not in self.bot.izumi_memories:
                self.bot.izumi_memories[user_str] = {}
            if "shared_experiences" not in self.bot.izumi_memories[user_str]:
                self.bot.izumi_memories[user_str]["shared_experiences"] = {}
            
            other_str = user2_str if user_str == user1_str else user1_str
            if other_str not in self.bot.izumi_memories[user_str]["shared_experiences"]:
                self.bot.izumi_memories[user_str]["shared_experiences"][other_str] = []
            
            self.bot.izumi_memories[user_str]["shared_experiences"][other_str].append(experience)
            self.bot.izumi_memories[user_str]["last_interaction"] = int(time.time())
        
        self.bot.pending_saves = True
    
    def get_shared_context(self, user_id: int, guild_id: int = None, channel_id: int = None) -> str:
        """Get shared context for a user"""
        user_id_str = str(user_id)
        context_parts = []
        
        # Get relationship data
        if user_id_str in self.learning_data['relationship_networks']:
            relations = self.learning_data['relationship_networks'][user_id_str]
            
            # Most mentioned users
            if relations['mention_frequency']:
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
            
            # Relationship strengths
            if relations['relationship_strength']:
                strong_relations = []
                for other_id_str, strength in relations['relationship_strength'].items():
                    if strength > 6:
                        try:
                            if guild_id:
                                guild = self.bot.get_guild(guild_id)
                                if guild:
                                    user = guild.get_member(int(other_id_str))
                                    if user:
                                        strong_relations.append(user.display_name)
                        except:
                            pass
                if strong_relations:
                    context_parts.append(f"💝 Close to: {', '.join(strong_relations[:3])}")
        
        # Get old memory relationships
        old_memories = self.bot.izumi_memories.get(user_id_str, {})
        if old_memories.get("relationships"):
            relationship_info = []
            for other_user_id_str, relationship in old_memories["relationships"].items():
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
    
    def get_izumi_self_memories(self) -> dict:
        """Get Izumi's self memories"""
        return self.bot.izumi_self
    
    def update_izumi_self_memory(self, category: str, value: str, append: bool = False):
        """Update Izumi's self memory"""
        if category not in self.bot.izumi_self:
            self.bot.izumi_self[category] = []
        
        if append:
            if value not in self.bot.izumi_self[category]:
                self.bot.izumi_self[category].append(value)
        else:
            self.bot.izumi_self[category] = value
        
        self.bot.pending_saves = True
    
    # ==================== RECENT MESSAGE CONTEXT SYSTEM ====================
    
    async def store_recent_message(self, message):
        """Store recent messages for chat context"""
        channel_id = message.channel.id
        
        if channel_id not in self.recent_messages:
            self.recent_messages[channel_id] = []
        
        # Create message data for context
        message_data = {
            'author_id': message.author.id,
            'author_name': message.author.display_name,
            'content': message.content[:300],  # Limit content length
            'timestamp': message.created_at.timestamp(),
            'mentions_bot': self.bot.user in message.mentions,
            'has_attachments': len(message.attachments) > 0,
            'channel_id': channel_id
        }
        
        self.recent_messages[channel_id].append(message_data)
        
        # Keep only the most recent messages
        if len(self.recent_messages[channel_id]) > self.context_message_limit:
            self.recent_messages[channel_id] = self.recent_messages[channel_id][-self.context_message_limit:]
    
    def get_recent_chat_context(self, channel_id: int, exclude_mentions: bool = True) -> str:
        """Get recent chat context for AI understanding"""
        if channel_id not in self.recent_messages:
            return ""
        
        messages = self.recent_messages[channel_id]
        
        # Filter out bot mentions if requested (to show what led to the mention)
        if exclude_mentions:
            messages = [msg for msg in messages if not msg['mentions_bot']]
        
        if not messages:
            return ""
        
        # Use ALL recent messages for maximum conversation context (all 50 messages)
        recent_messages = messages  # Use all available messages for full context
        
        if not recent_messages:
            return ""
        
        # Format context
        context_lines = []
        for msg in recent_messages:
            author = msg['author_name']
            content = msg['content']
            
            # Clean up the content for context
            content = self._clean_message_for_context(content)
            
            # Add attachment note if applicable
            if msg['has_attachments']:
                content += " [shared image/file]"
            
            # Format the line
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
        
        # Remove excessive punctuation
        content = re.sub(r'([!?.]){3,}', r'\1\1\1', content)
        
        # Limit length
        if len(content) > 150:
            content = content[:147] + "..."
        
        return content
