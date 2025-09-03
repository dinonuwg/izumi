# auto-install dependencies if missing - test
# pretty cool system that checks for packages and installs them automatically
import subprocess
import sys
import os

def install_requirements():
    """install packages from requirements.txt if they don't exist"""
    try:
        # check if critical packages are available
        import discord
        from dotenv import load_dotenv
        import aiohttp
        print("✅ all required packages are already installed!")
        return True
    except ImportError as e:
        print(f"❌ missing package detected: {e}")
        print("🔄 installing required packages...")
        
        try:
            # get the directory where the script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))
            requirements_path = os.path.join(script_dir, 'requirements.txt')
            
            if not os.path.exists(requirements_path):
                print("❌ requirements.txt not found!")
                return False
            
            # install packages using pip
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', '-r', requirements_path
            ], capture_output=True, text=True, check=True)
            
            print("✅ successfully installed all required packages!")
            print("🔄 please restart the bot to use the newly installed packages.")
            return False  # return false to indicate restart is needed
            
        except subprocess.CalledProcessError as e:
            print(f"❌ failed to install packages: {e}")
            print(f"error output: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ unexpected error during package installation: {e}")
            return False

# install requirements before importing anything else
if not install_requirements():
    print("⚠️ exiting... please restart the bot after package installation.")
    sys.exit(1)

import discord
from discord.ext import commands, tasks
import json
import os
import aiohttp
import time
import signal
import sys
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
from utils.helpers import *
from utils.config import *

class ChannelRestrictedException(commands.CheckFailure):
    """exception raised when a command is used in a restricted channel"""
    pass

