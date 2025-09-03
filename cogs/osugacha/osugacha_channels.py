import discord
import json
from discord.ext import commands
from discord import app_commands
from utils.helpers import *
from utils.config import *
from .osugacha_config import FILE_PATHS

class OsuGachaChannelsCog(commands.Cog, name="Osu Gacha Channels"):
    """Channel restriction management for osu gacha commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Load allowed channels
        self.allowed_channels = load_json(FILE_PATHS.get("allowed_channels", "data/allowed_channels.json"))
        if not isinstance(self.allowed_channels, dict):
            self.allowed_channels = {}

    def save_allowed_channels(self):
        """Save allowed channels to file"""
        save_json(FILE_PATHS.get("allowed_channels", "data/allowed_channels.json"), self.allowed_channels)

    def is_channel_allowed(self, guild_id, channel_id):
        """Check if channel is allowed for osu gacha commands"""
        guild_id_str = str(guild_id)
        channel_id_str = str(channel_id)
        
        # If no restrictions set for this guild, allow all channels
        if guild_id_str not in self.allowed_channels:
            return True
        
        # If empty list, no channels are allowed
        allowed = self.allowed_channels[guild_id_str]
        if not allowed:
            return False
        
        return channel_id_str in allowed

    async def check_channel_permission(self, ctx):
        """Check if command can be used in this channel"""
        if not ctx.guild:  # DMs always allowed
            return True
        
        return self.is_channel_allowed(ctx.guild.id, ctx.channel.id)

    # SLASH COMMANDS
    @app_commands.command(name="osuchannels", description="Manage allowed channels for osu gacha commands")
    @app_commands.describe(
        action="Action to perform",
        channel="Channel to add/remove (optional for list/clear)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="List allowed channels", value="list"),
        app_commands.Choice(name="Add channel", value="add"),
        app_commands.Choice(name="Remove channel", value="remove"),
        app_commands.Choice(name="Clear all restrictions", value="clear"),
    ])
    @app_commands.default_permissions(manage_channels=True)
    async def osu_channels_slash(self, interaction: discord.Interaction, action: str, channel: discord.TextChannel = None):
        await self._channels_command(interaction, action, channel)

    # PREFIX COMMANDS
    @commands.command(name="osuchannels", aliases=["ogchannels"])
    @commands.has_permissions(manage_channels=True)
    async def osu_channels_prefix(self, ctx: commands.Context, action: str = None, channel: discord.TextChannel = None):
        if not action:
            embed = discord.Embed(
                title="Osu Gacha Channel Management",
                description="Manage which channels can use osu gacha commands.\n\n"
                          "**Actions:**\n"
                          "`list` - Show allowed channels\n"
                          "`add #channel` - Add channel to allowed list\n"
                          "`remove #channel` - Remove channel from allowed list\n"
                          "`clear` - Remove all restrictions (allow all channels)\n\n"
                          "**Examples:**\n"
                          "`!ogchannels list`\n"
                          "`!ogchannels add #gacha-games`\n"
                          "`!ogchannels remove #general`\n"
                          "`!ogchannels clear`",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Requires 'Manage Channels' permission")
            await ctx.send(embed=embed)
            return
        
        await self._channels_command(ctx, action, channel)

    # SHARED IMPLEMENTATION
    async def _channels_command(self, ctx, action, channel):
        """Handle channel management command"""
        if not ctx.guild:
            await self._send_error(ctx, "This command can only be used in servers!")
            return
        
        guild_id_str = str(ctx.guild.id)
        
        if action == "list":
            if guild_id_str not in self.allowed_channels or not self.allowed_channels[guild_id_str]:
                embed = discord.Embed(
                    title="Allowed Channels",
                    description="No channel restrictions set. All channels are allowed.",
                    color=discord.Color.green()
                )
            else:
                channels = []
                for channel_id_str in self.allowed_channels[guild_id_str]:
                    ch = ctx.guild.get_channel(int(channel_id_str))
                    if ch:
                        channels.append(f"• {ch.mention}")
                    else:
                        channels.append(f"• Unknown Channel (ID: {channel_id_str})")
                
                embed = discord.Embed(
                    title="Allowed Channels",
                    description="\n".join(channels) if channels else "No valid channels found.",
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Total: {len(channels)} channels")
            
            await self._send_response(ctx, embed)
            
        elif action == "add":
            if not channel:
                await self._send_error(ctx, "Please specify a channel to add!")
                return
            
            if guild_id_str not in self.allowed_channels:
                self.allowed_channels[guild_id_str] = []
            
            channel_id_str = str(channel.id)
            if channel_id_str in self.allowed_channels[guild_id_str]:
                await self._send_error(ctx, f"{channel.mention} is already in the allowed list!")
                return
            
            self.allowed_channels[guild_id_str].append(channel_id_str)
            self.save_allowed_channels()
            
            embed = discord.Embed(
                title="Channel Added",
                description=f"Added {channel.mention} to allowed channels list.\n\n"
                          f"Osu gacha commands can now only be used in {len(self.allowed_channels[guild_id_str])} allowed channels.",
                color=discord.Color.green()
            )
            await self._send_response(ctx, embed)
            
        elif action == "remove":
            if not channel:
                await self._send_error(ctx, "Please specify a channel to remove!")
                return
            
            if guild_id_str not in self.allowed_channels or not self.allowed_channels[guild_id_str]:
                await self._send_error(ctx, "No channel restrictions are currently set!")
                return
            
            channel_id_str = str(channel.id)
            if channel_id_str not in self.allowed_channels[guild_id_str]:
                await self._send_error(ctx, f"{channel.mention} is not in the allowed list!")
                return
            
            self.allowed_channels[guild_id_str].remove(channel_id_str)
            
            # If no channels left, remove the guild entry
            if not self.allowed_channels[guild_id_str]:
                del self.allowed_channels[guild_id_str]
            
            self.save_allowed_channels()
            
            remaining = len(self.allowed_channels.get(guild_id_str, []))
            if remaining > 0:
                desc = f"Removed {channel.mention} from allowed channels list.\n\n" \
                       f"Osu gacha commands can now only be used in {remaining} allowed channels."
            else:
                desc = f"Removed {channel.mention} from allowed channels list.\n\n" \
                       f"All channel restrictions have been cleared. Commands can be used anywhere."
            
            embed = discord.Embed(
                title="Channel Removed",
                description=desc,
                color=discord.Color.orange()
            )
            await self._send_response(ctx, embed)
            
        elif action == "clear":
            if guild_id_str not in self.allowed_channels or not self.allowed_channels[guild_id_str]:
                await self._send_error(ctx, "No channel restrictions are currently set!")
                return
            
            del self.allowed_channels[guild_id_str]
            self.save_allowed_channels()
            
            embed = discord.Embed(
                title="Restrictions Cleared",
                description="All channel restrictions have been removed.\n\n"
                          "Osu gacha commands can now be used in any channel.",
                color=discord.Color.green()
            )
            await self._send_response(ctx, embed)
            
        else:
            await self._send_error(ctx, f"Invalid action: {action}\nValid actions: list, add, remove, clear")

    async def _send_error(self, ctx, message):
        """Send error message"""
        embed = discord.Embed(
            title="Error",
            description=message,
            color=discord.Color.red()
        )
        await self._send_response(ctx, embed)

    async def _send_response(self, ctx, embed):
        """Send response (handles both slash and prefix)"""
        if hasattr(ctx, 'response'):
            await ctx.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(OsuGachaChannelsCog(bot))