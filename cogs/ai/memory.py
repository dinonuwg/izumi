import discord
from discord.ext import commands
from discord import app_commands
from utils.helpers import *
from utils.config import *
import time
import json
import os

# Load BOT_OWNER_ID from environment variable
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))  # Default to 0 if not set

class MemoryManagement(commands.Cog):
    """Manage Izumi's memories about users"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def _truncate_field_value(self, value: str, max_length: int = 800) -> str:
        """Truncate field value to fit Discord's embed limits"""
        if len(value) <= max_length:
            return value
        return value[:max_length-3] + "..."
    
    def _calculate_embed_size(self, embed: discord.Embed) -> int:
        """Calculate approximate embed size in characters"""
        size = len(embed.title or "") + len(embed.description or "")
        for field in embed.fields:
            size += len(field.name) + len(field.value)
        if embed.footer:
            size += len(embed.footer.text or "")
        return size

    @commands.group(name='memory', invoke_without_command=True)
    async def memory(self, ctx):
        """Memory management commands for Izumi"""
        embed = discord.Embed(
            title="🧠 Izumi's Memory System",
            description="Manage what Izumi remembers about users",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="Commands:",
            value=(
                "`!memory view [user]` - View memories about a user\n"
                "`!memory add <user> <note>` - Add a custom note\n"
                "`!memory set <user> <field> <value>` - Set a specific field\n"
                "`!memory trust <user> <-10 to 10>` - Set trust level\n"
                "`!memory relate <user1> <user2> <relationship>` - Set relationship\n"
                "`!memory shared <user1> <user2> <experience>` - Add shared experience\n"
                "`!memory context <user>` - View user's social context\n"
                "`!memory clear <user>` - Clear all memories about a user\n"
                "`!memory forget <user>` - Make Izumi forget your conversation\n"
                "`!memory self` - View Izumi's self-memories\n"
                "`!memory selfadd <category> <value>` - Add to Izumi's memories\n"
                "`!memory selfclear <category>` - Clear a category of self-memories\n"
                "`!memory knowledge <info>` - Add general knowledge/information\n"
                "`!memory viewknowledge` - View stored general knowledge"
            ),
            inline=False
        )
        embed.add_field(
            name="Self-memory categories:",
            value=(
                "`personality_traits`, `likes`, `dislikes`, `backstory`, `goals`, "
                "`fears`, `hobbies`, `favorite_things`, `pet_peeves`, `life_philosophy`, "
                "`memories`, `relationships`, `skills`, `dreams`, `quirks`, `knowledge`"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @memory.command(name='view')
    async def view_memory(self, ctx, user: discord.Member = None):
        """View memories about a user"""
        if user is None:
            user = ctx.author
        
        memories = self.bot.get_user_memories(user.id)
        
        # Check if user has any memories stored
        has_memories = any([
            memories.get("name"),
            memories.get("nickname"), 
            memories.get("age"),
            memories.get("birthday"),
            memories.get("interests"),
            memories.get("personality"),
            memories.get("notes"),
            memories.get("achievements"),
            memories.get("last_seen")
        ])
        
        if not has_memories:
            await ctx.send(f"No memories stored about {user.display_name} yet!")
            return
        
        embed = discord.Embed(
            title=f"🧠 Izumi's memories about {user.display_name}",
            color=discord.Color.purple()
        )
        
        # Basic info
        basic_info = []
        if memories["name"]:
            basic_info.append(f"**Name:** {memories['name']}")
        if memories["nickname"]:
            basic_info.append(f"**Nickname:** {memories['nickname']}")
        if memories["age"]:
            basic_info.append(f"**Age:** {memories['age']}")
        if memories["birthday"]:
            basic_info.append(f"**Birthday:** {memories['birthday']}")
        if memories["relationship_status"]:
            basic_info.append(f"**Relationship:** {memories['relationship_status']}")
        
        if basic_info:
            embed.add_field(name="Basic Info", value="\n".join(basic_info), inline=False)
        
        # Personality & preferences
        if memories["interests"]:
            embed.add_field(
                name="Interests", 
                value=", ".join(memories["interests"]), 
                inline=False
            )
        
        if memories["dislikes"]:
            embed.add_field(
                name="Dislikes", 
                value=", ".join(memories["dislikes"]), 
                inline=False
            )
        
        if memories["personality_notes"]:
            embed.add_field(
                name="Personality Notes", 
                value=", ".join(memories["personality_notes"]), 
                inline=False
            )
        
        # Trust level with emoji
        trust = memories["trust_level"]
        trust_emoji = "💚" if trust > 5 else "💛" if trust > 0 else "❤️" if trust == 0 else "🧡" if trust > -5 else "💔"
        embed.add_field(
            name="Trust Level", 
            value=f"{trust_emoji} {trust}/10", 
            inline=True
        )
        
        # Other info
        if memories["conversation_style"]:
            embed.add_field(
                name="Communication Style", 
                value=memories["conversation_style"], 
                inline=True
            )
        
        if memories["important_events"]:
            embed.add_field(
                name="Important Events", 
                value="\n".join(memories["important_events"]), 
                inline=False
            )
        
        if memories["custom_notes"]:
            embed.add_field(
                name="Custom Notes", 
                value="\n".join(memories["custom_notes"]), 
                inline=False
            )
        
        # Social connections
        if memories.get("relationships"):
            relationship_info = []
            for other_user_id_str, relationship in memories["relationships"].items():
                try:
                    other_user_id = int(other_user_id_str)
                    other_user = ctx.guild.get_member(other_user_id)
                    if other_user:
                        relationship_info.append(f"{other_user.display_name} ({relationship})")
                except:
                    continue
            
            if relationship_info:
                embed.add_field(
                    name="Known Relationships",
                    value="\n".join(relationship_info[:5]),  # Limit to 5
                    inline=False
                )
        
        if memories.get("shared_experiences"):
            shared_info = []
            for other_user_id_str, experiences in memories["shared_experiences"].items():
                try:
                    other_user_id = int(other_user_id_str)
                    other_user = ctx.guild.get_member(other_user_id)
                    if other_user and experiences:
                        recent_experiences = experiences[-2:]  # Last 2 experiences
                        shared_info.append(f"**{other_user.display_name}:** {'; '.join(recent_experiences)}")
                except:
                    continue
            
            if shared_info:
                embed.add_field(
                    name="Shared Experiences",
                    value="\n".join(shared_info[:3]),  # Limit to 3
                    inline=False
                )
        
        if memories["last_interaction"]:
            last_time = time.time() - memories["last_interaction"]
            if last_time < 3600:  # Less than an hour
                time_str = f"{int(last_time // 60)} minutes ago"
            elif last_time < 86400:  # Less than a day
                time_str = f"{int(last_time // 3600)} hours ago"
            else:
                time_str = f"{int(last_time // 86400)} days ago"
            
            embed.set_footer(text=f"Last interaction: {time_str}")
        
        await ctx.send(embed=embed)

    @memory.command(name='add')
    @commands.has_permissions(manage_messages=True)
    async def add_note(self, ctx, user: discord.Member, *, note: str):
        """Add a custom note about a user"""
        if len(note) > 100:
            await ctx.send("Note is too long! Keep it under 100 characters.")
            return
        
        self.bot.update_user_memory(user.id, "custom_notes", note, append=True)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        await ctx.send(f"✅ Added note about {user.display_name}: '{note}'")

    @memory.command(name='set')
    @commands.has_permissions(manage_messages=True)
    async def set_field(self, ctx, user: discord.Member, field: str, *, value: str):
        """Set a specific memory field for a user"""
        valid_fields = ["name", "nickname", "age", "birthday", "relationship_status", "conversation_style"]
        
        if field not in valid_fields:
            await ctx.send(f"Invalid field! Valid fields: {', '.join(valid_fields)}")
            return
        
        # Convert age to int if needed
        if field == "age":
            try:
                value = int(value)
                if not (5 <= value <= 100):
                    await ctx.send("Age must be between 5 and 100!")
                    return
            except ValueError:
                await ctx.send("Age must be a number!")
                return
        
        self.bot.update_user_memory(user.id, field, value)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        await ctx.send(f"✅ Set {field} for {user.display_name} to: '{value}'")

    @memory.command(name='trust')
    @commands.has_permissions(manage_messages=True)
    async def set_trust(self, ctx, user: discord.Member, trust_level: int):
        """Set trust level for a user (-10 to 10)"""
        if not (-10 <= trust_level <= 10):
            await ctx.send("Trust level must be between -10 and 10!")
            return
        
        self.bot.update_user_memory(user.id, "trust_level", trust_level)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        
        trust_desc = "very high trust" if trust_level > 7 else \
                    "high trust" if trust_level > 3 else \
                    "neutral" if trust_level == 0 else \
                    "low trust" if trust_level > -5 else \
                    "very low trust"
        
        await ctx.send(f"✅ Set trust level for {user.display_name} to {trust_level}/10 ({trust_desc})")

    @memory.command(name='relate')
    @commands.has_permissions(manage_messages=True)
    async def set_relationship(self, ctx, user1: discord.Member, user2: discord.Member, *, relationship: str):
        """Set relationship between two users"""
        if len(relationship) > 50:
            await ctx.send("Relationship description is too long! Keep it under 50 characters.")
            return
        
        self.bot.update_user_relationship(user1.id, user2.id, relationship)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        await ctx.send(f"✅ Set relationship: {user1.display_name} → {user2.display_name} ({relationship})")

    @memory.command(name='shared')
    @commands.has_permissions(manage_messages=True)
    async def add_shared_experience(self, ctx, user1: discord.Member, user2: discord.Member, *, experience: str):
        """Add a shared experience between two users"""
        if len(experience) > 100:
            await ctx.send("Experience description is too long! Keep it under 100 characters.")
            return
        
        self.bot.add_shared_experience(user1.id, user2.id, experience)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        await ctx.send(f"✅ Added shared experience between {user1.display_name} and {user2.display_name}: '{experience}'")

    @memory.command(name='context')
    async def view_context(self, ctx, user: discord.Member = None):
        """View social context for a user"""
        if user is None:
            user = ctx.author
        
        # Get the social context that would be provided to the AI
        context = self.bot.get_shared_context(user.id, ctx.guild.id, ctx.channel.id)
        
        embed = discord.Embed(
            title=f"🌐 Social Context for {user.display_name}",
            color=discord.Color.blue()
        )
        
        if context:
            # Parse and format the context nicely
            context_clean = context.replace("OTHER USERS CONTEXT: ", "")
            parts = context_clean.split(" | ")
            
            for part in parts:
                if ":" in part:
                    key, value = part.split(":", 1)
                    embed.add_field(
                        name=key.strip().title(),
                        value=value.strip(),
                        inline=False
                    )
        else:
            embed.add_field(
                name="No Context Available",
                value="This user has no social connections or recent activity context.",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @memory.command(name='clear')
    @commands.has_permissions(administrator=True)
    async def clear_memory(self, ctx, user: discord.Member):
        """Clear all memories about a user"""
        user_id_str = str(user.id)
        try:
            # Check if user has memories in unified system
            if user_id_str in self.bot.unified_memory.memory_data.get('users', {}):
                # Clear user data from unified memory
                del self.bot.unified_memory.memory_data['users'][user_id_str]
                self.bot.unified_memory.pending_saves = True
                self.bot.unified_memory.save_unified_data()
                await ctx.send(f"✅ Cleared all memories about {user.display_name}")
            else:
                await ctx.send(f"No memories found for {user.display_name}")
        except Exception as e:
            await ctx.send(f"Error clearing memories: {e}")

    @memory.command(name='forget')
    async def forget_conversation(self, ctx, user: discord.Member = None):
        """Clear conversation history with Izumi"""
        if user is None:
            user = ctx.author
        
        # Only allow users to forget their own conversation or admins to forget anyone's
        if user != ctx.author and not ctx.author.guild_permissions.administrator:
            await ctx.send("You can only clear your own conversation history!")
            return
        
        # Get the AI cog to clear chat sessions
        ai_cog = self.bot.get_cog('IzumiAI')
        if ai_cog and user.id in ai_cog.gemini_chat_sessions:
            del ai_cog.gemini_chat_sessions[user.id]
            await ctx.send(f"✅ Cleared conversation history for {user.display_name}")
        else:
            await ctx.send(f"No conversation history found for {user.display_name}")

    @memory.command(name='stats')
    async def memory_stats(self, ctx):
        """Show memory system statistics"""
        # Get user count from unified memory system
        try:
            all_users = self.bot.unified_memory.memory_data.get('users', {})
            total_users = len(all_users)
            
            # Calculate trust levels
            trust_levels = []
            for user_data in all_users.values():
                trust_level = user_data.get('social', {}).get('trust_level', 0)
                trust_levels.append(trust_level)
        except Exception as e:
            total_users = 0
            trust_levels = []
        
        # Get active chats from AI cog
        ai_cog = self.bot.get_cog('IzumiAI')
        active_chats = len(ai_cog.gemini_chat_sessions) if ai_cog else 0
        
        embed = discord.Embed(
            title="📊 Memory System Stats",
            color=discord.Color.blue()
        )
        embed.add_field(name="Users with memories", value=str(total_users), inline=True)
        embed.add_field(name="Active chat sessions", value=str(active_chats), inline=True)
        
        if total_users > 0 and trust_levels:
            # Calculate trust level distribution
            avg_trust = sum(trust_levels) / len(trust_levels)
            embed.add_field(name="Average trust level", value=f"{avg_trust:.1f}/10", inline=True)
        
        await ctx.send(embed=embed)

    @memory.command(name='export')
    @commands.has_permissions(administrator=True)
    async def export_memories(self, ctx):
        """Export all memories as JSON (admin only)"""
        try:
            # Get all memory data from unified system
            all_data = self.bot.unified_memory.memory_data
            
            if not all_data or not all_data.get('users'):
                await ctx.send("No memories to export!")
                return
            
            # Create a formatted JSON string
            json_data = json.dumps(all_data, indent=2, ensure_ascii=False)
        except Exception as e:
            await ctx.send(f"Error accessing memory data: {e}")
            return
        
        # Create a file and send it
        file_content = f"# Izumi's Memory Export\n# Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{json_data}"
        
        import io
        file_buffer = io.StringIO(file_content)
        file = discord.File(file_buffer, filename="izumi_memories.json")
        
        await ctx.send("📁 Here's the memory export:", file=file)

    @memory.command(name='self')
    async def view_self_memories(self, ctx):
        """View Izumi's self-memories"""
        self_memories = self.bot.get_izumi_self_memories()
        
        embed = discord.Embed(
            title="🤖 Izumi's Self-Memories",
            description="What Izumi knows about herself",
            color=discord.Color.pink()
        )
        
        # Show each category that has content
        for category, values in self_memories.items():
            if values:  # Only show categories with content
                category_name = category.replace('_', ' ').title()
                if isinstance(values, list):
                    content = ", ".join(values) if len(", ".join(values)) <= 1000 else ", ".join(values)[:997] + "..."
                else:
                    content = str(values)
                
                embed.add_field(
                    name=category_name,
                    value=content,
                    inline=False
                )
        
        if not any(self_memories.values()):
            embed.add_field(
                name="No memories yet!",
                value="Use `!memory selfadd <category> <value>` to add some memories about Izumi!",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @memory.command(name='selftest')
    @commands.has_permissions(manage_messages=True)
    async def test_self_memories(self, ctx):
        """Test if self-memories are being retrieved correctly"""
        # Test the unified memory system
        self_memories = self.bot.unified_memory.get_izumi_self_memories()
        
        # Test the bot's formatting method
        formatted_self = self.bot.format_izumi_self_for_ai()
        
        embed = discord.Embed(
            title="🧪 Self-Memory System Test",
            color=discord.Color.orange()
        )
        
        # Show raw data
        total_items = sum(len(values) if isinstance(values, list) else (1 if values else 0) for values in self_memories.values())
        embed.add_field(
            name="Raw Memory Data",
            value=f"Categories with data: {len([k for k, v in self_memories.items() if v])}\nTotal items: {total_items}",
            inline=False
        )
        
        # Show character count info
        if formatted_self:
            embed.add_field(
                name="AI Data Stats",
                value=f"Full length: {len(formatted_self)} characters\nLines: {len(formatted_self.split(chr(10)))}\nIs truncated below: {'Yes' if len(formatted_self) > 1000 else 'No'}",
                inline=False
            )
            
            # Show formatted output (truncated for Discord)
            formatted_display = formatted_self[:1000] + "..." if len(formatted_self) > 1000 else formatted_self
            embed.add_field(
                name="Formatted for AI (Discord Preview - May Be Truncated)",
                value=f"```{formatted_display}```",
                inline=False
            )
        else:
            embed.add_field(
                name="Formatted for AI",
                value="❌ No formatted output (this is the problem!)",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
        # If the data was truncated, offer to send the full version
        if formatted_self and len(formatted_self) > 1000:
            await ctx.send("📄 **Full AI Data (EXACTLY what Izumi sees):**")
            
            # Split into chunks if needed for Discord's 2000 character limit
            chunks = []
            current_chunk = ""
            
            for line in formatted_self.split('\n'):
                if len(current_chunk + line + '\n') > 1900:  # Leave some room
                    chunks.append(current_chunk)
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # Send each chunk
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await ctx.send(f"```\n{chunk}\n```")
                else:
                    await ctx.send(f"```\n{chunk}\n```")

    @memory.command(name='selfadd')
    @commands.has_permissions(manage_messages=True)
    async def add_self_memory(self, ctx, category: str, *, value: str):
        """Add a memory about Izumi herself"""
        valid_categories = [
            "personality_traits", "likes", "dislikes", "backstory", "goals",
            "fears", "hobbies", "favorite_things", "pet_peeves", "life_philosophy",
            "memories", "relationships", "skills", "dreams", "quirks", "knowledge"
        ]
        
        if category not in valid_categories:
            await ctx.send(f"Invalid category! Valid categories: {', '.join(valid_categories)}")
            return
        
        if len(value) > 200:
            await ctx.send("Memory is too long! Keep it under 200 characters.")
            return
        
        self.bot.update_izumi_self_memory(category, value, append=True)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        category_name = category.replace('_', ' ').title()
        await ctx.send(f"✅ Added to Izumi's {category_name}: '{value}'")

    @memory.command(name='selfclear')
    @commands.has_permissions(administrator=True)
    async def clear_self_memory(self, ctx, category: str):
        """Clear a category of Izumi's self-memories (admin only)"""
        valid_categories = [
            "personality_traits", "likes", "dislikes", "backstory", "goals",
            "fears", "hobbies", "favorite_things", "pet_peeves", "life_philosophy",
            "memories", "relationships", "skills", "dreams", "quirks", "knowledge"
        ]
        
        if category not in valid_categories:
            await ctx.send(f"Invalid category! Valid categories: {', '.join(valid_categories)}")
            return
        
        self_memories = self.bot.get_izumi_self_memories()
        if category in self_memories:
            self_memories[category] = []
            self.bot.pending_saves = True
            await self.bot.save_immediately()  # Force immediate save for real-time updates
            category_name = category.replace('_', ' ').title()
            await ctx.send(f"✅ Cleared Izumi's {category_name} memories")
        else:
            await ctx.send(f"No memories found in category: {category}")

    @memory.command(name='knowledge')
    @commands.has_permissions(manage_messages=True)
    async def add_knowledge(self, ctx, *, info: str):
        """Add general knowledge/information for Izumi to remember"""
        if len(info) > 300:
            await ctx.send("Knowledge entry is too long! Keep it under 300 characters.")
            return
        
        # Add to the 'knowledge' category in self-memories
        self.bot.update_izumi_self_memory("knowledge", info, append=True)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        await ctx.send(f"✅ Added to Izumi's knowledge: '{info}'")

    @memory.command(name='cleanup')
    @commands.has_permissions(administrator=True)
    async def cleanup_duplicates(self, ctx, user: discord.Member = None):
        """Remove duplicate entries from memory data (Admin only)"""
        if user:
            users_to_clean = [user.id]
        else:
            # Clean all users
            try:
                all_users = self.bot.unified_memory.memory_data.get('users', {})
                users_to_clean = [int(uid) for uid in all_users.keys()]
            except:
                await ctx.send("Error accessing memory data!")
                return
        
        cleaned_count = 0
        for user_id in users_to_clean:
            try:
                user_id_str = str(user_id)
                if user_id_str not in self.bot.unified_memory.memory_data['users']:
                    continue
                    
                user_data = self.bot.unified_memory.memory_data['users'][user_id_str]
                cleaned = False
                
                # Clean list fields in personality section
                personality_fields = ['interests', 'dislikes', 'personality_notes']
                for field in personality_fields:
                    if field in user_data['personality'] and isinstance(user_data['personality'][field], list):
                        original_list = user_data['personality'][field]
                        original_length = len(original_list)
                        # Remove duplicates while preserving order
                        cleaned_list = []
                        for item in original_list:
                            if item and item not in cleaned_list:  # Also skip empty items
                                cleaned_list.append(item)
                        
                        if len(cleaned_list) != original_length:
                            user_data['personality'][field] = cleaned_list
                            cleaned = True
                            print(f"Cleaned {field} for user {user_id}: {original_length} -> {len(cleaned_list)}")
                
                # Clean list fields in activity section
                activity_fields = ['custom_notes', 'important_events']
                for field in activity_fields:
                    if field in user_data['activity'] and isinstance(user_data['activity'][field], list):
                        original_list = user_data['activity'][field]
                        original_length = len(original_list)
                        # Remove duplicates while preserving order
                        cleaned_list = []
                        for item in original_list:
                            if item and item not in cleaned_list:  # Also skip empty items
                                cleaned_list.append(item)
                        
                        if len(cleaned_list) != original_length:
                            user_data['activity'][field] = cleaned_list
                            cleaned = True
                            print(f"Cleaned {field} for user {user_id}: {original_length} -> {len(cleaned_list)}")
                
                if cleaned:
                    cleaned_count += 1
            
            except Exception as e:
                print(f"Error cleaning user {user_id}: {e}")
                continue
        
        if cleaned_count > 0:
            # Save cleaned data
            self.bot.unified_memory.pending_saves = True
            self.bot.unified_memory.save_unified_data()
            await ctx.send(f"✅ Cleaned duplicate entries for {cleaned_count} users!")
        else:
            await ctx.send("No duplicates found to clean.")

    @memory.command(name='debug')
    @commands.has_permissions(administrator=True)
    async def debug_memory(self, ctx, user: discord.Member):
        """Debug memory data for a user (Admin only)"""
        memories = self.bot.get_user_memories(user.id)
        
        # Create debug output
        debug_info = []
        debug_info.append(f"🔍 **Memory Debug for {user.display_name}**\n")
        
        for key, value in memories.items():
            value_type = type(value).__name__
            if isinstance(value, list):
                debug_info.append(f"**{key}** ({value_type}): {len(value)} items")
                if len(value) > 10:  # Suspicious large lists
                    debug_info.append(f"  ⚠️ Large list detected!")
                    # Show first few and last few items
                    preview_items = value[:3] + ["..."] + value[-3:] if len(value) > 6 else value
                    debug_info.append(f"  Sample: {preview_items}")
            elif isinstance(value, dict):
                debug_info.append(f"**{key}** ({value_type}): {len(value)} keys")
                if len(value) > 20:  # Suspicious large dicts
                    debug_info.append(f"  ⚠️ Large dict detected!")
            elif isinstance(value, str):
                debug_info.append(f"**{key}** ({value_type}): {len(value)} chars")
                if len(value) > 1000:  # Suspicious large strings
                    debug_info.append(f"  ⚠️ Large string detected!")
                    debug_info.append(f"  Preview: {value[:100]}...")
            else:
                debug_info.append(f"**{key}** ({value_type}): {value}")
        
        debug_text = "\n".join(debug_info)
        
        # Split into chunks if too long
        if len(debug_text) > 1900:
            chunks = [debug_text[i:i+1900] for i in range(0, len(debug_text), 1900)]
            for i, chunk in enumerate(chunks):
                await ctx.send(f"```\nDebug Info (Part {i+1}/{len(chunks)}):\n{chunk}\n```")
        else:
            await ctx.send(f"```\n{debug_text}\n```")

    @memory.command(name='viewknowledge')
    async def view_knowledge(self, ctx):
        """View all stored general knowledge"""
        self_memories = self.bot.get_izumi_self_memories()
        knowledge_list = self_memories.get("knowledge", [])
        
        if not knowledge_list:
            await ctx.send("No general knowledge stored yet! Use `!memory knowledge <info>` to add some.")
            return
        
        embed = discord.Embed(
            title="📚 Izumi's General Knowledge",
            description="Information Izumi has been taught",
            color=discord.Color.green()
        )
        
        # Split knowledge into chunks for Discord embed limits
        knowledge_text = "\n".join([f"• {item}" for item in knowledge_list])
        
        if len(knowledge_text) <= 4000:
            embed.add_field(
                name="Knowledge Database",
                value=knowledge_text,
                inline=False
            )
        else:
            # Split into multiple fields if too long
            chunks = []
            current_chunk = ""
            for item in knowledge_list:
                line = f"• {item}\n"
                if len(current_chunk + line) > 1000:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += line
            
            if current_chunk:
                chunks.append(current_chunk)
            
            for i, chunk in enumerate(chunks[:3]):  # Limit to 3 fields max
                embed.add_field(
                    name=f"Knowledge Database (Part {i+1})",
                    value=chunk,
                    inline=False
                )
            
            if len(chunks) > 3:
                embed.set_footer(text=f"... and {len(knowledge_list) - sum(len(chunk.split('\n')) for chunk in chunks[:3])} more entries")
        
        embed.set_footer(text=f"Total entries: {len(knowledge_list)}")
        await ctx.send(embed=embed)
    
    @memory.command(name='decay_trust')
    @commands.has_permissions(administrator=True)
    async def decay_trust_levels(self, ctx):
        """Manually trigger trust level decay for inactive users (Admin only)"""
        await ctx.send("🔄 Running trust level decay for inactive users...")
        
        try:
            await self.bot.unified_memory.decay_inactive_trust_levels()
            await ctx.send("✅ Trust level decay completed! Check console for details.")
        except Exception as e:
            await ctx.send(f"❌ Error during trust decay: {e}")
    
    @memory.command(name='emotion_test')
    @commands.has_permissions(administrator=True)
    async def test_emotional_context(self, ctx, user: discord.Member = None):
        """Test emotional context system for a user (Admin only)"""
        target_user = user if user else ctx.author
        
        try:
            emotional_context = self.bot.unified_memory.get_emotional_context(target_user.id, ctx.guild.id)
            
            embed = discord.Embed(
                title=f"🧠 Emotional Context for {target_user.display_name}",
                color=0xFF69B4
            )
            
            embed.add_field(
                name="Context Type",
                value=emotional_context["type"],
                inline=False
            )
            
            if emotional_context.get("message"):
                embed.add_field(
                    name="Emotional Response",
                    value=emotional_context["message"],
                    inline=False
                )
            
            if emotional_context.get("days_absent"):
                embed.add_field(
                    name="Days Absent",
                    value=f"{emotional_context['days_absent']} days",
                    inline=True
                )
            
            if emotional_context.get("days_ignored"):
                embed.add_field(
                    name="Days Ignored",
                    value=f"{emotional_context['days_ignored']} days", 
                    inline=True
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error testing emotional context: {e}")
    
    # Conversation Participation Commands
    @commands.hybrid_command(name='convo_enable')
    @commands.has_permissions(administrator=True)
    async def enable_conversation_participation(self, ctx, channel: discord.TextChannel = None):
        """Enable Izumi to participate in active conversations in a channel (Admin only)"""
        target_channel = channel if channel else ctx.channel
        
        try:
            # Add channel with default settings
            self.bot.unified_memory.add_conversation_channel(target_channel.id)
            
            embed = discord.Embed(
                title="🎭 Conversation Participation Enabled",
                description=f"Izumi will now participate in active conversations in {target_channel.mention}",
                color=0x00ff00
            )
            
            embed.add_field(
                name="Settings",
                value="• Min messages: 5\n• Time window: 5 minutes\n• Min users: 2\n• Participation chance: 30%\n• Cooldown: 10 minutes",
                inline=False
            )
            
            embed.add_field(
                name="Usage",
                value="Izumi will automatically detect active conversations and occasionally join in naturally!",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error enabling conversation participation: {e}")
    
    @commands.hybrid_command(name='convo_disable')
    @commands.has_permissions(administrator=True)
    async def disable_conversation_participation(self, ctx, channel: discord.TextChannel = None):
        """Disable Izumi's conversation participation in a channel (Admin only)"""
        target_channel = channel if channel else ctx.channel
        
        try:
            success = self.bot.unified_memory.remove_conversation_channel(target_channel.id)
            
            if success:
                embed = discord.Embed(
                    title="🎭 Conversation Participation Disabled",
                    description=f"Izumi will no longer participate in conversations in {target_channel.mention}",
                    color=0xff6b6b
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Conversation participation was not enabled in {target_channel.mention}")
                
        except Exception as e:
            await ctx.send(f"❌ Error disabling conversation participation: {e}")
    
    @commands.hybrid_command(name='convo_list')
    @commands.has_permissions(administrator=True)
    async def list_conversation_channels(self, ctx):
        """List all channels with conversation participation enabled (Admin only)"""
        try:
            conversation_channels = self.bot.unified_memory.memory_data.get('conversation_channels', {})
            
            if not conversation_channels:
                await ctx.send("📋 No channels have conversation participation enabled.")
                return
            
            embed = discord.Embed(
                title="🎭 Conversation Participation Channels",
                color=0x9966ff
            )
            
            for channel_id_str, settings in conversation_channels.items():
                try:
                    channel = self.bot.get_channel(int(channel_id_str))
                    if channel:
                        last_participation = settings.get('last_participation', 0)
                        if last_participation > 0:
                            import time
                            time_since = int(time.time() - last_participation)
                            last_info = f"Last joined: {time_since}s ago"
                        else:
                            last_info = "Never joined"
                        
                        embed.add_field(
                            name=f"#{channel.name}",
                            value=f"Chance: {int(settings['participation_chance']*100)}%\n{last_info}",
                            inline=True
                        )
                except:
                    continue
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error listing conversation channels: {e}")
    
    @commands.hybrid_command(name='convo_settings')
    @commands.has_permissions(administrator=True)
    async def configure_conversation_settings(self, ctx, channel: discord.TextChannel = None, 
                                           min_messages: int = None, participation_chance: float = None):
        """Configure conversation participation settings for a channel (Admin only)"""
        target_channel = channel if channel else ctx.channel
        
        try:
            if not self.bot.unified_memory.is_conversation_participation_enabled(target_channel.id):
                await ctx.send(f"❌ Conversation participation is not enabled in {target_channel.mention}. Use `/convo_enable` first.")
                return
            
            channel_id_str = str(target_channel.id)
            settings = self.bot.unified_memory.memory_data['conversation_channels'][channel_id_str]
            
            # Update settings if provided
            updated = []
            if min_messages is not None and 1 <= min_messages <= 20:
                settings['min_messages'] = min_messages
                updated.append(f"Min messages: {min_messages}")
            
            if participation_chance is not None and 0.0 <= participation_chance <= 1.0:
                settings['participation_chance'] = participation_chance
                updated.append(f"Participation chance: {int(participation_chance*100)}%")
            
            if updated:
                self.bot.unified_memory.pending_saves = True
                update_text = "\n".join(updated)
            else:
                update_text = "No valid updates provided"
            
            embed = discord.Embed(
                title=f"🎭 Conversation Settings - #{target_channel.name}",
                color=0x9966ff
            )
            
            embed.add_field(
                name="Current Settings",
                value=f"• Min messages: {settings['min_messages']}\n"
                      f"• Time window: {settings['time_window']//60} minutes\n"
                      f"• Min users: {settings['min_users']}\n" 
                      f"• Participation chance: {int(settings['participation_chance']*100)}%\n"
                      f"• Cooldown: {settings['cooldown']//60} minutes",
                inline=False
            )
            
            if updated:
                embed.add_field(name="Updated", value=update_text, inline=False)
            
            embed.add_field(
                name="Usage",
                value="`/convo_settings #channel min_messages:5 participation_chance:0.3`",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error configuring conversation settings: {e}")
    
    @commands.hybrid_command(name='convo_test')
    @commands.has_permissions(administrator=True)
    async def test_conversation_detection(self, ctx, channel: discord.TextChannel = None):
        """Test conversation detection in a channel (Admin only)"""
        target_channel = channel if channel else ctx.channel
        
        try:
            analysis = self.bot.unified_memory.detect_active_conversation(target_channel.id)
            
            embed = discord.Embed(
                title=f"🔍 Conversation Analysis - #{target_channel.name}",
                color=0x00bfff
            )
            
            embed.add_field(
                name="Should Participate",
                value="✅ Yes" if analysis["should_participate"] else "❌ No",
                inline=True
            )
            
            embed.add_field(
                name="Reason",
                value=analysis.get("reason", "analysis_successful"),
                inline=True
            )
            
            if analysis.get("message_count"):
                embed.add_field(
                    name="Recent Activity",
                    value=f"{analysis['message_count']} messages from {len(analysis.get('participants', []))} users",
                    inline=True
                )
            
            if analysis.get("conversation_context"):
                context_preview = analysis["conversation_context"][:200] + "..." if len(analysis["conversation_context"]) > 200 else analysis["conversation_context"]
                embed.add_field(
                    name="Context Preview",
                    value=f"```{context_preview}```",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Error testing conversation detection: {e}")
    
    
    
    @commands.command(name='export_self_memories')
    @commands.has_permissions(administrator=True)
    async def export_self_memories(self, ctx):
        """Export Izumi's self-memories as JSON (admin only)"""
        self_memories = self.bot.get_izumi_self_memories()
        
        if not any(self_memories.values()):
            await ctx.send("No self-memories to export!")
            return
        
        # Create a formatted JSON string
        json_data = json.dumps(self_memories, indent=2, ensure_ascii=False)
        
        # Create a file and send it
        file_content = f"# Izumi's Self-Memory Export\n# Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n{json_data}"
        
        import io
        file_buffer = io.StringIO(file_content)
        file = discord.File(file_buffer, filename="izumi_self_memories.json")
        
        await ctx.send("📁 Here's Izumi's self-memory export:", file=file)

    # ==================== SLASH COMMANDS ====================
    
    @app_commands.command(name="memory_view", description="View memories about a user")
    async def slash_view_memory(self, interaction: discord.Interaction, user: discord.Member = None):
        """View memories about a user (available to everyone)"""
        if user is None:
            user = interaction.user
        
        memories = self.bot.get_user_memories(user.id)
        
        # Check if user has any memories stored
        has_memories = any([
            memories.get("name"),
            memories.get("nickname"), 
            memories.get("age"),
            memories.get("birthday"),
            memories.get("interests"),
            memories.get("personality"),
            memories.get("notes"),
            memories.get("achievements"),
            memories.get("last_seen")
        ])
        
        if not has_memories:
            await interaction.response.send_message(f"No memories stored about {user.display_name} yet!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🧠 Izumi's memories about {user.display_name}",
            color=discord.Color.purple()
        )
        
        # Basic info
        basic_info = []
        if memories["name"]:
            basic_info.append(f"**Name:** {memories['name']}")
        else:
            # Use Discord username as default
            basic_info.append(f"**Name:** {user.display_name} (Discord username)")
        if memories["nickname"]:
            basic_info.append(f"**Nickname:** {memories['nickname']}")
        if memories["age"]:
            basic_info.append(f"**Age:** {memories['age']}")
        if memories["birthday"]:
            basic_info.append(f"**Birthday:** {memories['birthday']}")
        if memories["relationship_status"]:
            basic_info.append(f"**Relationship:** {memories['relationship_status']}")
        
        if basic_info:
            embed.add_field(name="Basic Info", value="\n".join(basic_info), inline=False)
        
        # Personality & preferences (with truncation)
        if memories["interests"]:
            interests_text = ", ".join(memories["interests"])
            embed.add_field(
                name="Interests", 
                value=self._truncate_field_value(interests_text), 
                inline=False
            )
        
        if memories["dislikes"]:
            dislikes_text = ", ".join(memories["dislikes"])
            embed.add_field(
                name="Dislikes", 
                value=self._truncate_field_value(dislikes_text), 
                inline=False
            )
        
        if memories["personality_notes"]:
            personality_text = ", ".join(memories["personality_notes"])
            embed.add_field(
                name="Personality Notes", 
                value=self._truncate_field_value(personality_text), 
                inline=False
            )
        
        # Trust level with emoji
        trust = memories["trust_level"]
        trust_emoji = "💚" if trust > 5 else "💛" if trust > 0 else "❤️" if trust == 0 else "🧡" if trust > -5 else "💔"
        embed.add_field(
            name="Trust Level", 
            value=f"{trust_emoji} {trust}/10", 
            inline=True
        )
        
        # Other info (with truncation)
        if memories["conversation_style"]:
            embed.add_field(
                name="Communication Style", 
                value=self._truncate_field_value(memories["conversation_style"]), 
                inline=True
            )
        
        if memories["important_events"]:
            events_text = "\n".join(memories["important_events"])
            embed.add_field(
                name="Important Events", 
                value=self._truncate_field_value(events_text), 
                inline=False
            )
        
        if memories["custom_notes"]:
            notes_text = "\n".join(memories["custom_notes"])
            embed.add_field(
                name="Custom Notes", 
                value=self._truncate_field_value(notes_text), 
                inline=False
            )
        
        # Social connections (with truncation)
        if memories.get("relationships"):
            relationship_info = []
            for other_user_id_str, relationship in memories["relationships"].items():
                try:
                    other_user_id = int(other_user_id_str)
                    other_user = interaction.guild.get_member(other_user_id)
                    if other_user:
                        relationship_info.append(f"{other_user.display_name} ({relationship})")
                except:
                    continue
            
            if relationship_info:
                rel_text = "\n".join(relationship_info[:5])  # Limit to 5
                embed.add_field(
                    name="Known Relationships",
                    value=self._truncate_field_value(rel_text),
                    inline=False
                )
        
        if memories.get("shared_experiences"):
            shared_info = []
            for other_user_id_str, experiences in memories["shared_experiences"].items():
                try:
                    other_user_id = int(other_user_id_str)
                    other_user = interaction.guild.get_member(other_user_id)
                    if other_user and experiences:
                        recent_experiences = experiences[-2:]  # Last 2 experiences
                        exp_text = '; '.join(recent_experiences)
                        # Truncate each experience entry to avoid field overflow
                        if len(exp_text) > 150:  # Limit per user
                            exp_text = exp_text[:147] + "..."
                        shared_info.append(f"**{other_user.display_name}:** {exp_text}")
                except:
                    continue
            
            if shared_info:
                shared_text = "\n".join(shared_info[:3])  # Limit to 3
                embed.add_field(
                    name="Shared Experiences",
                    value=self._truncate_field_value(shared_text),
                    inline=False
                )
        
        if memories["last_interaction"]:
            last_time = time.time() - memories["last_interaction"]
            if last_time < 3600:  # Less than an hour
                time_str = f"{int(last_time // 60)} minutes ago"
            elif last_time < 86400:  # Less than a day
                time_str = f"{int(last_time // 3600)} hours ago"
            else:
                time_str = f"{int(last_time // 86400)} days ago"
            
            embed.set_footer(text=f"Last interaction: {time_str}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="memory_add", description="Add a custom note about a user")
    async def slash_add_note(self, interaction: discord.Interaction, user: discord.Member, note: str):
        """Add a custom note about a user (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        if len(note) > 100:
            await interaction.response.send_message("Note is too long! Keep it under 100 characters.", ephemeral=True)
            return
        
        self.bot.update_user_memory(user.id, "custom_notes", note, append=True)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        await interaction.response.send_message(f"✅ Added note about {user.display_name}: '{note}'", ephemeral=True)

    @app_commands.command(name="memory_set", description="Set a specific memory field for a user")
    @app_commands.describe(
        user="The user to update",
        field="The field to set (name, nickname, age, birthday, relationship_status, conversation_style)",
        value="The value to set"
    )
    async def slash_set_field(self, interaction: discord.Interaction, user: discord.Member, field: str, value: str):
        """Set a specific memory field for a user (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        valid_fields = ["name", "nickname", "age", "birthday", "relationship_status", "conversation_style"]
        
        if field not in valid_fields:
            await interaction.response.send_message(f"Invalid field! Valid fields: {', '.join(valid_fields)}", ephemeral=True)
            return
        
        # Convert age to int if needed
        if field == "age":
            try:
                value = int(value)
                if not (5 <= value <= 100):
                    await interaction.response.send_message("Age must be between 5 and 100!", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("Age must be a number!", ephemeral=True)
                return
        
        self.bot.update_user_memory(user.id, field, value)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        await interaction.response.send_message(f"✅ Set {field} for {user.display_name} to: '{value}'", ephemeral=True)

    @app_commands.command(name="memory_trust", description="Set trust level for a user")
    @app_commands.describe(
        user="The user to update",
        trust_level="Trust level (-10 to 10)"
    )
    async def slash_set_trust(self, interaction: discord.Interaction, user: discord.Member, trust_level: int):
        """Set trust level for a user (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        if not (-10 <= trust_level <= 10):
            await interaction.response.send_message("Trust level must be between -10 and 10!", ephemeral=True)
            return
        
        self.bot.update_user_memory(user.id, "trust_level", trust_level)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        
        trust_desc = "very high trust" if trust_level > 7 else \
                    "high trust" if trust_level > 3 else \
                    "neutral" if trust_level == 0 else \
                    "low trust" if trust_level > -5 else \
                    "very low trust"
        
        await interaction.response.send_message(f"✅ Set trust level for {user.display_name} to {trust_level}/10 ({trust_desc})", ephemeral=True)

    @app_commands.command(name="memory_relate", description="Set relationship between two users")
    @app_commands.describe(
        user1="First user",
        user2="Second user", 
        relationship="Relationship type (friend, sibling, teammate, etc.)"
    )
    async def slash_set_relationship(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member, relationship: str):
        """Set relationship between two users (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        if len(relationship) > 50:
            await interaction.response.send_message("Relationship description is too long! Keep it under 50 characters.", ephemeral=True)
            return
        
        self.bot.update_user_relationship(user1.id, user2.id, relationship)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        await interaction.response.send_message(f"✅ Set relationship: {user1.display_name} → {user2.display_name} ({relationship})", ephemeral=True)

    @app_commands.command(name="memory_shared", description="Add a shared experience between two users")
    @app_commands.describe(
        user1="First user",
        user2="Second user",
        experience="Description of shared experience"
    )
    async def slash_add_shared_experience(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member, experience: str):
        """Add a shared experience between two users (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        if len(experience) > 100:
            await interaction.response.send_message("Experience description is too long! Keep it under 100 characters.", ephemeral=True)
            return
        
        self.bot.add_shared_experience(user1.id, user2.id, experience)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        await interaction.response.send_message(f"✅ Added shared experience between {user1.display_name} and {user2.display_name}: '{experience}'", ephemeral=True)

    @app_commands.command(name="memory_context", description="View social context for a user")
    async def slash_view_context(self, interaction: discord.Interaction, user: discord.Member = None):
        """View social context for a user (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        if user is None:
            user = interaction.user
        
        # Get the social context that would be provided to the AI
        context = self.bot.get_shared_context(user.id, interaction.guild.id, interaction.channel.id)
        
        embed = discord.Embed(
            title=f"🌐 Social Context for {user.display_name}",
            color=discord.Color.blue()
        )
        
        if context:
            # Parse and format the context nicely
            context_clean = context.replace("OTHER USERS CONTEXT: ", "")
            parts = context_clean.split(" | ")
            
            for part in parts:
                if ":" in part:
                    key, value = part.split(":", 1)
                    embed.add_field(
                        name=key.strip().title(),
                        value=value.strip(),
                        inline=False
                    )
        else:
            embed.add_field(
                name="No Context Available",
                value="This user has no social connections or recent activity context.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="memory_clear", description="Clear all memories about a user")
    async def slash_clear_memory(self, interaction: discord.Interaction, user: discord.Member):
        """Clear all memories about a user (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        user_id_str = str(user.id)
        try:
            # Check if user has memories in unified system
            if user_id_str in self.bot.unified_memory.memory_data.get('users', {}):
                # Clear user data from unified memory
                del self.bot.unified_memory.memory_data['users'][user_id_str]
                self.bot.unified_memory.pending_saves = True
                self.bot.unified_memory.save_unified_data()
                await interaction.response.send_message(f"✅ Cleared all memories about {user.display_name}", ephemeral=True)
            else:
                await interaction.response.send_message(f"No memories found for {user.display_name}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error clearing memories: {e}", ephemeral=True)

    @app_commands.command(name="memory_forget", description="Clear conversation history with Izumi")
    async def slash_forget_conversation(self, interaction: discord.Interaction, user: discord.Member = None):
        """Clear conversation history with Izumi (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        if user is None:
            user = interaction.user
        
        # Get the AI cog to clear chat sessions
        ai_cog = self.bot.get_cog('IzumiAI')
        if ai_cog and user.id in ai_cog.gemini_chat_sessions:
            del ai_cog.gemini_chat_sessions[user.id]
            await interaction.response.send_message(f"✅ Cleared conversation history for {user.display_name}", ephemeral=True)
        else:
            await interaction.response.send_message(f"No conversation history found for {user.display_name}", ephemeral=True)

    @app_commands.command(name="memory_self", description="View Izumi's self-memories")
    async def slash_view_self_memories(self, interaction: discord.Interaction):
        """View Izumi's self-memories (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        self_memories = self.bot.get_izumi_self_memories()
        
        embed = discord.Embed(
            title="🤖 Izumi's Self-Memories",
            description="What Izumi knows about herself",
            color=discord.Color.pink()
        )
        
        # Show each category that has content
        for category, values in self_memories.items():
            if values:  # Only show categories with content
                category_name = category.replace('_', ' ').title()
                if isinstance(values, list):
                    content = ", ".join(values) if len(", ".join(values)) <= 1000 else ", ".join(values)[:997] + "..."
                else:
                    content = str(values)
                
                embed.add_field(
                    name=category_name,
                    value=content,
                    inline=False
                )
        
        if not any(self_memories.values()):
            embed.add_field(
                name="No memories yet!",
                value="Use `/memory_selfadd` to add some memories about Izumi!",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="memory_selftest", description="Test if self-memories are being retrieved correctly")
    async def slash_test_self_memories(self, interaction: discord.Interaction):
        """Test if self-memories are being retrieved correctly (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        # Test the unified memory system
        self_memories = self.bot.unified_memory.get_izumi_self_memories()
        
        # Test the bot's formatting method
        formatted_self = self.bot.format_izumi_self_for_ai()
        
        embed = discord.Embed(
            title="🧪 Self-Memory System Test",
            color=discord.Color.orange()
        )
        
        # Show raw data
        total_items = sum(len(values) if isinstance(values, list) else (1 if values else 0) for values in self_memories.values())
        embed.add_field(
            name="Raw Memory Data",
            value=f"Categories with data: {len([k for k, v in self_memories.items() if v])}\nTotal items: {total_items}",
            inline=False
        )
        
        # Show character count info
        if formatted_self:
            embed.add_field(
                name="AI Data Stats",
                value=f"Full length: {len(formatted_self)} characters\nLines: {len(formatted_self.split(chr(10)))}\nIs truncated below: {'Yes' if len(formatted_self) > 1000 else 'No'}",
                inline=False
            )
            
            # Show formatted output (truncated for Discord)
            formatted_display = formatted_self[:1000] + "..." if len(formatted_self) > 1000 else formatted_self
            embed.add_field(
                name="Formatted for AI (Discord Preview - May Be Truncated)",
                value=f"```{formatted_display}```",
                inline=False
            )
        else:
            embed.add_field(
                name="Formatted for AI",
                value="❌ No formatted output (this is the problem!)",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # If the data was truncated, send the full version
        if formatted_self and len(formatted_self) > 1000:
            await interaction.followup.send("📄 **Full AI Data (EXACTLY what Izumi sees):**", ephemeral=True)
            
            # Split into chunks if needed for Discord's 2000 character limit
            chunks = []
            current_chunk = ""
            
            for line in formatted_self.split('\n'):
                if len(current_chunk + line + '\n') > 1900:  # Leave some room
                    chunks.append(current_chunk)
                    current_chunk = line + '\n'
                else:
                    current_chunk += line + '\n'
            
            if current_chunk:
                chunks.append(current_chunk)
            
            # Send each chunk
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(f"```\n{chunk}\n```", ephemeral=True)
                else:
                    await interaction.followup.send(f"```\n{chunk}\n```", ephemeral=True)

    @app_commands.command(name="memory_selfadd", description="Add a memory about Izumi herself")
    @app_commands.describe(
        category="Category (personality_traits, likes, dislikes, backstory, goals, fears, hobbies, etc.)",
        value="Memory content"
    )
    async def slash_add_self_memory(self, interaction: discord.Interaction, category: str, value: str):
        """Add a memory about Izumi herself (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        valid_categories = [
            "personality_traits", "likes", "dislikes", "backstory", "goals",
            "fears", "hobbies", "favorite_things", "pet_peeves", "life_philosophy",
            "memories", "relationships", "skills", "dreams", "quirks", "knowledge"
        ]
        
        if category not in valid_categories:
            await interaction.response.send_message(f"Invalid category! Valid categories: {', '.join(valid_categories)}", ephemeral=True)
            return
        
        if len(value) > 200:
            await interaction.response.send_message("Memory is too long! Keep it under 200 characters.", ephemeral=True)
            return
        
        self.bot.update_izumi_self_memory(category, value, append=True)
        await self.bot.save_immediately()  # Force immediate save for real-time updates
        category_name = category.replace('_', ' ').title()
        await interaction.response.send_message(f"✅ Added to Izumi's {category_name}: '{value}'", ephemeral=True)

    @app_commands.command(name="memory_selfclear", description="Clear a category of Izumi's self-memories")
    @app_commands.describe(
        category="Category to clear"
    )
    async def slash_clear_self_memory(self, interaction: discord.Interaction, category: str):
        """Clear a category of Izumi's self-memories (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
            
        valid_categories = [
            "personality_traits", "likes", "dislikes", "backstory", "goals",
            "fears", "hobbies", "favorite_things", "pet_peeves", "life_philosophy",
            "memories", "relationships", "skills", "dreams", "quirks", "knowledge"
        ]
        
        if category not in valid_categories:
            await interaction.response.send_message(f"Invalid category! Valid categories: {', '.join(valid_categories)}", ephemeral=True)
            return
        
        self_memories = self.bot.get_izumi_self_memories()
        if category in self_memories:
            self_memories[category] = []
            self.bot.pending_saves = True
            await self.bot.save_immediately()  # Force immediate save for real-time updates
            category_name = category.replace('_', ' ').title()
            await interaction.response.send_message(f"✅ Cleared Izumi's {category_name} memories", ephemeral=True)
        else:
            await interaction.response.send_message(f"No memories found in category: {category}", ephemeral=True)

    @commands.command(name='train')
    async def train_on_history(self, ctx, channel: discord.TextChannel = None, limit: int = 10000):
        """Train Izumi on historical messages in a channel"""
        # Only allow bot owner to run this
        if ctx.author.id != BOT_OWNER_ID:
            await ctx.send("❌ Only the bot owner can run training commands.")
            return
        
        if channel is None:
            channel = ctx.channel
        
        # Get the learning engine (unified memory system)
        ai_cog = self.bot.get_cog('IzumiAI')
        if not ai_cog or not hasattr(ai_cog, 'learning_engine'):
            await ctx.send("❌ AI learning system not available.")
            return
        
        unified_memory = ai_cog.learning_engine  # This now references the unified memory system  # This is now the unified memory system
        
        # Send initial message
        status_msg = await ctx.send(f"🧠 Starting training on {channel.mention}...\n📊 Limit: {limit} messages")
        
        processed = 0
        learned = 0
        
        try:
            # Get messages (Discord API limit is 100 per call)
            async for message in channel.history(limit=limit, oldest_first=False):
                # Skip bot messages
                if message.author.bot:
                    continue
                
                # Skip commands and prefixed messages
                content = message.content.strip()
                if not content:
                    continue
                
                # Skip messages that start with common command prefixes
                skip_prefixes = ['!', '/', '?', '<', '>', '$', '%', '&', '*', '+', '=', '~', '`', '@everyone', '@here']
                if any(content.startswith(prefix) for prefix in skip_prefixes):
                    continue
                
                # Skip messages that are just URLs
                if content.startswith('http://') or content.startswith('https://'):
                    continue
                
                # Skip very short messages (less than 3 characters)
                if len(content) < 3:
                    continue
                
                try:
                    # Process the message through the unified memory system
                    await unified_memory.learn_from_message(message)
                    learned += 1
                except Exception as e:
                    print(f"Error learning from message {message.id}: {e}")
                
                processed += 1
                
                # Update status every 100 messages
                if processed % 100 == 0:
                    try:
                        await status_msg.edit(content=f"🧠 Training in progress...\n📊 Processed: {processed}/{limit}\n✅ Learned from: {learned} messages")
                    except:
                        pass  # Message might be deleted
            
            # Save unified memory data
            unified_memory.save_unified_data()
            
            # Final status
            await status_msg.edit(content=f"✅ Training complete!\n📊 Processed: {processed} messages\n🧠 Learned from: {learned} messages\n💾 Data saved!")
            
        except Exception as e:
            await ctx.send(f"❌ Error during training: {e}")

    @commands.command(name='trainall')
    async def train_all_channels(self, ctx, limit_per_channel: int = 10000):
        """Train Izumi on all channels in the server"""
        # Only allow bot owner to run this
        if ctx.author.id != BOT_OWNER_ID:
            await ctx.send("❌ Only the bot owner can run training commands.")
            return
        
        # Get the learning engine (unified memory system)
        ai_cog = self.bot.get_cog('IzumiAI')
        if not ai_cog or not hasattr(ai_cog, 'learning_engine'):
            await ctx.send("❌ AI learning system not available.")
            return
        
        unified_memory = ai_cog.learning_engine  # This now references the unified memory system  # This is now the unified memory system
        
        # Get all text channels
        text_channels = [ch for ch in ctx.guild.channels if isinstance(ch, discord.TextChannel)]
        
        # Send initial message
        status_msg = await ctx.send(f"🧠 Starting server-wide training...\n📊 Channels: {len(text_channels)}\n📝 Limit per channel: {limit_per_channel}")
        
        total_processed = 0
        total_learned = 0
        channels_done = 0
        
        try:
            for channel in text_channels:
                # Check if bot can read the channel
                if not channel.permissions_for(ctx.guild.me).read_message_history:
                    continue
                
                channel_processed = 0
                channel_learned = 0
                
                try:
                    async for message in channel.history(limit=limit_per_channel, oldest_first=False):
                        # Skip bot messages
                        if message.author.bot:
                            continue
                        
                        # Skip commands and prefixed messages
                        content = message.content.strip()
                        if not content:
                            continue
                        
                        # Skip messages that start with common command prefixes
                        skip_prefixes = ['!', '/', '?', '<', '>', '$', '%', '&', '*', '+', '=', '~', '`', '@everyone', '@here']
                        if any(content.startswith(prefix) for prefix in skip_prefixes):
                            continue
                        
                        # Skip messages that are just URLs
                        if content.startswith('http://') or content.startswith('https://'):
                            continue
                        
                        # Skip very short messages (less than 3 characters)
                        if len(content) < 3:
                            continue
                        
                        try:
                            # Process the message through the unified memory system
                            await unified_memory.learn_from_message(message)
                            channel_learned += 1
                            total_learned += 1
                        except Exception as e:
                            print(f"Error learning from message {message.id}: {e}")
                        
                        channel_processed += 1
                        total_processed += 1
                
                except Exception as e:
                    print(f"Error processing channel {channel.name}: {e}")
                
                channels_done += 1
                
                # Update status every channel
                try:
                    await status_msg.edit(content=f"🧠 Training in progress...\n📊 Channels: {channels_done}/{len(text_channels)}\n📝 Current: #{channel.name}\n✅ Total learned: {total_learned} messages")
                except:
                    pass  # Message might be deleted
            
            # Save unified memory data
            unified_memory.save_unified_data()
            
            # Final status
            await status_msg.edit(content=f"✅ Server-wide training complete!\n📊 Channels processed: {channels_done}\n📝 Total messages: {total_processed}\n🧠 Learned from: {total_learned} messages\n💾 Data saved!")
            
        except Exception as e:
            await ctx.send(f"❌ Error during training: {e}")

    @app_commands.command(name="train", description="Train Izumi on historical messages in a channel")
    @app_commands.describe(
        channel="Channel to train on (defaults to current channel)",
        limit="Maximum number of messages to process (default: 10000)"
    )
    async def slash_train_on_history(self, interaction: discord.Interaction, channel: discord.TextChannel = None, limit: int = 10000):
        """Train Izumi on historical messages in a channel (bot owner only)"""
        # Only allow bot owner to run this
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can run training commands.", ephemeral=True)
            return
        
        if channel is None:
            channel = interaction.channel
        
        # Get the unified memory system
        ai_cog = self.bot.get_cog('IzumiAI')
        if not ai_cog or not hasattr(ai_cog, 'learning_engine'):
            await interaction.response.send_message("❌ AI learning system not available.", ephemeral=True)
            return
        
        unified_memory = ai_cog.learning_engine  # This now references the unified memory system
        
        # Send initial response
        await interaction.response.send_message(f"🧠 Starting training on {channel.mention}...\n📊 Limit: {limit} messages", ephemeral=True)
        
        # Get the interaction message for updates
        try:
            status_msg = await interaction.followup.send(f"🧠 Training in progress...\n📊 Processed: 0/{limit}\n✅ Learned from: 0 messages")
        except:
            status_msg = None
        
        processed = 0
        learned = 0
        
        try:
            # Get messages (Discord API limit is 100 per call)
            async for message in channel.history(limit=limit, oldest_first=False):
                # Skip bot messages
                if message.author.bot:
                    continue
                
                # Skip commands and prefixed messages
                content = message.content.strip()
                if not content:
                    continue
                
                # Skip messages that start with common command prefixes
                skip_prefixes = ['!', '/', '?', '<', '>', '$', '%', '&', '*', '+', '=', '~', '`', '@everyone', '@here']
                if any(content.startswith(prefix) for prefix in skip_prefixes):
                    continue
                
                # Skip messages that are just URLs
                if content.startswith('http://') or content.startswith('https://'):
                    continue
                
                # Skip very short messages (less than 3 characters)
                if len(content) < 3:
                    continue
                
                try:
                    # Process the message through the unified memory system
                    await unified_memory.learn_from_message(message)
                    learned += 1
                except Exception as e:
                    print(f"Error learning from message {message.id}: {e}")
                
                processed += 1
                
                # Update status every 100 messages
                if processed % 100 == 0 and status_msg:
                    try:
                        await status_msg.edit(content=f"🧠 Training in progress...\n📊 Processed: {processed}/{limit}\n✅ Learned from: {learned} messages")
                    except:
                        pass  # Message might be deleted
            
            # Save unified memory data
            unified_memory.save_unified_data()
            
            # Final status
            if status_msg:
                await status_msg.edit(content=f"✅ Training complete!\n📊 Processed: {processed} messages\n🧠 Learned from: {learned} messages\n💾 Data saved!")
            else:
                await interaction.followup.send(f"✅ Training complete!\n📊 Processed: {processed} messages\n🧠 Learned from: {learned} messages\n💾 Data saved!")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during training: {e}")

    @app_commands.command(name="trainall", description="Train Izumi on all channels in the server")
    @app_commands.describe(
        limit_per_channel="Maximum number of messages per channel (default: 10000)"
    )
    async def slash_train_all_channels(self, interaction: discord.Interaction, limit_per_channel: int = 10000):
        """Train Izumi on all channels in the server (bot owner only)"""
        # Only allow bot owner to run this
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can run training commands.", ephemeral=True)
            return
        
        # Get the learning engine
        ai_cog = self.bot.get_cog('IzumiAI')
        if not ai_cog or not hasattr(ai_cog, 'learning_engine'):
            await interaction.response.send_message("❌ AI learning system not available.", ephemeral=True)
            return
        
        unified_memory = ai_cog.learning_engine  # This now references the unified memory system
        
        # Get all text channels
        text_channels = [ch for ch in interaction.guild.channels if isinstance(ch, discord.TextChannel)]
        
        # Send initial response
        await interaction.response.send_message(f"🧠 Starting server-wide training...\n📊 Channels: {len(text_channels)}\n📝 Limit per channel: {limit_per_channel}", ephemeral=True)
        
        # Send followup for status updates
        try:
            status_msg = await interaction.followup.send(f"🧠 Training in progress...\n📊 Channels: 0/{len(text_channels)}\n✅ Total learned: 0 messages")
        except:
            status_msg = None
        
        total_processed = 0
        total_learned = 0
        channels_done = 0
        
        try:
            for channel in text_channels:
                # Check if bot can read the channel
                if not channel.permissions_for(interaction.guild.me).read_message_history:
                    continue
                
                channel_processed = 0
                channel_learned = 0
                
                try:
                    async for message in channel.history(limit=limit_per_channel, oldest_first=False):
                        # Skip bot messages
                        if message.author.bot:
                            continue
                        
                        # Skip commands and prefixed messages
                        content = message.content.strip()
                        if not content:
                            continue
                        
                        # Skip messages that start with common command prefixes
                        skip_prefixes = ['!', '/', '?', '<', '>', '$', '%', '&', '*', '+', '=', '~', '`', '@everyone', '@here']
                        if any(content.startswith(prefix) for prefix in skip_prefixes):
                            continue
                        
                        # Skip messages that are just URLs
                        if content.startswith('http://') or content.startswith('https://'):
                            continue
                        
                        # Skip very short messages (less than 3 characters)
                        if len(content) < 3:
                            continue
                        
                        try:
                            # Process the message through the unified memory system
                            await unified_memory.learn_from_message(message)
                            channel_learned += 1
                            total_learned += 1
                        except Exception as e:
                            print(f"Error learning from message {message.id}: {e}")
                        
                        channel_processed += 1
                        total_processed += 1
                
                except Exception as e:
                    print(f"Error processing channel {channel.name}: {e}")
                
                channels_done += 1
                
                # Update status every channel
                if status_msg:
                    try:
                        await status_msg.edit(content=f"🧠 Training in progress...\n📊 Channels: {channels_done}/{len(text_channels)}\n📝 Current: #{channel.name}\n✅ Total learned: {total_learned} messages")
                    except:
                        pass  # Message might be deleted
            
            # Save unified memory data
            unified_memory.save_unified_data()
            
            # Final status
            if status_msg:
                await status_msg.edit(content=f"✅ Server-wide training complete!\n📊 Channels processed: {channels_done}\n📝 Total messages: {total_processed}\n🧠 Learned from: {total_learned} messages\n💾 Data saved!")
            else:
                await interaction.followup.send(f"✅ Server-wide training complete!\n📊 Channels processed: {channels_done}\n📝 Total messages: {total_processed}\n🧠 Learned from: {total_learned} messages\n💾 Data saved!")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during training: {e}")

async def setup(bot):
    await bot.add_cog(MemoryManagement(bot))