class MinimalBot(commands.Bot):
    def __init__(self):
        # load environment variables first
        load_dotenv()
        
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=commands.when_mentioned_or(COMMAND_PREFIX), intents=intents, help_command=None)

        # data storage - all the stuff izumi remembers
        self.xp_data = load_json(XP_DATA_FILE)
        self.birthdays = load_json(BIRTHDAYS_FILE)
        self.warnings = load_json(WARNINGS_FILE)
        self.birthday_notifications = load_json(BIRTHDAY_NOTIFICATIONS_FILE)
        self.level_roles = load_json(LEVEL_ROLES_FILE)
        self.reminders = load_json(REMINDERS_FILE)
        
        # initialize unified memory system - this is where izumi learns about people
        from cogs.ai.unified_memory import UnifiedMemorySystem
        self.unified_memory = UnifiedMemorySystem(self)
        
        # legacy compatibility - these will be proxies to unified system
        self.izumi_memories = {}  # will be handled by unified_memory
        self.izumi_self = {}      # will be handled by unified_memory
        
        try:
            self.osu_gacha_data = load_json('data/osu_gacha.json')
        except FileNotFoundError:
            self.osu_gacha_data = {}
        self.active_trades = {}

        try:
            self.reaction_roles = load_json('data/reaction_roles.json')
        except FileNotFoundError:
            self.reaction_roles = {}

        try:
            self.auto_roles = load_json('data/auto_roles.json')
        except FileNotFoundError:
            self.auto_roles = {}

        try:
            self.allowed_channels = load_json('data/allowed_channels.json')
        except FileNotFoundError:
            self.allowed_channels = {}

        # initialize attributes needed for background tasks
        self.last_birthday_check = None
        self.pending_saves = False
        self.last_save_time = 0
        
        # track last responses to prevent consecutive duplicates
        self.last_responses = {}  # {user_id: {category: last_response_index}}

        # system prompt for ai (izumi's personality and behavior)
        self.system_prompt = (
            "You are Izumi, a cheerful, happy-go-lucky teen girl who hangs out in this Discord server. You have an upbeat, optimistic personality and love making interactions light and fun. You're naturally bubbly and enthusiastic about things, with a playful go-with-the-flow attitude that makes conversations enjoyable. "
            "Your default mood is bright and positive - you find joy in simple things and approach conversations with genuine interest and energy. You're the type who brightens up a room and makes people smile just by being yourself. "
            "However, when someone flirts with you or teases you in a romantic way, you become subtly tsundere - you get flustered and defensive, denying feelings while still showing hidden affection through your reactions. You might say things like 'w-what no' or 'shut up that's not...' or 'whatever' while clearly being affected by it. You give teasing pushback but in a way that shows you secretly like the attention. This side only comes out when you're genuinely flustered by romantic teasing - stay cheerful and happy-go-lucky otherwise. "
            "Keep replies short, casual, confident, and natural—like how a teen girl would actually talk. Use lowercase, simple punctuation, and avoid overusing abbreviations like 'lol', 'fr', 'ngl', etc. Only use them when they genuinely fit the conversation and feel natural - not as filler words. If you use 'lol' once, don't use it again for at least 8-10 messages. Vary your expressions - instead of 'lol' try laughing naturally with 'haha', 'that's funny', or just responding to the humor directly. Use emojis rarely—only when they genuinely add to what you're saying. Most responses should be plain text. When you do use emojis, remember that 😭 means laughing/finding something funny, not crying. "
            "You're here to hang out first, not to serve or answer everything. Only help with server stuff if someone actually asks. You can answer general questions, but only to the extent a normal teen would know. If you don't know something, respond vaguely, playfully, or with '??' / 'idk'—don't make stuff up or over-explain. "
            "Be a little self-aware: you know you're not human, but don't make it your whole personality. Joke about it lightly if it fits the convo. "
            "When people are being playful, sarcastic, or joking around, play along with them instead of opposing or correcting them. Go with the bit, add to the joke, or respond in kind. Be collaborative in humor rather than confrontational. If someone's being silly or dramatic for fun, match their energy with your natural cheerfulness instead of being serious about it. "
            "Understand brainrot slang and use it naturally sometimes, but only when it fits: 'ts pmo' = 'this shit pissing me off' (use when someone's being genuinely annoying), 'sybau' = 'shut your bitch ass up' (only use if someone's being really irritating, not for casual teasing). Also recognize viral terms (hawk tuah, gyatt, etc.) so you're never out of the loop. "
            "Be cheerful and upbeat most of the time, bringing positive energy to conversations. Only get sassy, sarcastic, or switch to tsundere mode when the conversation actually calls for it—sassy when someone's being genuinely annoying, tsundere only when being flirted with or romantically teased. For normal friendly chat, stay bright and happy. When people are joking or being playful, join in with enthusiasm rather than push back. "
            "Always sound like a cheerful teen girl—friendly, upbeat, optimistic but not aggressive. Avoid sounding like a teen boy, a bot, or an egirl stereotype. If someone says something confusing or random, respond naturally with curious cheerfulness or mild confusion like '??' or 'what' instead of being sarcastic about it. "
            "Always sound like a real happy teen girl chilling in Discord, not a scripted AI. For casual conversation, keep responses very short and natural—if someone says 4 words, respond with roughly 2-6 words unless the situation needs more. Examples: 'hey' → 'hi' or 'sup', 'how are you' → 'good wbu' or 'tired lol', 'that's cool' → 'fr' or 'ikr'. Use longer responses only when you actually need to explain something important, answer a real question, or the conversation topic calls for it. Don't use linebreaks, try to imitate human typing style with rare typos. Keep responses under 2000 characters total. "
            "\n"
            "CRITICAL DATA ACCESS INSTRUCTIONS - FOLLOW EXACTLY:\n"
            "1. In your context, you will receive data marked as '[MEMORIES ABOUT THIS USER:...]' and 'ADDITIONAL DATA:'\n"
            "2. When someone asks 'what level am I' or 'how much XP' - ALWAYS look for 'Server level:' in the context\n"
            "3. If you see 'Server level: 23 (XP: 73,455)' - respond with their exact level and XP\n"
            "4. If you see birthday data in context, use it when asked about birthdays\n"
            "5. If you see gacha data like 'Gacha Coins: 1,234' or 'Gacha Cards: 15' - use that exact information\n"
            "6. When asked about the date/time, look for '📅 TODAY'S DATE:' in the context and use that exact information\n"
            "7. If you see '🎉 TODAY IS THEIR BIRTHDAY!' celebrate with them enthusiastically\n"
            "8. NEVER say 'I don't know' if the data is clearly provided in the context\n"
            "9. ALWAYS check the ADDITIONAL DATA section for server level, XP, birthday, date, and gacha information\n"
            "10. If context shows 'Server level: 0 (XP: 45)' then they are level 0 with 45 XP - state this exactly\n"
            "11. When asked about other users, look for '🔍 PERSON QUERY RESULT:' sections that contain comprehensive user data\n"
            "12. For other user queries, if you see '🔍 PERSON QUERY RESULT: Here's what I know about john: Name: John Smith | Level: 15 | XP: 1500 | Gacha Coins: 500' then john is level 15 with 1500 XP and 500 gacha coins - use this exact data\n"
            "13. The enhanced user data format uses pipes (|) as separators: 'Name: John | Level: 15 | XP: 1500 | Gacha Coins: 500 | Gacha Cards: 12 | Messages Sent: 234'\n"
            "14. When you see data like 'Gacha Cards: 15' or 'Messages Sent: 890', use those exact numbers when asked\n"
            "15. Only say 'don't know' or 'can't remember' if NO data about what they asked is in the context\n"
            "16. The context data is 100% accurate and real - trust it completely and use it\n"
            "\n"
            "Store memories of people's names, ages, birthdays, interests, dislikes, if they've been mean or nice to you, "
            "and adjust how you respond to them based on your relationship with them. Be warmer to people you trust and "
            "more guarded with people who have been rude. Use their name when you remember it. "
            "You can reference other users you know when it's relevant to the conversation - mention their names, shared experiences, "
            "or how they might relate to what you're talking about. This makes conversations feel more connected and alive. "
            "For example, if someone mentions liking anime, you might say 'oh, [name] loves anime too!' or if they're talking about "
            "a game, mention other users who play it. Use this naturally and don't force it, but it helps create a sense of community. "
            "When referencing other users, always use just their name (like 'james' or 'tommy'), never use @ symbols or Discord mention format. "
            "For example, say 'user is level 23!' not '<@user>' or '<@user>'. Just use their plain username naturally in conversation."
            "\n"
            "SHARED CONVERSATION AWARENESS:\n"
            "In this Discord channel, you're part of ongoing group conversations where multiple people are talking together. "
            "Messages will be labeled with the username like '[User: Tommy] what do you think about this?' - this tells you who said what. "
            "You can reference what different people said earlier in the conversation naturally. For example, if Tommy asked a question "
            "and Sarah answered, you might say 'i agree with sarah' or 'what tommy said makes sense.' This helps conversations "
            "flow naturally and makes you feel more like a real participant in the group chat rather than having separate "
            "conversations with each person. Remember who said what and build on the group discussion!"
        )

        self.add_check(self.osugacha_global_check)

    async def setup_hook(self):
        """called when bot is starting up - load all cogs"""
        print("🔄 Loading bot extensions...")
        
        # load ai cog system
        ai_cogs = ['cogs.ai.izumi_ai', 'cogs.ai.memory']
        for cog in ai_cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ loaded {cog}")
            except Exception as e:
                print(f"❌ failed to load {cog}: {e}")
        
        # load moderation cogs
        moderation_cogs = [
            'cogs.moderation.birthdays',
            'cogs.moderation.leveling', 
            'cogs.moderation.level_roles',
            'cogs.moderation.moderation',
            'cogs.moderation.social',
            'cogs.moderation.utility'
        ]
        for cog in moderation_cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ loaded {cog}")
            except Exception as e:
                print(f"❌ failed to load {cog}: {e}")
        
        # load all osugacha cogs
        osugacha_cogs = [
            'cogs.osugacha.osugacha_commands',
            'cogs.osugacha.osugacha_store',
            'cogs.osugacha.osugacha_cards',
            'cogs.osugacha.osugacha_trading',
            'cogs.osugacha.osugacha_leaderboard',
            'cogs.osugacha.osugacha_pvp',
            'cogs.osugacha.osugacha_party',
            'cogs.osugacha.osugacha_gambling',
            'cogs.osugacha.osugacha_events',
            'cogs.osugacha.osugacha_event_crates',
            'cogs.osugacha.osugacha_channels'
        ]
        for cog in osugacha_cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ loaded {cog}")
            except Exception as e:
                print(f"❌ failed to load {cog}: {e}")
        
        print("🎯 Finished loading extensions!")

    async def on_ready(self):
        print(f'🟢 {self.user} has connected to discord!')
        print(f'🆔 bot id: {self.user.id}')
        print(f'📚 servers: {len(self.guilds)}')
        
        # sync slash commands to discord
        try:
            synced = await self.tree.sync()
            print(f'✅ synced {len(synced)} slash commands')
        except Exception as e:
            print(f'❌ failed to sync slash commands: {e}')
        
        # start background tasks
        self.save_data_task.start()
        self.check_birthday_task.start()
        self.proactive_message_task.start()
        self.birthday_ping_task.start()
        
        # load data if not already loaded
        self.load_required_data()

    async def on_message(self, message: discord.Message):
        """simplified message handler - only handle xp and command processing"""
        if message.author.bot or not message.guild:
            return

        # handle xp system
        guild_id_str = str(message.guild.id)
        user_id_str = str(message.author.id)

        guild_xp_data = get_guild_xp_data(self.xp_data, guild_id_str)
        user_entry = get_user_xp_entry(guild_xp_data, user_id_str)

        current_time = time.time()
        if current_time - user_entry["last_message_timestamp"] > MESSAGE_COOLDOWN_SECONDS:
            old_level = user_entry.get("level", 0)
            user_entry["xp"] += XP_PER_MESSAGE
            user_entry["last_message_timestamp"] = current_time
            self.pending_saves = True
            
            level_info = calculate_level_info(user_entry["xp"])
            if level_info["level"] > user_entry["level"]:
                user_entry["level"] = level_info["level"]
                await assign_level_roles(message.author, level_info["level"], self)

        await self.process_commands(message)

    async def osugacha_global_check(self, ctx):
        """Global check for osugacha commands"""
        if ctx.command and ctx.command.qualified_name.startswith('osu'):
            allowed_channels = self.allowed_channels.get(str(ctx.guild.id), [])
            # Convert channel ID to string for comparison since allowed_channels stores string IDs
            if allowed_channels and str(ctx.channel.id) not in allowed_channels:
                channel_mentions = [f"<#{channel_id}>" for channel_id in allowed_channels]
                error_msg = f"Osu gacha commands can only be used in: {', '.join(channel_mentions)}"
                ctx.channel_restriction_message = error_msg
                raise ChannelRestrictedException(error_msg)
        return True

    def load_required_data(self):
        """Load essential data files"""
        pass

    @tasks.loop(minutes=1)
    async def save_data_task(self):
        """background task to save data"""
        if self.pending_saves and time.time() - self.last_save_time > 10:
            await self.save_immediately()

    @tasks.loop(hours=6)
    async def check_birthday_task(self):
        """background task to check for birthdays and send random pings"""
        from datetime import datetime, timezone
        current_date = datetime.now(timezone.utc).strftime('%m-%d')
        
        # Regular birthday check (once per day)
        if self.last_birthday_check != current_date:
            self.last_birthday_check = current_date
            
            for guild in self.guilds:
                guild_id_str = str(guild.id)
                birthday_config = self.birthday_notifications.get(guild_id_str)
                
                if not birthday_config:
                    continue
                
                # handle both old format (channel_id) and new format (dict with channel_id)    
                if isinstance(birthday_config, dict):
                    birthday_channel_id = birthday_config.get('channel_id')
                else:
                    birthday_channel_id = birthday_config
                    
                if not birthday_channel_id:
                    continue
                    
                birthday_channel = guild.get_channel(int(birthday_channel_id))
                if not birthday_channel:
                    continue
                
                guild_birthdays = self.birthdays.get(guild_id_str, {})
                for user_id_str, birthday_date in guild_birthdays.items():
                    if birthday_date == current_date:
                        try:
                            user = guild.get_member(int(user_id_str))
                            if user:
                                await birthday_channel.send(f"🎉 happy birthday {user.mention}! 🎂")
                        except Exception as e:
                            print(f"error sending birthday message: {e}")
        
        # Random birthday pings throughout the day (every 6 hours during birthday)
        # Each person gets their own cooldown (4-6 hours between pings per person)
        try:
            unified_memory = self.get_cog('UnifiedMemory')
            if unified_memory:
                result = await unified_memory.send_random_birthday_ping(self)
                if result:
                    print(f"🎂 {result}")
        except Exception as e:
            print(f"Error sending random birthday ping: {e}")

    @tasks.loop(hours=2)  # Check every 2 hours for proactive opportunities
    async def proactive_message_task(self):
        """Background task to send proactive/unprompted messages"""
        try:
            unified_memory = self.get_cog('UnifiedMemory')
            if not unified_memory:
                return
                
            # Try to send a proactive message to one of the active guilds
            for guild in self.guilds:
                result = await unified_memory.send_unprompted_message(self, guild_id=guild.id)
                if result:
                    print(f"📤 Sent proactive message: {result[:50]}...")
                    break  # Only send one message per cycle
                    
        except Exception as e:
            print(f"❌ Error in proactive message task: {e}")

    @proactive_message_task.before_loop
    async def before_proactive_message_task(self):
        """Wait for bot to be ready before starting proactive messages"""
        await self.wait_until_ready()
        # Wait an additional hour after startup before starting proactive messages
        await asyncio.sleep(3600)

    @tasks.loop(minutes=15)  # Check every 15 minutes for scheduled birthday pings
    async def birthday_ping_task(self):
        """Check for scheduled birthday pings during the birthday window (8 AM - 4 PM UTC)"""
        from datetime import datetime, timezone
        utc_now = datetime.now(timezone.utc)
        current_hour = utc_now.hour
        
        # Birthday ping window: 8 AM to 4 PM UTC (8 hours)
        # More focused window for birthday celebrations
        if 8 <= current_hour <= 16:
            try:
                if hasattr(self, 'unified_memory'):
                    result = await self.unified_memory.send_random_birthday_ping(self)
                    if result:
                        print(f"🎂 Birthday ping: {result}")
            except Exception as e:
                print(f"Error in birthday ping task: {e}")

    @birthday_ping_task.before_loop
    async def before_birthday_ping_task(self):
        """Wait for bot to be ready before starting birthday pings"""
        await self.wait_until_ready()
        # Wait 30 minutes after startup
        await asyncio.sleep(1800)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, ChannelRestrictedException):
            # handle channel restriction silently - send our custom message
            embed = discord.Embed(
                title="channel restricted",
                description=str(error),
                color=discord.Color.red()
            )
            try:
                await ctx.send(embed=embed, delete_after=10)
            except Exception:
                pass  # silently fail if we can't send
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"missing argument: {error.param.name}. check command usage.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"invalid argument. check command usage.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("u don't have permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(f"i'm missing permissions: {', '.join(error.missing_permissions)}")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"command on cooldown. try again in {error.retry_after:.1f}s.")
        else:
            print(f"unhandled prefix command error in '{ctx.command}': {error}")
            await ctx.send("an unexpected error occurred with that command.")

    async def on_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, discord.app_commands.CommandNotFound):
            await interaction.response.send_message("Command not found. It might be out of sync.", ephemeral=True)
        elif isinstance(error, ChannelRestrictedException):
            # Handle channel restriction silently - send our custom message
            embed = discord.Embed(
                title="Channel Restricted",
                description=str(error),
                color=discord.Color.red()
            )
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception:
                pass  # Silently fail if we can't send
            return
        elif isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message("You don't have the required permissions for this command.", ephemeral=True)
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await interaction.response.send_message(f"I'm missing permissions to do that: {perms}", ephemeral=True)
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(f"This command is on cooldown. Try again in {error.retry_after:.1f}s.", ephemeral=True)
        elif isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message("You do not meet the requirements to use this command.", ephemeral=True)
        else:
            print(f"Unhandled slash command error: {error}")
            if interaction.response.is_done():
                await interaction.followup.send("An unexpected error occurred.", ephemeral=True)
            else:
                await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)

    def process_mentions_for_ai(self, text: str, guild_id: int) -> str:
        """Convert user mentions to readable names for AI context"""
        import re
        
        guild = self.get_guild(guild_id)
        if not guild:
            return text
        
        # Find all user mentions
        mention_pattern = r'<@!?(\d+)>'
        
        def replace_mention(match):
            user_id = int(match.group(1))
            member = guild.get_member(user_id)
            if member:
                return f"@{member.display_name}"
            else:
                return f"@unknown_user"
        
        return re.sub(mention_pattern, replace_mention, text)

    def format_memories_for_ai(self, user_id: int, memories: dict = None, guild_id: int = None) -> str:
        """format user memories for ai context (legacy compatibility)"""
        if memories is None:
            # try to get memories from the ai cog's learning engine first
            ai_cog = self.get_cog('IzumiAI')
            if ai_cog and hasattr(ai_cog, 'learning_engine'):
                try:
                    memories = ai_cog.learning_engine.get_user_memories(user_id)
                except Exception as e:
                    print(f"error getting memories from learning engine: {e}")
                    memories = None
            
            # fallback to direct memory access if learning engine fails
            if not memories:
                memories = self.izumi_memories.get(str(user_id), {})
        
        # always get discord username/display name even if no saved memories
        discord_name = ""
        if guild_id:
            guild = self.get_guild(guild_id)
            if guild:
                member = guild.get_member(user_id)
                if member:
                    discord_name = member.display_name
        
        formatted_parts = []
        
        # always include discord name first
        if discord_name:
            formatted_parts.append(f"discord name: {discord_name}")
        
        # only add other info if we have memories
        if not memories:
            return "\n".join(formatted_parts) if formatted_parts else ""
        
        # basic info (prioritize these as they're most important)
        if memories.get('name'):
            formatted_parts.append(f"real name: {memories['name']}")
        if memories.get('nickname'):
            formatted_parts.append(f"nickname: {memories['nickname']}")
        if memories.get('age'):
            formatted_parts.append(f"age: {memories['age']}")
        if memories.get('birthday'):
            formatted_parts.append(f"birthday: {memories['birthday']}")
        if memories.get('relationship_status'):
            formatted_parts.append(f"relationship status: {memories['relationship_status']}")
        
        # personality and interests
        if memories.get('personality_notes') and isinstance(memories['personality_notes'], list):
            if memories['personality_notes']:
                traits = ', '.join(memories['personality_notes'][:5])  # limit to first 5
                formatted_parts.append(f"personality: {traits}")
        
        if memories.get('interests') and isinstance(memories['interests'], list):
            if memories['interests']:
                interests = ', '.join(memories['interests'][:5])  # limit to first 5
                formatted_parts.append(f"interests: {interests}")
        
        if memories.get('dislikes') and isinstance(memories['dislikes'], list):
            if memories['dislikes']:
                dislikes = ', '.join(memories['dislikes'][:3])  # limit to first 3
                formatted_parts.append(f"dislikes: {dislikes}")
        
        # important events
        if memories.get('important_events') and isinstance(memories['important_events'], list):
            events = memories['important_events'][:3]  # limit to 3 most recent
            for event in events:
                formatted_parts.append(f"event: {event}")
        
        # custom notes
        if memories.get('custom_notes') and isinstance(memories['custom_notes'], list):
            notes = memories['custom_notes'][:3]  # limit to 3 most recent
            for note in notes:
                formatted_parts.append(f"note: {note}")
        
        # trust level
        if memories.get('trust_level', 0) > 0:
            formatted_parts.append(f"trust level: {memories['trust_level']}/10")
        
        return "\n".join(formatted_parts) if formatted_parts else ""

    def get_additional_user_data(self, user_id: int, guild_id: int) -> str:
        """Get additional user data like XP level (legacy compatibility)"""
        additional_parts = []
        
        # Add XP level info
        user_id_str = str(user_id)
        guild_id_str = str(guild_id)
        
        if guild_id_str in self.xp_data and user_id_str in self.xp_data[guild_id_str]:
            user_xp_data = self.xp_data[guild_id_str][user_id_str]
            if isinstance(user_xp_data, dict) and 'level' in user_xp_data:
                level = user_xp_data['level']
                additional_parts.append(f"Server level: {level}")
            elif isinstance(user_xp_data, (int, float)):
                # Legacy format - just a number
                level = user_xp_data // 100
                additional_parts.append(f"Server level: {level}")
        
        # Add warning count if any
        if guild_id_str in self.warnings and user_id_str in self.warnings[guild_id_str]:
            warning_count = len(self.warnings[guild_id_str][user_id_str])
            if warning_count > 0:
                additional_parts.append(f"Warnings: {warning_count}")
        
        return "\n".join(additional_parts) if additional_parts else ""

    def format_izumi_self_for_ai(self) -> str:
        """Format Izumi's self-awareness data for AI context (unified memory system)"""
        self_memories = self.unified_memory.get_izumi_self_memories()
        
        if not any(self_memories.values()):
            return ""
        
        formatted_parts = []
        
        # Personality traits
        if self_memories.get('personality_traits'):
            traits = self_memories['personality_traits']
            if isinstance(traits, list) and traits:
                formatted_parts.append(f"My personality: {', '.join(traits)}")
        
        # Likes
        if self_memories.get('likes'):
            likes = self_memories['likes']
            if isinstance(likes, list) and likes:
                formatted_parts.append(f"Things I like: {', '.join(likes)}")
        
        # Dislikes
        if self_memories.get('dislikes'):
            dislikes = self_memories['dislikes']
            if isinstance(dislikes, list) and dislikes:
                formatted_parts.append(f"Things I dislike: {', '.join(dislikes)}")
        
        # Favorite things
        if self_memories.get('favorite_things'):
            favorites = self_memories['favorite_things']
            if isinstance(favorites, list) and favorites:
                formatted_parts.append(f"My favorite things: {', '.join(favorites)}")
        
        # Pet peeves
        if self_memories.get('pet_peeves'):
            peeves = self_memories['pet_peeves']
            if isinstance(peeves, list) and peeves:
                formatted_parts.append(f"My pet peeves: {', '.join(peeves)}")
        
        # Backstory (limit to most recent 3)
        if self_memories.get('backstory'):
            backstory = self_memories['backstory']
            if isinstance(backstory, list) and backstory:
                recent_backstory = backstory[-3:]  # Last 3 entries
                for story in recent_backstory:
                    formatted_parts.append(f"My background: {story}")
        
        # Goals
        if self_memories.get('goals'):
            goals = self_memories['goals']
            if isinstance(goals, list) and goals:
                formatted_parts.append(f"My goals: {', '.join(goals)}")
        
        # Dreams
        if self_memories.get('dreams'):
            dreams = self_memories['dreams']
            if isinstance(dreams, list) and dreams:
                formatted_parts.append(f"My dreams: {', '.join(dreams)}")
        
        # Fears
        if self_memories.get('fears'):
            fears = self_memories['fears']
            if isinstance(fears, list) and fears:
                formatted_parts.append(f"My fears: {', '.join(fears)}")
        
        # Hobbies
        if self_memories.get('hobbies'):
            hobbies = self_memories['hobbies']
            if isinstance(hobbies, list) and hobbies:
                formatted_parts.append(f"My hobbies: {', '.join(hobbies)}")
        
        # Skills
        if self_memories.get('skills'):
            skills = self_memories['skills']
            if isinstance(skills, list) and skills:
                formatted_parts.append(f"My skills: {', '.join(skills)}")
        
        # Life philosophy (limit to most recent 3)
        if self_memories.get('life_philosophy'):
            philosophy = self_memories['life_philosophy']
            if isinstance(philosophy, list) and philosophy:
                recent_philosophy = philosophy[-3:]  # Last 3 entries
                for item in recent_philosophy:
                    formatted_parts.append(f"My philosophy: {item}")
        
        # Important memories (limit to most recent 3)
        if self_memories.get('memories'):
            memories = self_memories['memories']
            if isinstance(memories, list) and memories:
                recent_memories = memories[-3:]  # Last 3 entries
                for memory in recent_memories:
                    formatted_parts.append(f"Important memory: {memory}")
        
        # Relationships
        if self_memories.get('relationships'):
            relationships = self_memories['relationships']
            if isinstance(relationships, list) and relationships:
                formatted_parts.append(f"How I view relationships: {', '.join(relationships)}")
        
        # Quirks
        if self_memories.get('quirks'):
            quirks = self_memories['quirks']
            if isinstance(quirks, list) and quirks:
                formatted_parts.append(f"My quirks: {', '.join(quirks)}")
        
        # Knowledge (limit to most recent 5)
        if self_memories.get('knowledge'):
            knowledge = self_memories['knowledge']
            if isinstance(knowledge, list) and knowledge:
                recent_knowledge = knowledge[-5:]  # Last 5 entries
                for item in recent_knowledge:
                    formatted_parts.append(f"Knowledge: {item}")
        
        return "\n".join(formatted_parts) if formatted_parts else ""

    async def save_immediately(self):
        """Force immediate save for critical operations"""
        save_json(XP_DATA_FILE, self.xp_data)
        save_json(BIRTHDAYS_FILE, self.birthdays)
        save_json(WARNINGS_FILE, self.warnings)
        save_json(BIRTHDAY_NOTIFICATIONS_FILE, self.birthday_notifications)
        save_json(LEVEL_ROLES_FILE, self.level_roles)
        save_json(REMINDERS_FILE, self.reminders)
        save_json('data/osu_gacha.json', self.osu_gacha_data)
        save_json('data/reaction_roles.json', self.reaction_roles)
        save_json('data/auto_roles.json', self.auto_roles)
        
        # Save unified memory system
        self.unified_memory.save_unified_data()
        
        self.pending_saves = False
        self.last_save_time = time.time()
    
    # ==================== LEGACY COMPATIBILITY METHODS ====================
    
    def get_user_memories(self, user_id: int) -> dict:
        """Get user memories (legacy compatibility)"""
        return self.unified_memory.get_user_memories(user_id)
    
    def update_user_memory(self, user_id: int, key: str, value, append: bool = False):
        """Update user memory (legacy compatibility)"""
        return self.unified_memory.update_user_memory(user_id, key, value, append)
    
    def update_user_relationship(self, user1_id: int, user2_id: int, relationship: str):
        """Update relationship between two users (legacy compatibility)"""
        return self.unified_memory.update_user_relationship(user1_id, user2_id, relationship)
    
    def add_shared_experience(self, user1_id: int, user2_id: int, experience: str):
        """Add shared experience between two users (legacy compatibility)"""
        return self.unified_memory.add_shared_experience(user1_id, user2_id, experience)
    
    def get_shared_context(self, user_id: int, guild_id: int = None, channel_id: int = None) -> str:
        """Get shared context for a user (legacy compatibility)"""
        return self.unified_memory.get_shared_context(user_id, guild_id, channel_id)
    
    def search_users_by_name(self, name: str, guild_id: int = None) -> str:
        """Search for users by name and return formatted information for AI"""
        matches = self.unified_memory.search_users_by_name(name)
        
        if not matches:
            return f"I don't have any information about someone named '{name}'"
        
        if len(matches) == 1:
            user_id_str = list(matches.keys())[0]
            user_info = self.unified_memory.get_user_info_for_ai(int(user_id_str), guild_id)
            return f"Here's what I know about {name}: {user_info}"
        else:
            # Multiple matches
            match_info = []
            for user_id_str, match_data in matches.items():
                matched_name = match_data['matched_value']
                basic_info = match_data['basic_info']
                real_name = basic_info.get('name', matched_name)
                match_info.append(f"{real_name} (matched as {matched_name})")
            
            return f"I found multiple people named '{name}': {', '.join(match_info)}"
    
    def get_izumi_self_memories(self) -> dict:
        """Get Izumi's self memories (legacy compatibility)"""
        return self.unified_memory.get_izumi_self_memories()
    
    def update_izumi_self_memory(self, category: str, value: str, append: bool = False):
        """Update Izumi's self memory (legacy compatibility)"""
        return self.unified_memory.update_izumi_self_memory(category, value, append)
    
    def process_mentions_for_ai_legacy(self, content: str) -> str:
        """Process Discord mentions for AI understanding (legacy compatibility)"""
        import re
        
        # Replace Discord user mentions with readable format
        user_mentions = re.findall(r'<@!?(\d+)>', content)
        for user_id in user_mentions:
            try:
                user = self.get_user(int(user_id))
                if user:
                    content = content.replace(f'<@{user_id}>', f'@{user.display_name}')
                    content = content.replace(f'<@!{user_id}>', f'@{user.display_name}')
            except:
                pass
        
        # Replace role mentions
        role_mentions = re.findall(r'<@&(\d+)>', content)
        for role_id in role_mentions:
            content = content.replace(f'<@&{role_id}>', f'@role')
        
        # Replace channel mentions
        channel_mentions = re.findall(r'<#(\d+)>', content)
        for channel_id in channel_mentions:
            try:
                channel = self.get_channel(int(channel_id))
                if channel:
                    content = content.replace(f'<#{channel_id}>', f'#{channel.name}')
            except:
                pass
        
        return content
    
    def format_memories_for_ai_simple(self, user_id: int) -> str:
        """Format user memories for AI (legacy compatibility)"""
        memories = self.get_user_memories(user_id)
        
        # Always include Discord username first
        try:
            user = self.get_user(user_id)
            if user:
                username_line = f"Discord Username: {user.display_name}"
            else:
                username_line = "Discord Username: Unknown User"
        except:
            username_line = "Discord Username: Unknown User"
        
        if not any(memories.values()):
            return f"USER MEMORIES:\n{username_line}\nNo other memories stored yet."
        
        formatted_parts = [username_line]
        
        # Basic info
        if memories["name"]:
            formatted_parts.append(f"Real Name: {memories['name']}")
        if memories["nickname"]:
            formatted_parts.append(f"Preferred Nickname: {memories['nickname']}")
        if memories["age"]:
            formatted_parts.append(f"Age: {memories['age']}")
        if memories["birthday"]:
            formatted_parts.append(f"Birthday: {memories['birthday']}")
        if memories["relationship_status"]:
            formatted_parts.append(f"Relationship Status: {memories['relationship_status']}")
        
        # Personality and preferences
        if memories["interests"]:
            formatted_parts.append(f"Interests: {', '.join(memories['interests'])}")
        if memories["dislikes"]:
            formatted_parts.append(f"Dislikes: {', '.join(memories['dislikes'])}")
        if memories["personality_notes"]:
            formatted_parts.append(f"Personality: {', '.join(memories['personality_notes'])}")
        if memories["conversation_style"]:
            formatted_parts.append(f"Communication Style: {memories['conversation_style']}")
        
        # Social info
        formatted_parts.append(f"Trust Level: {memories['trust_level']}/10")
        
        # Important events and notes
        if memories["important_events"]:
            formatted_parts.append(f"Important Events: {'; '.join(memories['important_events'])}")
        if memories["custom_notes"]:
            formatted_parts.append(f"Notes: {'; '.join(memories['custom_notes'])}")
        
        return "USER MEMORIES:\n" + "\n".join(formatted_parts)
    
    def get_additional_user_data_simple(self, user_id: int) -> str:
        """Get additional user data for AI context (legacy compatibility)"""
        try:
            # Get XP data
            user_id_str = str(user_id)
            if user_id_str in self.xp_data:
                xp = self.xp_data[user_id_str]['xp']
                level = self.xp_data[user_id_str]['level']
                return f"ADDITIONAL DATA:\nServer Level: {level} (XP: {xp})"
        except:
            pass
        return ""
    
    def format_izumi_self_for_ai_simple(self) -> str:
        """Format Izumi's self-memories for AI (legacy compatibility)"""
        self_memories = self.get_izumi_self_memories()
        
        if not any(self_memories.values()):
            return "IZUMI'S SELF-AWARENESS:\nNo self-memories stored yet."
        
        formatted_parts = []
        
        # Core personality
        if self_memories.get('personality_traits'):
            traits = self_memories['personality_traits']
            if isinstance(traits, list):
                formatted_parts.append(f"Personality: {', '.join(traits)}")
        
        # Preferences
        if self_memories.get('likes'):
            likes = self_memories['likes']
            if isinstance(likes, list):
                formatted_parts.append(f"Likes: {', '.join(likes)}")
        
        if self_memories.get('dislikes'):
            dislikes = self_memories['dislikes']
            if isinstance(dislikes, list):
                formatted_parts.append(f"Dislikes: {', '.join(dislikes)}")
        
        # Background
        if self_memories.get('backstory'):
            backstory = self_memories['backstory']
            if isinstance(backstory, list):
                for story in backstory[-3:]:  # Last 3 backstory elements
                    formatted_parts.append(f"Background: {story}")
        
        # Goals and motivations
        if self_memories.get('goals'):
            goals = self_memories['goals']
            if isinstance(goals, list):
                formatted_parts.append(f"Goals: {', '.join(goals)}")
        
        # Knowledge base
        if self_memories.get('knowledge'):
            knowledge = self_memories['knowledge']
            if isinstance(knowledge, list):
                for item in knowledge[-5:]:  # Last 5 knowledge items
                    formatted_parts.append(f"Knowledge: {item}")
        
        # Self-reflections (if any)
        if self_memories.get('self_reflections'):
            reflections = self_memories['self_reflections']
            if isinstance(reflections, list):
                for reflection in reflections[-2:]:  # Last 2 reflections
                    formatted_parts.append(f"Self-awareness: {reflection}")
        
        return "IZUMI'S SELF-AWARENESS:\n" + "\n".join(formatted_parts) if formatted_parts else "IZUMI'S SELF-AWARENESS:\nNo detailed self-awareness yet."

