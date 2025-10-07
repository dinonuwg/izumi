import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
from utils.helpers import *
from utils.config import *
import re
import asyncio

class ModerationCog(commands.Cog, name="Moderation"):
    def __init__(self, bot):
        self.bot = bot

    def parse_duration(self, duration_str: str) -> int:
        """Parse duration string (e.g., '5m', '1h', '2d') to seconds"""
        if not duration_str:
            return 300  # Default 5 minutes
        
        # Match number and unit
        match = re.match(r'^(\d+)([smhd]?)$', duration_str.lower())
        if not match:
            return 300  # Default if invalid format
        
        amount, unit = match.groups()
        amount = int(amount)
        
        multipliers = {
            's': 1,      # seconds
            'm': 60,     # minutes
            'h': 3600,   # hours
            'd': 86400,  # days
            '': 60       # default to minutes if no unit
        }
        
        return amount * multipliers.get(unit, 60)

    def create_compact_embed(self, member: discord.Member, action: str, reason: str, duration: str = None):
        """Create a compact minimalistic embed with user avatar"""
        embed = discord.Embed(color=0x2b2d31)
        
        description = ""
        if reason:
            description += f"**Reason : **{reason}\n"
        if duration:
            description += f"**Duration : **{duration}\n"
        
        embed.description = description
        embed.set_author(name=f"{member.display_name} has been {action}", icon_url=member.display_avatar.url)
        
        return embed
    
    @app_commands.command(name="reactionroles", description="Set up reaction roles in a channel (Admin only).")
    @app_commands.describe(
        channel="The channel to send the reaction role message",
        message="The message content to display",
        role_pairs="Emoji-role pairs (format: emoji1:@role1 emoji2:@role2)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def reactionroles_slash(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str, role_pairs: str):
        """Set up reaction roles with emoji-role pairs"""
        try:
            # Parse emoji-role pairs
            pairs = role_pairs.split()
            reaction_data = []
            
            for pair in pairs:
                if ':' not in pair:
                    await interaction.response.send_message("❌ Invalid format! Use: `emoji1:@role1 emoji2:@role2`\nExample: `🔴:@Red 🔵:@Blue`", ephemeral=True)
                    return
                
                emoji_part, role_part = pair.split(':', 1)
                
                # Extract role ID from mention
                role_id_match = re.search(r'<@&(\d+)>', role_part)
                if not role_id_match:
                    await interaction.response.send_message(f"❌ Invalid role format: {role_part}\nUse @role mentions like @Red", ephemeral=True)
                    return
                
                role_id = int(role_id_match.group(1))
                role = interaction.guild.get_role(role_id)
                
                if not role:
                    await interaction.response.send_message(f"❌ Role not found: {role_part}", ephemeral=True)
                    return
                
                # Check if bot can manage the role
                if role >= interaction.guild.me.top_role:
                    await interaction.response.send_message(f"❌ I cannot manage {role.mention} - it's higher than my highest role!", ephemeral=True)
                    return
                
                reaction_data.append({'emoji': emoji_part, 'role': role})
            
            if not reaction_data:
                await interaction.response.send_message("❌ No valid emoji-role pairs provided!", ephemeral=True)
                return
            
            if len(reaction_data) > 20:
                await interaction.response.send_message("❌ Too many reaction roles! Maximum is 20.", ephemeral=True)
                return
            
            await interaction.response.defer()
            
            # Create embed for the reaction role message
            embed = discord.Embed(
                title=message,
                description="",
                color=discord.Color.blue()
            )
            
            # Add role information to embed
            role_info = ""
            for item in reaction_data:
                role_info += f"{item['emoji']} - <@&{item['role'].id}>\n"
            
            embed.add_field(name="Available Roles", value=role_info, inline=False)
            embed.set_footer(text="React with an emoji to get the role, unreact to remove it!")
            
            # Send the message
            sent_message = await channel.send(embed=embed)
            
            # Add reactions
            for item in reaction_data:
                try:
                    await sent_message.add_reaction(item['emoji'])
                except discord.HTTPException:
                    await interaction.followup.send(f"❌ Failed to add reaction {item['emoji']} - invalid emoji?", ephemeral=True)
                    return
            
            # Store reaction role data
            guild_id_str = str(interaction.guild.id)
            message_id_str = str(sent_message.id)
            
            if not hasattr(self.bot, 'reaction_roles'):
                self.bot.reaction_roles = {}
            
            if guild_id_str not in self.bot.reaction_roles:
                self.bot.reaction_roles[guild_id_str] = {}
            
            self.bot.reaction_roles[guild_id_str][message_id_str] = {
                'channel_id': str(channel.id),
                'roles': {item['emoji']: str(item['role'].id) for item in reaction_data}
            }
            
            await self.bot.save_immediately()
            
            # Success message
            embed = discord.Embed(
                title="✅ Reaction Roles Set Up",
                description=f"Successfully created reaction roles in {channel.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Roles Added", value=f"{len(reaction_data)} roles", inline=True)
            embed.add_field(name="Message ID", value=str(sent_message.id), inline=True)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            if hasattr(interaction, 'response') and not interaction.response.is_done():
                await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ {error_msg}", ephemeral=True)

    @app_commands.command(name="spam", description="Spam messages in the current channel (Admin only).")
    @app_commands.describe(
        amount="Number of messages to spam (1-100)",
        message="The message content to spam"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def spam_slash(self, interaction: discord.Interaction, amount: int, message: str):
        """Spam messages in the channel"""
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        if len(message) > 2000:
            await interaction.response.send_message("❌ Message is too long! Maximum is 2000 characters.", ephemeral=True)
            return
        
        # Check if message contains mentions or @everyone/@here
        if "@everyone" in message or "@here" in message or "<@" in message:
            await interaction.response.send_message("❌ Cannot spam messages with mentions or @everyone/@here!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Send the spam messages
            for i in range(amount):
                try:
                    await interaction.channel.send(message)
                    # Small delay to avoid rate limits
                    if i % 5 == 0 and i > 0:
                        await asyncio.sleep(0.5)
                except discord.HTTPException as e:
                    await interaction.followup.send(f"❌ Error sending message {i+1}: Rate limited or other error", ephemeral=True)
                    break
                except Exception as e:
                    await interaction.followup.send(f"❌ Error sending message {i+1}: {str(e)}", ephemeral=True)
                    break
            
            embed = discord.Embed(
                title="✅ Spam Complete",
                description=f"Successfully sent **{amount}** messages",
                color=discord.Color.green()
            )
            embed.add_field(name="Message", value=f"`{message[:100]}{'...' if len(message) > 100 else ''}`", inline=False)
            embed.set_footer(text=f"Spammed by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="purge", description="Delete messages from the channel.")
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        member="Optional: Only delete messages from this member"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    async def purge_slash(self, interaction: discord.Interaction, amount: int, member: discord.Member = None):
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            if member:
                # Purge messages from specific user
                def check(message):
                    return message.author == member
                
                deleted = await interaction.channel.purge(limit=amount * 2, check=check)  # Check more messages to find user's messages
                deleted = [msg for msg in deleted if msg.author == member][:amount]  # Limit to requested amount
                
                embed = discord.Embed(
                    title="🗑️ Messages Purged",
                    description=f"Deleted **{len(deleted)}** messages from {member.mention}",
                    color=discord.Color.green()
                )
            else:
                # Purge any messages
                deleted = await interaction.channel.purge(limit=amount)
                
                embed = discord.Embed(
                    title="🗑️ Messages Purged", 
                    description=f"Deleted **{len(deleted)}** messages",
                    color=discord.Color.green()
                )
            
            embed.set_footer(text=f"Purged by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to delete messages in this channel.")
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}")


    @app_commands.command(name="warn", description="Warns a member.")
    @app_commands.describe(member="The member to warn.", reason="The reason for the warning.")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.bot:
            await interaction.response.send_message("You cannot warn bots.", ephemeral=True)
            return
        if member == interaction.user:
            await interaction.response.send_message("You cannot warn yourself.", ephemeral=True)
            return

        guild_id_str = str(interaction.guild.id)
        user_id_str = str(member.id)

        if guild_id_str not in self.bot.warnings:
            self.bot.warnings[guild_id_str] = {}
        if user_id_str not in self.bot.warnings[guild_id_str]:
            self.bot.warnings[guild_id_str][user_id_str] = []

        warning_entry = {
            "reason": reason,
            "moderator_id": str(interaction.user.id),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.bot.warnings[guild_id_str][user_id_str].append(warning_entry)
        
        embed = self.create_compact_embed(member, "warned", reason)
        
        await interaction.response.send_message(embed=embed)
        await self.bot.save_immediately()

    @app_commands.command(name="mute", description="Mutes a member for a specified duration.")
    @app_commands.describe(
        member="The member to mute.",
        duration="Duration (e.g., 5m, 1h, 2d). Default is 5 minutes.",
        reason="The reason for the mute."
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def mute_slash(self, interaction: discord.Interaction, member: discord.Member, duration: str = "5m", reason: str = "No reason provided"):
        if member.bot:
            await interaction.response.send_message("You cannot mute bots.", ephemeral=True)
            return
        if member == interaction.user:
            await interaction.response.send_message("You cannot mute yourself.", ephemeral=True)
            return
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("You can't mute someone with an equal or higher role.", ephemeral=True)
            return
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("I can't mute someone with an equal or higher role than me.", ephemeral=True)
            return

        # Parse duration
        duration_seconds = self.parse_duration(duration)
        duration_td = timedelta(seconds=duration_seconds)
        
        # Format duration for display
        if duration_seconds < 60:
            duration_display = f"{duration_seconds} seconds"
        elif duration_seconds < 3600:
            duration_display = f"{duration_seconds // 60} minutes"
        elif duration_seconds < 86400:
            duration_display = f"{duration_seconds // 3600} hours"
        else:
            duration_display = f"{duration_seconds // 86400} days"

        try:
            await member.timeout(duration_td, reason=f"Muted by {interaction.user.name}: {reason}")
            
            embed = self.create_compact_embed(member, "muted", reason, duration_display)
            
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to mute this member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="unmute", description="Unmutes a member.")
    @app_commands.describe(member="The member to unmute.", reason="The reason for the unmute.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def unmute_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.bot:
            await interaction.response.send_message("Bots cannot be muted or unmuted.", ephemeral=True)
            return
        if member == interaction.user:
            await interaction.response.send_message("You cannot unmute yourself.", ephemeral=True)
            return
        if not member.is_timed_out():
            await interaction.response.send_message(f"{member.mention} is not currently muted.", ephemeral=True)
            return

        try:
            await member.timeout(None, reason=f"Unmuted by {interaction.user.name}: {reason}")
            
            embed = self.create_compact_embed(member, "unmuted", reason)
            
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to unmute this member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)    

    @app_commands.command(name="kick", description="Kicks a member from the server.")
    @app_commands.describe(member="The member to kick.", reason="The reason for the kick.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member == interaction.user:
            await interaction.response.send_message("You can't kick yourself.", ephemeral=True)
            return
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("You can't kick someone with an equal or higher role.", ephemeral=True)
            return
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("I can't kick someone with an equal or higher role than me.", ephemeral=True)
            return

        await member.kick(reason=f"Kicked by {interaction.user.name}: {reason}")
        
        embed = self.create_compact_embed(member, "kicked", reason)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ban", description="Bans a member from the server.")
    @app_commands.describe(member="The member to ban.", reason="The reason for the ban.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member == interaction.user:
            await interaction.response.send_message("You can't ban yourself.", ephemeral=True)
            return
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("You can't ban someone with an equal or higher role.", ephemeral=True)
            return
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message("I can't ban someone with an equal or higher role than me.", ephemeral=True)
            return

        await member.ban(reason=f"Banned by {interaction.user.name}: {reason}")
        
        embed = self.create_compact_embed(member, "banned", reason)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warnings", description="Checks warnings for a user.")
    @app_commands.describe(member="The member to check warnings for (defaults to yourself).")
    async def warnings_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user

        guild_id_str = str(interaction.guild.id)
        user_id_str = str(member.id)

        user_warnings = self.bot.warnings.get(guild_id_str, {}).get(user_id_str, [])

        if not user_warnings:
            embed = discord.Embed(color=0x2b2d31)
            embed.description = f"This user has a clean record."
            embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(color=0x2b2d31)
        embed.set_author(name=f"{member.display_name} has {len(user_warnings)} warning(s)", icon_url=member.display_avatar.url)
        
        warnings_text = ""
        for i, warn_entry in enumerate(user_warnings[-3:], 1):  # Show last 3 warnings
            mod_user = interaction.guild.get_member(int(warn_entry["moderator_id"]))
            mod_display = mod_user.display_name if mod_user else f"ID: {warn_entry['moderator_id']}"
            try:
                warn_time = datetime.fromisoformat(warn_entry['timestamp'])
                time_str = format_discord_timestamp(warn_time.timestamp(), "R")
            except:
                time_str = "Unknown time"
            warnings_text += f"**#{len(user_warnings) - len(user_warnings[-3:]) + i}** {warn_entry['reason']} • {time_str}\n"
        
        if warnings_text:
            embed.add_field(name="Recent Warnings", value=warnings_text.strip(), inline=False)
        
        await interaction.response.send_message(embed=embed)

    # Prefix command versions (same style as slash commands)

    @commands.command(name="spam", aliases=["spammsg", "repeat"])
    @commands.has_permissions(administrator=True)
    async def spam_prefix(self, ctx: commands.Context, amount: int = None, *, message: str = None):
        """Spam messages - Usage: !spam 50 "your message here" """
        
        if amount is None or message is None:
            await ctx.send("❌ Usage: `!spam <amount> \"your message\"`\nExample: `!spam 10 \"hello world\"`")
            return
        
        if amount < 1 or amount > 100:
            await ctx.send("❌ Amount must be between 1 and 100.")
            return
        
        if len(message) > 2000:
            await ctx.send("❌ Message is too long! Maximum is 2000 characters.")
            return
        
        # Check if message contains mentions or @everyone/@here
        if "@everyone" in message or "@here" in message or "<@" in message:
            await ctx.send("❌ Cannot spam messages with mentions or @everyone/@here!")
            return
        
        # Delete the command message first
        try:
            await ctx.message.delete()
        except:
            pass
        
        try:
            # Send confirmation
            confirm_msg = await ctx.send(f"🚀 Starting spam: {amount} messages...")
            
            # Send the spam messages
            successful_sends = 0
            for i in range(amount):
                try:
                    await ctx.send(message)
                    successful_sends += 1
                    # Small delay to avoid rate limits
                    if i % 5 == 0 and i > 0:
                        await asyncio.sleep(0.5)
                except discord.HTTPException:
                    break  # Stop if rate limited
                except Exception:
                    break  # Stop on other errors
            
            # Edit confirmation with results
            embed = discord.Embed(
                title="✅ Spam Complete",
                description=f"Successfully sent **{successful_sends}/{amount}** messages",
                color=discord.Color.green()
            )
            embed.add_field(name="Message", value=f"`{message[:100]}{'...' if len(message) > 100 else ''}`", inline=False)
            embed.set_footer(text=f"Spammed by {ctx.author.display_name}")
            
            try:
                await confirm_msg.edit(content=None, embed=embed)
                # Delete confirmation after 5 seconds
                await asyncio.sleep(5)
                await confirm_msg.delete()
            except:
                pass
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")

    @commands.command(name="reactionroles", aliases=["rr", "reactionrole"])
    @commands.has_permissions(administrator=True)
    async def reactionroles_prefix(self, ctx: commands.Context, channel: discord.TextChannel = None, *, args: str = None):
        """Set up reaction roles - Usage: !reactionroles #channel "message" emoji1:@role1 emoji2:@role2"""
        if not channel or not args:
            await ctx.send("❌ Usage: `!reactionroles #channel \"Your message here\" 🔴:@Role1 🔵:@Role2`")
            return
        
        # Parse message and role pairs from args
        # Expected format: "message text" emoji1:@role1 emoji2:@role2
        args = args.strip()
        
        # Extract message (should be in quotes)
        if args.startswith('"'):
            end_quote = args.find('"', 1)
            if end_quote == -1:
                await ctx.send("❌ Message must be in quotes! Example: `\"React to get roles!\"`")
                return
            message = args[1:end_quote]
            role_pairs = args[end_quote + 1:].strip()
        else:
            await ctx.send("❌ Message must be in quotes! Example: `\"React to get roles!\"`")
            return
        
        if not role_pairs:
            await ctx.send("❌ No emoji-role pairs provided! Example: `🔴:@Red 🔵:@Blue`")
            return
        
        try:
            # Parse emoji-role pairs (more flexible parsing)
            pairs = role_pairs.split()
            reaction_data = []

            for pair in pairs:
                # Handle different formats: emoji:@role, emoji: @role, emoji :@role, emoji : @role
                if ':' not in pair:
                    await ctx.send("❌ Invalid format! Use: `emoji1: @role1 emoji2: @role2`\nExample: `🔴: @Red 🔵: @Blue`")
                    return
                
                # Split and clean up whitespace
                parts = pair.split(':', 1)
                emoji_part = parts[0].strip()
                role_part = parts[1].strip()
                
                # Extract role ID from mention (handles @role format)
                role_id_match = re.search(r'<@&(\d+)>', role_part)
                if not role_id_match:
                    await ctx.send(f"❌ Invalid role format: {role_part}\nUse @role mentions like @Red")
                    return
                
                role_id = int(role_id_match.group(1))
                role = ctx.guild.get_role(role_id)  # Changed from interaction.guild
                
                if not role:
                    await ctx.send(f"❌ Role not found: {role_part}")
                    return
                
                # Check if bot can manage the role
                if role >= ctx.guild.me.top_role:  # Changed from interaction.guild
                    await ctx.send(f"❌ I cannot manage {role.mention} - it's higher than my highest role!")
                    return
                
                reaction_data.append({'emoji': emoji_part, 'role': role})
            
            if not reaction_data:
                await ctx.send("❌ No valid emoji-role pairs provided!")
                return
            
            if len(reaction_data) > 20:
                await ctx.send("❌ Too many reaction roles! Maximum is 20.")
                return
            
            # Create embed for the reaction role message
            embed = discord.Embed(
                title=message,
                description="",
                color=discord.Color.blue()
            )
            
            # Add role information to embed
            role_info = ""
            for item in reaction_data:
                role_info += f"{item['emoji']} - <@&{item['role'].id}>\n"
            
            embed.add_field(name="Available Roles", value=role_info, inline=False)
            embed.set_footer(text="React with an emoji to get the role, unreact to remove it!")
            
            # Send the message
            sent_message = await channel.send(embed=embed)
            
            # Add reactions
            for item in reaction_data:
                try:
                    await sent_message.add_reaction(item['emoji'])
                except discord.HTTPException:
                    await ctx.send(f"❌ Failed to add reaction {item['emoji']} - invalid emoji?")
                    return
            
            # Store reaction role data
            guild_id_str = str(ctx.guild.id)
            message_id_str = str(sent_message.id)
            
            if not hasattr(self.bot, 'reaction_roles'):
                self.bot.reaction_roles = {}
            
            if guild_id_str not in self.bot.reaction_roles:
                self.bot.reaction_roles[guild_id_str] = {}
            
            self.bot.reaction_roles[guild_id_str][message_id_str] = {
                'channel_id': str(channel.id),
                'roles': {item['emoji']: str(item['role'].id) for item in reaction_data}
            }
            
            await self.bot.save_immediately()
            
            # Success message
            embed = discord.Embed(
                title="✅ Reaction Roles Set Up",
                description=f"Successfully created reaction roles in {channel.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Roles Added", value=f"{len(reaction_data)} roles", inline=True)
            embed.add_field(name="Message ID", value=str(sent_message.id), inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")

    @app_commands.command(name="sync_reaction_roles", description="Sync existing reactions with reaction roles (assign missing roles)")
    @app_commands.describe(
        message_id="The message ID to sync reactions for (optional - syncs all if not provided)"
    )
    async def sync_reaction_roles(self, interaction: discord.Interaction, message_id: str = None):
        """Sync existing reactions with reaction roles to assign missing roles"""
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You need the 'Manage Roles' permission to use this command.", ephemeral=True)
            return

        await interaction.response.defer()

        if not hasattr(self.bot, 'reaction_roles') or not self.bot.reaction_roles:
            await interaction.followup.send("❌ No reaction roles are currently set up.")
            return

        synced_count = 0
        error_count = 0
        messages_processed = 0

        try:
            # Filter reaction roles to sync
            guild_id_str = str(interaction.guild.id)
            roles_to_sync = {}
            
            if message_id:
                # Sync specific message
                if guild_id_str in self.bot.reaction_roles and message_id in self.bot.reaction_roles[guild_id_str]:
                    roles_to_sync[message_id] = self.bot.reaction_roles[guild_id_str][message_id]
                else:
                    await interaction.followup.send(f"❌ No reaction roles found for message ID: {message_id}")
                    return
            else:
                # Sync all reaction role messages for this guild
                if guild_id_str in self.bot.reaction_roles:
                    roles_to_sync = self.bot.reaction_roles[guild_id_str].copy()
                else:
                    await interaction.followup.send("❌ No reaction roles found for this server.")
                    return

            for msg_id, reaction_data in roles_to_sync.items():
                try:
                    # Get the channel and message
                    channel = self.bot.get_channel(int(reaction_data['channel_id']))
                    if not channel:
                        continue

                    message = await channel.fetch_message(int(msg_id))
                    if not message:
                        continue

                    messages_processed += 1

                    # Process each reaction on the message
                    for reaction in message.reactions:
                        emoji_str = str(reaction.emoji)
                        if emoji_str in reaction_data['roles']:
                            role_id = int(reaction_data['roles'][emoji_str])
                            role = interaction.guild.get_role(role_id)
                            
                            if not role:
                                continue

                            # Get all users who reacted with this emoji
                            async for user in reaction.users():
                                if user.bot:  # Skip bots
                                    continue

                                member = interaction.guild.get_member(user.id)
                                if not member:
                                    continue

                                # Check if user already has the role
                                if role not in member.roles:
                                    try:
                                        await member.add_roles(role, reason="Reaction role sync")
                                        synced_count += 1
                                        print(f"✅ Assigned {role.name} to {member.display_name}")
                                    except discord.Forbidden:
                                        error_count += 1
                                        print(f"❌ Forbidden: Could not assign {role.name} to {member.display_name}")
                                    except Exception as e:
                                        error_count += 1
                                        print(f"❌ Error assigning {role.name} to {member.display_name}: {e}")

                except discord.NotFound:
                    print(f"❌ Message or channel not found for ID: {msg_id}")
                    continue
                except discord.Forbidden:
                    error_count += 1
                    print(f"❌ Forbidden: Could not access message {msg_id}")
                    continue
                except Exception as e:
                    error_count += 1
                    print(f"❌ Error processing message {msg_id}: {e}")
                    continue

            # Send summary
            embed = discord.Embed(
                title="✅ Reaction Role Sync Complete",
                color=discord.Color.green()
            )
            embed.add_field(name="Messages Processed", value=str(messages_processed), inline=True)
            embed.add_field(name="Roles Assigned", value=str(synced_count), inline=True)
            embed.add_field(name="Errors", value=str(error_count), inline=True)
            
            if error_count > 0:
                embed.add_field(
                    name="⚠️ Issues Found", 
                    value=f"Check console output for detailed error logs. Common causes:\n• Users left the server\n• Roles were deleted\n• Network/API errors", 
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred during sync: {str(e)}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle reaction role assignment when user adds reaction"""
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return

        # Check if this message has reaction roles set up
        if not hasattr(self.bot, 'reaction_roles'):
            return

        guild_id_str = str(payload.guild_id)
        message_id_str = str(payload.message_id)

        if guild_id_str not in self.bot.reaction_roles:
            return

        if message_id_str not in self.bot.reaction_roles[guild_id_str]:
            return

        reaction_role_data = self.bot.reaction_roles[guild_id_str][message_id_str]
        emoji_str = str(payload.emoji)

        # Check if this emoji is mapped to a role
        if emoji_str not in reaction_role_data['roles']:
            return

        try:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            member = guild.get_member(payload.user_id)
            if not member:
                return

            role_id = int(reaction_role_data['roles'][emoji_str])
            role = guild.get_role(role_id)
            
            if not role:
                print(f"Reaction role not found: {role_id} in guild {guild.name}")
                return

            # Check if member already has the role
            if role in member.roles:
                return

            # Check if bot can assign the role
            if role >= guild.me.top_role:
                print(f"Cannot assign role {role.name} - higher than bot's highest role")
                return

            await member.add_roles(role, reason="Reaction role assignment")
            print(f"Assigned role {role.name} to {member.display_name} via reaction")

        except Exception as e:
            print(f"Error assigning reaction role: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle reaction role removal when user removes reaction"""
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return

        # Check if this message has reaction roles set up
        if not hasattr(self.bot, 'reaction_roles'):
            return

        guild_id_str = str(payload.guild_id)
        message_id_str = str(payload.message_id)

        if guild_id_str not in self.bot.reaction_roles:
            return

        if message_id_str not in self.bot.reaction_roles[guild_id_str]:
            return

        reaction_role_data = self.bot.reaction_roles[guild_id_str][message_id_str]
        emoji_str = str(payload.emoji)

        # Check if this emoji is mapped to a role
        if emoji_str not in reaction_role_data['roles']:
            return

        try:
            guild = self.bot.get_guild(payload.guild_id)
            if not guild:
                return

            member = guild.get_member(payload.user_id)
            if not member:
                return

            role_id = int(reaction_role_data['roles'][emoji_str])
            role = guild.get_role(role_id)
            
            if not role:
                print(f"Reaction role not found: {role_id} in guild {guild.name}")
                return

            # Check if member has the role
            if role not in member.roles:
                return

            # Check if bot can remove the role
            if role >= guild.me.top_role:
                print(f"Cannot remove role {role.name} - higher than bot's highest role")
                return

            await member.remove_roles(role, reason="Reaction role removal")
            print(f"Removed role {role.name} from {member.display_name} via reaction removal")

        except Exception as e:
            print(f"Error removing reaction role: {e}")

    @commands.command(name="purge", aliases=["clear", "delete", "clean"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge_prefix(self, ctx: commands.Context, member_or_amount, amount: int = None):
        """Purge messages - Usage: !purge 50 OR !purge @user 50"""
        
        # Parse arguments
        if amount is None:
            # Only amount provided: !purge 50
            try:
                amount = int(member_or_amount)
                member = None
            except ValueError:
                await ctx.send("❌ Usage: `!purge <amount>` or `!purge @user <amount>`")
                return
        else:
            # Member and amount provided: !purge @user 50
            if isinstance(member_or_amount, str):
                # Try to convert string to member
                try:
                    member_id = int(member_or_amount.strip('<@!>'))
                    member = ctx.guild.get_member(member_id)
                except:
                    await ctx.send("❌ Invalid user format. Usage: `!purge @user <amount>`")
                    return
            else:
                member = member_or_amount
        
        if amount < 1 or amount > 100:
            await ctx.send("❌ Amount must be between 1 and 100.")
            return
        
        try:
            if member:
                # Purge messages from specific user
                def check(message):
                    return message.author == member
                
                deleted = await ctx.channel.purge(limit=amount * 2, check=check)  # Check more messages to find user's messages
                deleted = [msg for msg in deleted if msg.author == member][:amount]  # Limit to requested amount
                
                embed = discord.Embed(
                    title="🗑️ Messages Purged",
                    description=f"Deleted **{len(deleted)}** messages from {member.mention}",
                    color=discord.Color.green()
                )
            else:
                # Purge any messages (including the command message)
                deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include command message
                
                embed = discord.Embed(
                    title="🗑️ Messages Purged",
                    description=f"Deleted **{len(deleted)}** messages",
                    color=discord.Color.green()
                )
            
            embed.set_footer(text=f"Purged by {ctx.author.display_name}")
            
            # Send confirmation and delete it after 5 seconds
            confirmation = await ctx.send(embed=embed)
            await asyncio.sleep(5)
            try:
                await confirmation.delete()
            except:
                pass
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages in this channel.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")


    @commands.command(name="warn", aliases=["warning", "w"])
    @commands.has_permissions(manage_messages=True)
    async def warn_prefix(self, ctx: commands.Context, member: discord.Member = None, *, reason: str = "No reason provided"):
        if member is None:
            from utils.helpers import show_command_usage
            command_data = {
                'description': '⚠️ Issue a warning to a server member',
                'usage_examples': [
                    {'usage': '!warn @user', 'description': 'Warn user with default reason'},
                    {'usage': '!warn @user spamming messages', 'description': 'Warn user with custom reason'},
                    {'usage': '!warning @user being disruptive', 'description': 'Using alias with reason'},
                    {'usage': '!w @user', 'description': 'Quick warn (short alias)'}
                ],
                'notes': '🔒 Requires Manage Messages permission\n📝 Warnings are permanently logged\n👀 Use `!warnings @user` to view user\'s warning history'
            }
            await show_command_usage(ctx, "warn", command_data)
            return
            
        if member.bot:
            await ctx.send("You cannot warn bots.")
            return
        if member == ctx.author:
            await ctx.send("You cannot warn yourself.")
            return

        guild_id_str = str(ctx.guild.id)
        user_id_str = str(member.id)

        if guild_id_str not in self.bot.warnings:
            self.bot.warnings[guild_id_str] = {}
        if user_id_str not in self.bot.warnings[guild_id_str]:
            self.bot.warnings[guild_id_str][user_id_str] = []

        warning_entry = {
            "reason": reason,
            "moderator_id": str(ctx.author.id),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.bot.warnings[guild_id_str][user_id_str].append(warning_entry)
        
        embed = self.create_compact_embed(member, "warned", reason)
        
        await ctx.send(embed=embed)
        await self.bot.save_immediately()

    @commands.command(name="mute", aliases=["timeout", "silence"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute_prefix(self, ctx: commands.Context, member: discord.Member = None, duration: str = "5m", *, reason: str = "No reason provided"):
        if member is None:
            from utils.helpers import show_command_usage
            command_data = {
                'description': '🔇 Temporarily mute a server member',
                'usage_examples': [
                    {'usage': '!mute @user', 'description': 'Mute for 5 minutes (default)'},
                    {'usage': '!mute @user 1h', 'description': 'Mute for 1 hour'},
                    {'usage': '!mute @user 30m spamming', 'description': 'Mute for 30 minutes with reason'},
                    {'usage': '!timeout @user 2h being disruptive', 'description': 'Using alias with custom duration'}
                ],
                'subcommands': {
                    'Duration formats': 's (seconds), m (minutes), h (hours), d (days)',
                    'Examples': '30s, 5m, 2h, 1d'
                },
                'notes': '🔒 Requires Moderate Members permission\n⏰ Default duration is 5 minutes if not specified\n🚫 Cannot mute bots, yourself, or higher roles'
            }
            await show_command_usage(ctx, "mute", command_data)
            return
            
        if member.bot:
            await ctx.send("You cannot mute bots.")
            return
        if member == ctx.author:
            await ctx.send("You cannot mute yourself.")
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("You can't mute someone with an equal or higher role.")
            return
        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send("I can't mute someone with an equal or higher role than me.")
            return

        # Parse duration
        duration_seconds = self.parse_duration(duration)
        duration_td = timedelta(seconds=duration_seconds)
        
        # Format duration for display
        if duration_seconds < 60:
            duration_display = f"{duration_seconds} seconds"
        elif duration_seconds < 3600:
            duration_display = f"{duration_seconds // 60} minutes"
        elif duration_seconds < 86400:
            duration_display = f"{duration_seconds // 3600} hours"
        else:
            duration_display = f"{duration_seconds // 86400} days"

        try:
            await member.timeout(duration_td, reason=f"Muted by {ctx.author.name}: {reason}")
            
            embed = self.create_compact_embed(member, "muted", reason, duration_display)
            
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("I don't have permission to mute this member.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command(name="unmute", aliases=["untimeout", "unsilence"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute_prefix(self, ctx: commands.Context, member: discord.Member = None, *, reason: str = "No reason provided"):
        if member is None:
            await ctx.send("Please specify a member to unmute. Usage: `!unmute @user [reason]`")
            return
            
        if member.bot:
            await ctx.send("Bots cannot be muted or unmuted.")
            return
        if member == ctx.author:
            await ctx.send("You cannot unmute yourself.")
            return
        if not member.is_timed_out():
            await ctx.send(f"{member.mention} is not currently muted.")
            return

        try:
            await member.timeout(None, reason=f"Unmuted by {ctx.author.name}: {reason}")
            
            embed = self.create_compact_embed(member, "unmuted", reason)
            
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("I don't have permission to unmute this member.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command(name="kick", aliases=["kickmember", "boot"])
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick_prefix(self, ctx: commands.Context, member: discord.Member = None, *, reason: str = "No reason provided"):
        if member is None:
            await ctx.send("Please specify a member to kick. Usage: `!kick @user [reason]`")
            return
            
        if member == ctx.author:
            await ctx.send("You can't kick yourself.")
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("You can't kick someone with an equal or higher role.")
            return
        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send("I can't kick someone with an equal or higher role than me.")
            return

        await member.kick(reason=f"Kicked by {ctx.author.name}: {reason}")
        
        embed = self.create_compact_embed(member, "kicked", reason)
        
        await ctx.send(embed=embed)

    @commands.command(name="ban", aliases=["banmember", "banish"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban_prefix(self, ctx: commands.Context, member: discord.Member = None, *, reason: str = "No reason provided"):
        if member is None:
            await ctx.send("Please specify a member to ban. Usage: `!ban @user [reason]`")
            return
            
        if member == ctx.author:
            await ctx.send("You can't ban yourself.")
            return
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("You can't ban someone with an equal or higher role.")
            return
        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send("I can't ban someone with an equal or higher role than me.")
            return

        await member.ban(reason=f"Banned by {ctx.author.name}: {reason}")
        
        embed = self.create_compact_embed(member, "banned", reason)
        
        await ctx.send(embed=embed)

    @commands.command(name="warnings", aliases=["warns", "checkwarns", "checkwarnings", "getwarns"])
    async def warnings_prefix(self, ctx: commands.Context, member: discord.Member = None):
        if member is None:
            member = ctx.author

        guild_id_str = str(ctx.guild.id)
        user_id_str = str(member.id)

        user_warnings = self.bot.warnings.get(guild_id_str, {}).get(user_id_str, [])

        if not user_warnings:
            embed = discord.Embed(color=0x2b2d31)
            embed.description = f"This user has a clean record."
            embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(color=0x2b2d31)
        embed.set_author(name=f"{member.display_name} has {len(user_warnings)} warning(s)", icon_url=member.display_avatar.url)
        
        warnings_text = ""
        for i, warn_entry in enumerate(user_warnings[-3:], 1):  # Show last 3 warnings
            mod_user = ctx.guild.get_member(int(warn_entry["moderator_id"]))
            mod_display = mod_user.display_name if mod_user else f"ID: {warn_entry['moderator_id']}"
            try:
                warn_time = datetime.fromisoformat(warn_entry['timestamp'])
                time_str = format_discord_timestamp(warn_time.timestamp(), "R")
            except:
                time_str = "Unknown time"
            warnings_text += f"**#{len(user_warnings) - len(user_warnings[-3:]) + i}** {warn_entry['reason']} • {time_str}\n"
        
        if warnings_text:
            embed.add_field(name="Recent Warnings", value=warnings_text.strip(), inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))