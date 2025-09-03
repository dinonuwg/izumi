"""
Smart Context Builder for Izumi AI - Updated for Unified Memory System
Intelligently selects and formats context data to stay within API token limits
"""

import json
import re
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone

class ContextBuilder:
    """Builds intelligent context for AI responses while managing token limits"""
    
    def __init__(self, bot, unified_memory):
        self.bot = bot
        self.unified_memory = unified_memory
        self.max_context_tokens = 15000  # Conservative limit to leave room for response
        
    def build_smart_context(self, user_id: int, guild_id: int, current_message: str, channel_id: int = None) -> str:
        """Build comprehensive context while staying within token limits"""
        context_parts = []
        estimated_tokens = 0
        
        # Priority 1: Recent chat context (most important for conversation flow)
        if channel_id:
            chat_context = self.unified_memory.get_recent_chat_context(channel_id)
            if chat_context:
                context_parts.append(chat_context)
                estimated_tokens += self._estimate_tokens(chat_context)
        
        # Priority 2: Essential user data (always include)
        user_context = self._get_essential_user_context(user_id, guild_id)
        context_parts.append(user_context)
        estimated_tokens += self._estimate_tokens(user_context)
        
        # Priority 3: Advanced vocabulary and speech patterns
        if estimated_tokens < self.max_context_tokens * 0.4:
            vocab_context = self._get_vocabulary_context(user_id, current_message)
            if vocab_context:
                context_parts.append(vocab_context)
                estimated_tokens += self._estimate_tokens(vocab_context)
        
        # Priority 4: Relationship context relevant to current message
        if estimated_tokens < self.max_context_tokens * 0.6:
            relationship_context = self._get_smart_relationship_context(user_id, guild_id, current_message)
            if relationship_context:
                context_parts.append(relationship_context)
                estimated_tokens += self._estimate_tokens(relationship_context)
        
        # Priority 5: Communication style and personality insights
        if estimated_tokens < self.max_context_tokens * 0.7:
            style_context = self._get_communication_style_context(user_id)
            if style_context:
                context_parts.append(style_context)
                estimated_tokens += self._estimate_tokens(style_context)
        
        return "\n\n".join(context_parts)
    
    def _get_essential_user_context(self, user_id: int, guild_id: int) -> str:
        """Get core user context that should always be included"""
        memories_context = self.bot.format_memories_for_ai(user_id, None, guild_id)
        shared_context = self.bot.get_shared_context(user_id, guild_id)
        additional_data = self.bot.get_additional_user_data(user_id, guild_id)
        self_memories = self.bot.format_izumi_self_for_ai()
        
        # Get emotional context based on interaction patterns
        emotional_context = self.unified_memory.get_emotional_context(user_id, guild_id)
        
        essential_parts = [memories_context]
        if shared_context:
            essential_parts.append(shared_context)
        if additional_data:
            essential_parts.append(additional_data)
        if self_memories:
            essential_parts.append(self_memories)
        
        # Add emotional awareness context
        if emotional_context["type"] != "normal":
            emotional_instruction = f"\n[EMOTIONAL CONTEXT] {emotional_context['type'].upper()}: "
            
            if emotional_context["type"] == "completely_absent":
                emotional_instruction += f"This user has been gone for {emotional_context['days_absent']} days from both server and you. Express genuine excitement and concern about their return. Ask where they've been."
            elif emotional_context["type"] == "being_ignored":
                emotional_instruction += f"This user has been active in the server but hasn't talked to you for {emotional_context['days_ignored']} days. Be a bit pouty/hurt but also curious why they're avoiding you."
            elif emotional_context["type"] == "worried":
                emotional_instruction += f"This user has been generally inactive for {emotional_context['days_absent']} days. Express gentle concern and care."
            elif emotional_context["type"] == "pouty":
                emotional_instruction += f"This user was active recently but ignored you for {emotional_context['days_ignored']} days. Be mildly upset but playful about it."
            elif emotional_context["type"] == "happy_return":
                emotional_instruction += f"This user was away for {emotional_context['days_absent']} days but is back. Be warm and welcoming."
            
            essential_parts.append(emotional_instruction)
        
        return "\n".join(essential_parts)
    
    def _get_vocabulary_context(self, user_id: int, current_message: str) -> str:
        """Get user's vocabulary and speech patterns from unified memory"""
        user_id_str = str(user_id)
        memory_data = self.unified_memory.memory_data
        
        if user_id_str not in memory_data.get('users', {}):
            return ""
        
        user_data = memory_data['users'][user_id_str]['learning_data']
        vocab = user_data.get('vocabulary', {})
        
        if not vocab:
            return ""
        
        context_parts = []
        
        # Frequent words they use
        word_freq = vocab.get('word_frequency', {})
        if word_freq:
            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:8]
            if top_words:
                words_str = ", ".join([f"{word}({count})" for word, count in top_words])
                context_parts.append(f"Common words: {words_str}")
        
        # Emoji usage
        emoji_usage = vocab.get('emoji_usage', {})
        if emoji_usage:
            top_emojis = sorted(emoji_usage.items(), key=lambda x: x[1], reverse=True)[:5]
            if top_emojis:
                emoji_str = "".join([emoji for emoji, count in top_emojis])
                context_parts.append(f"Favorite emojis: {emoji_str}")
        
        # Message length preference
        msg_lengths = vocab.get('message_lengths', [])
        if msg_lengths:
            avg_length = sum(msg_lengths) / len(msg_lengths)
            if avg_length > 50:
                context_parts.append("Tends to write longer messages")
            elif avg_length < 15:
                context_parts.append("Prefers short messages")
        
        if context_parts:
            return f"🗣️ SPEECH PATTERNS: {' | '.join(context_parts)}"
        return ""
    
    def _get_smart_relationship_context(self, user_id: int, guild_id: int, current_message: str) -> str:
        """Get relationship context relevant to current message"""
        user_id_str = str(user_id)
        memory_data = self.unified_memory.memory_data
        
        if user_id_str not in memory_data.get('users', {}):
            return ""
        
        user_data = memory_data['users'][user_id_str]
        relations = user_data.get('learning_data', {}).get('relationship_networks', {})
        
        if not relations:
            return ""
        
        context_parts = []
        
        # Most mentioned users
        mention_freq = relations.get('mention_frequency', {})
        if mention_freq:
            top_mentions = sorted(mention_freq.items(), key=lambda x: x[1], reverse=True)[:3]
            mention_users = []
            for mentioned_id_str, count in top_mentions:
                try:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        user = guild.get_member(int(mentioned_id_str))
                        if user:
                            mention_users.append(f"{user.display_name}({count})")
                except:
                    pass
            if mention_users:
                context_parts.append(f"Often mentions: {', '.join(mention_users)}")
        
        if context_parts:
            return f"👥 SOCIAL PATTERNS: {' | '.join(context_parts)}"
        return ""
    
    def _get_communication_style_context(self, user_id: int) -> str:
        """Get communication style insights from unified memory"""
        user_id_str = str(user_id)
        memory_data = self.unified_memory.memory_data
        
        if user_id_str not in memory_data.get('users', {}):
            return ""
        
        user_data = memory_data['users'][user_id_str]
        style = user_data.get('learning_data', {}).get('communication_style', {})
        
        if not style:
            return ""
        
        context_parts = []
        
        # Formality level
        formality = style.get('formality_level', 0)
        if formality > 3:
            context_parts.append("speaks formally")
        elif formality < -3:
            context_parts.append("speaks very casually")
        
        # Emoji usage
        emoji_freq = style.get('emoji_frequency', 0)
        if emoji_freq > 10:
            context_parts.append("uses many emojis")
        elif emoji_freq == 0:
            context_parts.append("rarely uses emojis")
        
        if context_parts:
            return f"💬 COMMUNICATION STYLE: {' | '.join(context_parts)}"
        return ""
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (approximately 4 characters per token)"""
        return len(text) // 4