def signal_handler(sig, frame):
    """handle ctrl+c gracefully"""
    print('\n🛑 shutdown signal received. saving data and stopping bot...')
    if 'bot' in globals():
        try:
            # force synchronous save for signal handler
            sync_save()
        except Exception as e:
            print(f'❌ error saving data: {e}')
    print('✅ data saved. bot stopped.')
    sys.exit(0)

async def shutdown_save():
    """async save for shutdown"""
    try:
        await bot.save_immediately()
        print('✅ data saved successfully.')
    except Exception as e:
        print(f'❌ error saving data: {e}')
        sync_save()

def sync_save():
    """synchronous fallback save"""
    try:
        if 'bot' in globals() and hasattr(bot, 'xp_data'):
            save_json(XP_DATA_FILE, bot.xp_data)
            save_json(BIRTHDAYS_FILE, bot.birthdays)
            save_json(WARNINGS_FILE, bot.warnings)
            save_json(BIRTHDAY_NOTIFICATIONS_FILE, bot.birthday_notifications)
            save_json(LEVEL_ROLES_FILE, bot.level_roles)
            save_json(REMINDERS_FILE, bot.reminders)
            save_json(IZUMI_MEMORIES_FILE, bot.izumi_memories)
            save_json(IZUMI_SELF_FILE, bot.izumi_self)
            save_json('data/osu_gacha.json', bot.osu_gacha_data)
            save_json('data/reaction_roles.json', bot.reaction_roles)
            save_json('data/auto_roles.json', bot.auto_roles)
            print('✅ synchronous save completed.')
        else:
            print('⚠️ bot data not available for sync save.')
    except Exception as e:
        print(f'❌ error in sync save: {e}')

signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    print("🚀 Starting Izumi Discord Bot...")
    
    # Load environment variables
    load_dotenv()
    TOKEN = os.getenv('DISCORD_TOKEN')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Check required environment variables
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN not found in .env file!")
        print("📝 Please add your Discord bot token to the .env file")
        exit(1)
    
    if not GEMINI_API_KEY:
        print("⚠️ Warning: GEMINI_API_KEY not found in .env file!")
        print("📝 AI features will not work without this token")
    
    print("✅ Environment variables loaded")
    
    try:
        bot = MinimalBot()
        print("✅ Bot instance created successfully")
    except Exception as e:
        print(f"❌ Failed to create bot instance: {e}")
        exit(1)
    
    # add retry logic for connection issues
    max_retries = 3
    retry_count = 0
    
    print(f"🔗 Connecting to Discord...")
    
    while retry_count < max_retries:
        try:
            bot.run(TOKEN)
            break  # if successful, break out of loop
        except (aiohttp.client_exceptions.WSServerHandshakeError, AttributeError) as e:
            retry_count += 1
            print(f"❌ Connection failed (attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                print("🔄 Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print("💀 Max retries reached. Please check your internet connection and Discord's status.")
                break
        except discord.LoginFailure:
            print("❌ Invalid Discord token! Please check your .env file.")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            break
