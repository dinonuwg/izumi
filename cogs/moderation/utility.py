import discord
import os
import sys
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from discord.ext import commands
from discord import app_commands
from utils.config import *

# Load BOT_OWNER_ID from environment variable
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", "0"))  # Default to 0 if not set

class UtilityCog(commands.Cog, name="Utility"):
    def __init__(self, bot):
        self.bot = bot

    def parse_time_duration(self, time_str):
        """Parse various time formats into seconds"""
        time_str = time_str.lower().strip()
        
        # Remove common words
        time_str = re.sub(r'\bin\b|\bafter\b|\bfrom\b|\bnow\b', '', time_str).strip()
        
        # Pattern for extracting number and unit
        patterns = [
            # Standard patterns like "2 hours", "30 minutes", etc.
            r'(\d+(?:\.\d+)?)\s*(year|years|yr|yrs|y)',
            r'(\d+(?:\.\d+)?)\s*(month|months|mon|mons|mo)',
            r'(\d+(?:\.\d+)?)\s*(week|weeks|wk|wks|w)',
            r'(\d+(?:\.\d+)?)\s*(day|days|d)',
            r'(\d+(?:\.\d+)?)\s*(hour|hours|hr|hrs|h)',
            r'(\d+(?:\.\d+)?)\s*(minute|minutes|min|mins|m)',
            r'(\d+(?:\.\d+)?)\s*(second|seconds|sec|secs|s)',
        ]
        
        total_seconds = 0
        
        for pattern in patterns:
            matches = re.findall(pattern, time_str)
            for match in matches:
                value = float(match[0])
                unit = match[1]
                
                if unit in ['year', 'years', 'yr', 'yrs', 'y']:
                    total_seconds += value * 365 * 24 * 3600
                elif unit in ['month', 'months', 'mon', 'mons', 'mo']:
                    total_seconds += value * 30 * 24 * 3600
                elif unit in ['week', 'weeks', 'wk', 'wks', 'w']:
                    total_seconds += value * 7 * 24 * 3600
                elif unit in ['day', 'days', 'd']:
                    total_seconds += value * 24 * 3600
                elif unit in ['hour', 'hours', 'hr', 'hrs', 'h']:
                    total_seconds += value * 3600
                elif unit in ['minute', 'minutes', 'min', 'mins', 'm']:
                    total_seconds += value * 60
                elif unit in ['second', 'seconds', 'sec', 'secs', 's']:
                    total_seconds += value
        
        # If no matches found, try parsing as just a number (assume minutes)
        if total_seconds == 0:
            try:
                num = float(time_str)
                total_seconds = num * 60  # Default to minutes
            except ValueError:
                return None
        
        return int(total_seconds) if total_seconds > 0 else None

    def format_time_duration(self, seconds):
        """Format seconds into a human-readable duration"""
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            if hours > 0:
                return f"{days} day{'s' if days != 1 else ''} and {hours} hour{'s' if hours != 1 else ''}"
            return f"{days} day{'s' if days != 1 else ''}"

    @app_commands.command(name="remindme", description="Set a reminder for yourself or allow others to opt in")
    @app_commands.describe(
        time="Time duration (e.g., '2 hours', '30 min', '1d 6h', '45m')",
        message="The reminder message"
    )
    async def remindme_slash(self, interaction: discord.Interaction, time: str, *, message: str):
        """Set a reminder with flexible time parsing"""
        await self._handle_remindme(interaction, time, message, True)

    @commands.command(name="remindme", aliases=["remind", "reminder", "rm"])
    async def remindme_prefix(self, ctx: commands.Context, *, args: str):
        """Set a reminder for yourself or allow others to opt in
        
        Usage: !remindme <time> <message>
        
        Time examples:
        - 2 hours, 2h, 2hr
        - 30 minutes, 30min, 30m
        - 1 day, 1d
        - 2d 6h 30m (combines units)
        - 45 (defaults to minutes)
        """
        # Parse the arguments manually to handle quoted messages
        args = args.strip()
        
        # Try to find where the time part ends and message begins
        # Look for common patterns that indicate end of time
        time_part = ""
        message_part = ""
        
        # Split by words to analyze
        words = args.split()
        if not words:
            from utils.helpers import show_command_usage
            await show_command_usage(
                ctx, "remindme",
                description="Set a reminder for yourself or allow others to opt in",
                usage_examples=[
                    f"{COMMAND_PREFIX}remindme 1 hour take out dishes",
                    f"{COMMAND_PREFIX}remind 30 minutes check the oven",
                    f"{COMMAND_PREFIX}rm 2d 6h 30m important meeting",
                    f"{COMMAND_PREFIX}reminder 45 default to minutes"
                ],
                notes=[
                    "Time formats: 2h, 30min, 1d, 2d 6h 30m",
                    "Bare numbers default to minutes",
                    "Can combine multiple time units"
                ]
            )
            return
        
        # Try to parse different combinations to find valid time
        # Prefer explicit units but don't go beyond reasonable time phrases
        best_match = None
        
        for i in range(1, min(len(words) + 1, 4)):  # Limit to max 3 words for time
            potential_time = " ".join(words[:i])
            duration = self.parse_time_duration(potential_time)
            
            if duration is not None:
                has_explicit_unit = any(unit in potential_time.lower() for unit in 
                                     ['hour', 'hours', 'minute', 'minutes', 'day', 'days', 
                                      'week', 'weeks', 'month', 'months', 'year', 'years',
                                      'hr', 'hrs', 'min', 'mins', 'sec', 'secs', 'h', 'm', 'd', 'w', 'y'])
                
                # If this has explicit units, use it and stop looking
                if has_explicit_unit:
                    best_match = (potential_time, " ".join(words[i:]) if i < len(words) else "")
                    break
                # Otherwise, keep it as a fallback but continue looking
                elif best_match is None:
                    best_match = (potential_time, " ".join(words[i:]) if i < len(words) else "")
        
        if best_match:
            time_part, message_part = best_match
        else:
            # Final fallback: assume first word is time
            time_part = words[0]
            message_part = " ".join(words[1:]) if len(words) > 1 else ""
        
        # Clean up quoted message
        message_part = message_part.strip()
        if message_part.startswith('"') and message_part.endswith('"'):
            message_part = message_part[1:-1]
        elif message_part.startswith("'") and message_part.endswith("'"):
            message_part = message_part[1:-1]
        
        if not message_part:
            await ctx.send("Please provide a reminder message. Example: `!remindme 1 hour take out dishes`")
            return
        
        await self._handle_remindme(ctx, time_part, message_part, False)

    async def _handle_remindme(self, ctx_or_interaction, time_str, message, is_slash):
        """Handle reminder creation for both slash and prefix commands"""
        # Parse the time duration
        duration_seconds = self.parse_time_duration(time_str)
        
        if duration_seconds is None:
            error_msg = f"Invalid time format: `{time_str}`. Examples: `2 hours`, `30 min`, `1d 6h`, `45m`"
            if is_slash:
                await ctx_or_interaction.response.send_message(error_msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(error_msg)
            return
        
        # Limit to reasonable time ranges
        if duration_seconds < 60:  # Less than 1 minute
            error_msg = "Minimum reminder time is 1 minute."
            if is_slash:
                await ctx_or_interaction.response.send_message(error_msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(error_msg)
            return
        
        if duration_seconds > 365 * 24 * 3600:  # More than 1 year
            error_msg = "Maximum reminder time is 1 year."
            if is_slash:
                await ctx_or_interaction.response.send_message(error_msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(error_msg)
            return
        
        # Create reminder
        current_time = time.time()
        trigger_time = current_time + duration_seconds
        reminder_id = str(uuid.uuid4())
        
        user = ctx_or_interaction.user if is_slash else ctx_or_interaction.author
        guild = ctx_or_interaction.guild
        channel = ctx_or_interaction.channel
        
        # Store reminder data
        self.bot.reminders[reminder_id] = {
            "creator_id": user.id,
            "guild_id": guild.id,
            "channel_id": channel.id,
            "message": message,
            "created_time": current_time,
            "trigger_time": trigger_time,
            "users": [user.id]  # Creator is automatically opted in
        }
        
        self.bot.pending_saves = True
        
        # Format response
        time_formatted = self.format_time_duration(duration_seconds)
        trigger_timestamp = f"<t:{int(trigger_time)}:F>"
        
        embed = discord.Embed(
            title="⏰ Reminder Set",
            description=f"**Message:** {message}\n**Time:** {time_formatted}\n**When:** {trigger_timestamp}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Reminder ID: {reminder_id[:8]}... • Others can react with ⏰ to opt in")
        
        if is_slash:
            await ctx_or_interaction.response.send_message(embed=embed)
            response_msg = await ctx_or_interaction.original_response()
        else:
            response_msg = await ctx_or_interaction.send(embed=embed)
        
        # Add reaction for others to opt in
        try:
            await response_msg.add_reaction("⏰")
        except discord.Forbidden:
            pass  # Bot doesn't have permission to add reactions

    @app_commands.command(name="reminders", description="View your active reminders")
    async def reminders_slash(self, interaction: discord.Interaction):
        """View active reminders"""
        await self._handle_reminders_list(interaction, True)

    @commands.command(name="reminders", aliases=["myreminders", "listreminders"])
    async def reminders_prefix(self, ctx: commands.Context):
        """View your active reminders"""
        await self._handle_reminders_list(ctx, False)

    async def _handle_reminders_list(self, ctx_or_interaction, is_slash):
        """Handle listing reminders for both slash and prefix commands"""
        user = ctx_or_interaction.user if is_slash else ctx_or_interaction.author
        user_reminders = []
        
        current_time = time.time()
        
        for reminder_id, reminder_data in self.bot.reminders.items():
            if user.id in reminder_data["users"]:
                time_left = reminder_data["trigger_time"] - current_time
                if time_left > 0:  # Only show future reminders
                    user_reminders.append((reminder_id, reminder_data, time_left))
        
        if not user_reminders:
            msg = "You have no active reminders."
            if is_slash:
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)
            return
        
        # Sort by time remaining
        user_reminders.sort(key=lambda x: x[2])
        
        embed = discord.Embed(
            title=f"⏰ Active Reminders ({len(user_reminders)})",
            color=discord.Color.blue()
        )
        
        for i, (reminder_id, reminder_data, time_left) in enumerate(user_reminders[:10]):  # Limit to 10
            time_formatted = self.format_time_duration(int(time_left))
            trigger_timestamp = f"<t:{int(reminder_data['trigger_time'])}:R>"
            
            message_preview = reminder_data["message"]
            if len(message_preview) > 50:
                message_preview = message_preview[:47] + "..."
            
            embed.add_field(
                name=f"{i+1}. {message_preview}",
                value=f"**In:** {time_formatted}\n**When:** {trigger_timestamp}\n**ID:** `{reminder_id[:8]}`",
                inline=True
            )
        
        if len(user_reminders) > 10:
            embed.set_footer(text=f"Showing 10 of {len(user_reminders)} reminders")
        
        if is_slash:
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await ctx_or_interaction.send(embed=embed)

    @app_commands.command(name="cancelreminder", description="Cancel one of your reminders")
    @app_commands.describe(reminder_id="The reminder ID (first 8 characters)")
    async def cancel_reminder_slash(self, interaction: discord.Interaction, reminder_id: str):
        """Cancel a reminder"""
        await self._handle_cancel_reminder(interaction, reminder_id, True)

    @commands.command(name="cancelreminder", aliases=["delreminder", "removereminder", "cancelrem"])
    async def cancel_reminder_prefix(self, ctx: commands.Context, reminder_id: str):
        """Cancel one of your reminders
        
        Usage: !cancelreminder <reminder_id>
        Get the reminder ID from !reminders
        """
        await self._handle_cancel_reminder(ctx, reminder_id, False)

    async def _handle_cancel_reminder(self, ctx_or_interaction, reminder_id_input, is_slash):
        """Handle reminder cancellation for both slash and prefix commands"""
        user = ctx_or_interaction.user if is_slash else ctx_or_interaction.author
        
        # Find matching reminder
        matching_reminder = None
        for full_id, reminder_data in self.bot.reminders.items():
            if full_id.startswith(reminder_id_input) and user.id in reminder_data["users"]:
                matching_reminder = (full_id, reminder_data)
                break
        
        if not matching_reminder:
            msg = f"No reminder found with ID starting with `{reminder_id_input}` that you're subscribed to."
            if is_slash:
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)
            return
        
        full_id, reminder_data = matching_reminder
        
        # If user is the creator and only person subscribed, delete the reminder
        if reminder_data["creator_id"] == user.id and len(reminder_data["users"]) == 1:
            del self.bot.reminders[full_id]
            msg = f"✅ Reminder deleted: `{reminder_data['message'][:50]}{'...' if len(reminder_data['message']) > 50 else ''}`"
        else:
            # Just remove user from the reminder
            reminder_data["users"].remove(user.id)
            msg = f"✅ You've been removed from reminder: `{reminder_data['message'][:50]}{'...' if len(reminder_data['message']) > 50 else ''}`"
        
        self.bot.pending_saves = True
        
        if is_slash:
            await ctx_or_interaction.response.send_message(msg, ephemeral=True)
        else:
            await ctx_or_interaction.send(msg)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle users opting into reminders via reactions"""
        if payload.user_id == self.bot.user.id:
            return  # Ignore bot's own reactions
        
        if str(payload.emoji) != "⏰":
            return  # Only handle clock emoji
        
        # Get the message
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
        
        try:
            message = await channel.fetch_message(payload.message_id)
        except (discord.NotFound, discord.Forbidden):
            return
        
        # Check if it's a reminder message from the bot
        if message.author.id != self.bot.user.id:
            return
        
        if not message.embeds or not message.embeds[0].title == "⏰ Reminder Set":
            return
        
        # Extract reminder ID from footer
        footer_text = message.embeds[0].footer.text
        if not footer_text or "Reminder ID:" not in footer_text:
            return
        
        try:
            reminder_id_short = footer_text.split("Reminder ID: ")[1].split("...")[0]
        except (IndexError, AttributeError):
            return
        
        # Find the full reminder ID
        matching_reminder = None
        for full_id, reminder_data in self.bot.reminders.items():
            if full_id.startswith(reminder_id_short):
                matching_reminder = (full_id, reminder_data)
                break
        
        if not matching_reminder:
            return  # Reminder not found or already triggered
        
        full_id, reminder_data = matching_reminder
        
        # Add user to reminder if not already added
        if payload.user_id not in reminder_data["users"]:
            reminder_data["users"].append(payload.user_id)
            self.bot.pending_saves = True
            
            # Try to DM the user confirmation
            try:
                user = self.bot.get_user(payload.user_id)
                if user:
                    embed = discord.Embed(
                        title="⏰ Added to Reminder",
                        description=f"You'll be notified: {reminder_data['message']}",
                        color=discord.Color.green()
                    )
                    trigger_timestamp = f"<t:{int(reminder_data['trigger_time'])}:R>"
                    embed.add_field(name="When", value=trigger_timestamp, inline=False)
                    await user.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                pass  # User has DMs disabled or other error

    @app_commands.command(name="help", description="Shows information about available commands.")
    @app_commands.describe(command_name="The specific command to get help for (optional).")
    async def custom_help_slash(self, interaction: discord.Interaction, command_name: str = None):
        if command_name:
            command = None
            for cmd_obj in self.bot.tree.get_commands():
                if cmd_obj.name == command_name:
                    command = cmd_obj
                    break
            
            if command:
                embed = discord.Embed(title=f"Help: /{command.name}", description=command.description or "No description provided.", color=discord.Color.blue())
                
                param_details = []
                for param_name, param_obj in command.parameters.items():
                    detail = f"`{param_obj.display_name or param_name}`"
                    if param_obj.description and param_obj.description != discord.utils.MISSING:
                         detail += f": {param_obj.description}"
                    if not param_obj.required:
                        detail += " (optional)"
                    param_details.append(detail)

                if param_details:
                    embed.add_field(name="Parameters", value="\n".join(param_details) or "None", inline=False)
                else:
                    embed.add_field(name="Usage", value=f"`/{command.name}`", inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(f"Command `{command_name}` not found.", ephemeral=True)
        else:
            embed = discord.Embed(title="Bot Commands", description="Here are the available slash commands. Use `/help <command>` for more info.", color=discord.Color.blue())
            
            categories = {"Moderation": [], "Birthdays": [], "Leveling": [], "Level Roles": [], "Osu Gacha": [], "Social": [], "Utility": []}
            
            all_commands = self.bot.tree.get_commands()
            for cmd in all_commands:
                category = "Utility"
                if cmd.name in ["warn", "warnings", "ban", "kick", "mute", "unmute"]: category = "Moderation"
                elif cmd.name in ["setbirthday", "birthday", "birthdays", "birthdaycountdown", "randombdfact", "notifybirthday"]: category = "Birthdays"
                elif cmd.name in ["level", "levels", "calculatexp"]: category = "Leveling"
                elif cmd.name in ["setlevelrole", "removelevelrole", "levelroles", "syncuserroles"]: category = "Level Roles"
                elif cmd.name.startswith("osu"): category = "Osu Gacha"
                elif cmd.name in ["kiss", "hug", "slap", "sex"]: category = "Social"
                elif cmd.name in ["remindme", "reminders", "cancelreminder"]: category = "Utility"

                cmd_desc = cmd.description.splitlines()[0] if cmd.description else "No description"
                categories[category].append(f"`/{cmd.name}`: {cmd_desc}")

            for category_name, cmd_list in categories.items():
                if cmd_list:
                    embed.add_field(name=category_name, value="\n".join(cmd_list), inline=False)
            
            if not any(categories.values()):
                embed.description = "No slash commands seem to be registered or an error occurred."
                
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # Prefix command versions
    @commands.command(name="help", aliases=["h", "commands", "cmd", "cmds"])
    async def help_prefix(self, ctx: commands.Context, *, command_name: str = None):
        """Shows information about available commands."""
        if command_name:
            command = self.bot.get_command(command_name)
            if command:
                embed = discord.Embed(title=f"Help: {COMMAND_PREFIX}{command.name}", description=command.help or "No description provided.", color=discord.Color.blue())
                
                aliases_str = ", ".join([f"`{COMMAND_PREFIX}{alias}`" for alias in command.aliases]) if command.aliases else "None"
                embed.add_field(name="Aliases", value=aliases_str, inline=False)
                
                usage = f"`{COMMAND_PREFIX}{command.name} {command.signature}`" if command.signature else f"`{COMMAND_PREFIX}{command.name}`"
                embed.add_field(name="Usage", value=usage, inline=False)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Command `{command_name}` not found.")
        else:
            embed = discord.Embed(title="Bot Commands", description=f"Here are the available prefix commands (using `{COMMAND_PREFIX}`). Use `{COMMAND_PREFIX}help <command>` for more info.", color=discord.Color.blue())
            
            categories = {
                "Moderation": ["warn", "warnings", "ban", "kick", "mute", "unmute"],
                "Birthdays": ["setbirthday", "birthday", "birthdays", "birthdaycountdown", "randombdfact", "notifybirthday"],
                "Leveling": ["level", "levels", "calculatexp"],
                "Level Roles": ["setlevelrole", "removelevelrole", "levelroles", "syncuserroles"],
                "Osu Gacha": ["osudaily", "osuopen", "osucards", "osubalance", "osusell", "osubuy", "osutrade", "osugamble"],
                "Social": ["kiss", "hug", "slap", "sex"],
                "Utility": ["help", "save", "shutdown", "restart", "remindme", "reminders", "cancelreminder"]
            }
            
            for category_name, cmd_names in categories.items():
                cmd_list = []
                for cmd_name in cmd_names:
                    cmd = self.bot.get_command(cmd_name)
                    if cmd:
                        aliases = f" (aliases: {', '.join(cmd.aliases[:3])}{'...' if len(cmd.aliases) > 3 else ''})" if cmd.aliases else ""
                        cmd_list.append(f"`{COMMAND_PREFIX}{cmd.name}`{aliases}")
                
                if cmd_list:
                    embed.add_field(name=category_name, value="\n".join(cmd_list), inline=False)
            
            embed.set_footer(text="💡 Most commands also work as slash commands (e.g., /birthday)")
            await ctx.send(embed=embed)

    @commands.command(name="shutdown", aliases=["stop", "quit", "exit"])
    @commands.is_owner()
    async def shutdown_command(self, ctx: commands.Context):
        """Shutdown the bot (Owner only)"""
        embed = discord.Embed(
            title="🛑 Bot Shutdown", 
            description="Saving data and shutting down...", 
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        
        # Save data before shutdown
        await self.bot.save_immediately()
        
        # Close the bot
        await self.bot.close()

    @commands.command(name="save", aliases=["forcesave", "backup"])
    @commands.has_permissions(administrator=True)
    async def manual_save_command(self, ctx: commands.Context):
        """Manually save all data (Admin only)"""
        try:
            await self.bot.save_immediately()
            embed = discord.Embed(
                title="💾 Data Saved", 
                description="All data has been saved to JSON files.", 
                color=discord.Color.green()
            )
        except Exception as e:
            embed = discord.Embed(
                title="❌ Save Error", 
                description=f"Error saving data: {e}", 
                color=discord.Color.red()
            )
        
        await ctx.send(embed=embed)

    @commands.command(name="restart", aliases=["reboot"])
    @commands.is_owner()
    async def restart_command(self, ctx: commands.Context):
        """Restart the bot (Owner only)"""
        embed = discord.Embed(
            title="🔄 Bot Restart", 
            description="Saving data and restarting...", 
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
        
        # Save data before restart
        await self.bot.save_immediately()
        
        # Use subprocess to preserve signal handling
        import subprocess
        import asyncio
        
        async def delayed_restart():
            await asyncio.sleep(0.5)  # Give time for message to send
            subprocess.Popen([sys.executable] + sys.argv)
            await self.bot.close()
            import os
            os._exit(0)
        
        # Schedule restart without blocking
        asyncio.create_task(delayed_restart())

    @commands.command(name='proactive', aliases=['unprompted', 'izumi_talk'])
    @commands.has_permissions(administrator=True)
    async def trigger_proactive_message(self, ctx):
        """Manually trigger a proactive message from Izumi (admin only)"""
        # Access unified memory system directly from bot
        if not hasattr(self.bot, 'unified_memory'):
            await ctx.send("❌ Unified memory system not available")
            return
            
        try:
            result = await self.bot.unified_memory.send_unprompted_message(self.bot, channel_id=ctx.channel.id)
            if result:
                await ctx.send(f"✅ Triggered proactive message!", delete_after=5)
            else:
                await ctx.send("ℹ️ No proactive message was appropriate right now", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @commands.command(name='birthday_ping', aliases=['testbirthdayping', 'bdping'])
    @commands.has_permissions(administrator=True)
    async def test_birthday_ping(self, ctx):
        """Manually test the birthday ping system (admin only)"""
        unified_memory = self.bot.get_cog('UnifiedMemory')
        if not unified_memory:
            await ctx.send("❌ Unified memory system not available")
            return
            
        try:
            result = await unified_memory.send_random_birthday_ping(self.bot)
            if result:
                await ctx.send(f"✅ Birthday ping sent: {result}", delete_after=10)
            else:
                await ctx.send("ℹ️ No birthday users found or cooldown active", delete_after=10)
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

    @app_commands.command(name="prefixcommands", description="[OWNER] View all available prefix commands")
    async def prefix_commands_reference(self, interaction: discord.Interaction):
        """Shows all available prefix commands (bot owner only)"""
        if interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌ Only the bot owner can use this command.", ephemeral=True)
            return
        
        # Comprehensive list of all prefix commands organized by category
        commands_data = {
            "🤖 **AI & Memory Commands**": [
                "`!memory <user>` - View memories about a user",
                "`!memory add <user> <note>` - Add a custom note about a user",
                "`!memory set <user> <field> <value>` - Set a specific memory field",
                "`!memory trust <user> <level>` - Set trust level (-10 to 10)",
                "`!memory relate <user1> <user2> <relationship>` - Set relationship",
                "`!memory shared <user1> <user2> <experience>` - Add shared experience",
                "`!memory context <user>` - View social context for a user",
                "`!memory clear <user>` - Clear all memories about a user",
                "`!memory forget <user>` - Clear conversation history",
                "`!memory self` - View Izumi's self-memories",
                "`!memory selftest` - Test self-memory system",
                "`!memory selfadd <category> <value>` - Add self-memory",
                "`!memory selfclear <category>` - Clear self-memory category",
                "`!train [channel] [limit]` - Train on channel messages",
                "`!trainall [limit]` - Train on all server channels"
            ],
            "🛠️ **Admin & Utility Commands**": [
                "`!shutdown` - Shut down the bot",
                "`!save` - Force save all data",
                "`!restart` - Restart the bot",
                "`!proactive <on/off>` - Toggle proactive responses",
                "`!birthday_ping` - Test birthday ping system",
                "`!remind <time> <message>` - Set a reminder",
                "`!reminders` - View your reminders",
                "`!cancel_reminder <id>` - Cancel a reminder"
            ],
            "🎮 **Osu! Gacha Commands**": [
                "`!osugive <user> <coins/player> [mutation]` - Give coins or cards",
                "`!osusimulate <crate_type> [amount]` - Simulate crate openings",
                "`!osupity <user>` - Add/remove user from pity list",
                "`!osuparty <mode> [args...]` - Manage osu party events",
                "`!osureset <user>` - Reset user's gacha data",
                "`!osuaddcard <user> <player> [mutation]` - Add card to user",
                "`!osuremovecard <user> <card_id>` - Remove card from user",
                "`!osusetcoins <user> <amount>` - Set user's coin amount",
                "`!osuimport` - Import card data from JSON",
                "`!osuexport <user>` - Export user's card data"
            ],
            "👥 **Moderation Commands**": [
                "`!warn <user> [reason]` - Warn a user",
                "`!warnings <user>` - View user's warnings",
                "`!clearwarnings <user>` - Clear user's warnings",
                "`!mute <user> [time] [reason]` - Mute a user",
                "`!unmute <user>` - Unmute a user",
                "`!kick <user> [reason]` - Kick a user",
                "`!ban <user> [reason]` - Ban a user",
                "`!unban <user>` - Unban a user",
                "`!purge <amount>` - Delete messages"
            ],
            "🎂 **Birthday & Social Commands**": [
                "`!setbirthday <DD/MM>` - Set your birthday",
                "`!birthday [user]` - View birthday info",
                "`!birthdays` - List upcoming birthdays",
                "`!clearbirthday` - Clear your birthday",
                "`!rep <user>` - Give reputation points",
                "`!profile [user]` - View user profile",
                "`!leaderboard [page]` - View XP leaderboard"
            ],
            "🔧 **Level & Role Commands**": [
                "`!level [user]` - Check XP/level",
                "`!setlevel <user> <level>` - Set user's level",
                "`!addxp <user> <amount>` - Add XP to user",
                "`!levelroles` - View level roles",
                "`!addlevelrole <level> <role>` - Add level role",
                "`!removelevelrole <level>` - Remove level role"
            ]
        }
        
        # Create embeds (split due to Discord's character limits)
        embeds = []
        current_embed = discord.Embed(
            title="📋 Complete Prefix Commands Reference",
            description="All available prefix commands organized by category.\n*Note: Many admin commands were removed as slash commands to stay under Discord's 100 command limit.*",
            color=discord.Color.blue()
        )
        
        for category, commands in commands_data.items():
            # Check if adding this category would exceed Discord's field limits
            commands_text = "\n".join(commands)
            
            if len(current_embed.fields) >= 6 or len(current_embed) + len(commands_text) > 5500:
                # Start a new embed
                embeds.append(current_embed)
                current_embed = discord.Embed(
                    title="📋 Prefix Commands Reference (continued)",
                    color=discord.Color.blue()
                )
            
            current_embed.add_field(
                name=category,
                value=commands_text,
                inline=False
            )
        
        # Add the last embed
        if current_embed.fields:
            embeds.append(current_embed)
        
        # Add footer to the last embed
        if embeds:
            embeds[-1].set_footer(text=f"Total categories: {len(commands_data)} | Use these commands with the bot's prefix!")
        
        # Send all embeds
        await interaction.response.send_message(embed=embeds[0], ephemeral=True)
        
        for embed in embeds[1:]:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="pfp", description="Display a user's profile picture")
    @app_commands.describe(user="The user whose profile picture to display (defaults to yourself)")
    async def pfp_slash(self, interaction: discord.Interaction, user: discord.Member = None):
        """Display a user's profile picture"""
        await self._handle_pfp(interaction, user, True)
    
    @commands.command(name="pfp", aliases=["avatar", "av", "profilepic", "profilepicture"])
    async def pfp_prefix(self, ctx: commands.Context, user: discord.Member = None):
        """Display a user's profile picture
        
        Usage: 
        - !pfp - Shows your own profile picture
        - !pfp @user - Shows mentioned user's profile picture
        - +pfp @user - Also works with + prefix
        """
        await self._handle_pfp(ctx, user, False)
    
    async def _handle_pfp(self, ctx_or_interaction, user, is_slash):
        """Handle PFP command for both slash and prefix commands"""
        # Default to command author if no user specified
        if user is None:
            user = ctx_or_interaction.user if is_slash else ctx_or_interaction.author
        
        # Get the user's avatar URL
        # Use display_avatar which respects server-specific avatars
        avatar_url = user.display_avatar.url
        
        # Also get the global avatar URL if different from server avatar
        global_avatar_url = user.avatar.url if user.avatar else None
        
        # Create embed
        embed = discord.Embed(
            title=f"{user.display_name}'s Profile Picture",
            color=user.color if user.color != discord.Color.default() else discord.Color.blue()
        )
        
        # Set the main image to the display avatar (server-specific or global)
        embed.set_image(url=avatar_url)
        
        # Add download link
        embed.add_field(
            name="🔗 Links",
            value=f"[Download]({avatar_url})",
            inline=False
        )
        
        # If there's a different global avatar, mention it
        if global_avatar_url and global_avatar_url != avatar_url:
            embed.add_field(
                name="📎 Global Avatar",
                value=f"[View Global Avatar]({global_avatar_url})",
                inline=False
            )
            embed.set_footer(text="Showing server-specific avatar")
        
        # Send response
        if is_slash:
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)

async def setup(bot):
    await bot.add_cog(UtilityCog(bot))