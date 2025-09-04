import discord
from discord.ext import commands
from discord import app_commands
from utils.helpers import *
from utils.config import *

# Import the handler cog
from .osugacha_handlers import OsuGachaHandlers

class OsuGachaCommandsCog(commands.Cog, name="Osu Gacha Commands"):
    """Main commands cog - delegates to handler methods"""
    
    def __init__(self, bot):
        self.bot = bot
        self.handlers = OsuGachaHandlers(bot)

    # SLASH COMMANDS
    @app_commands.command(name="osugive", description="[ADMIN] Give coins or cards to players")
    @app_commands.describe(
        target="Player to give items to",
        amount_or_player="Coin amount (number) or player name for card",
        mutation="Optional mutation for card (ignored for coins)"
    )
    async def osu_give_slash(self, interaction: discord.Interaction, target: discord.Member, amount_or_player: str, mutation: str = None):
        """Admin slash command for giving items"""
        await self.handlers.handle_give_command(interaction, target, amount_or_player, mutation, interaction)

    @app_commands.command(name="osuhelp", description="Complete guide to the osu! gacha system")
    async def osu_help_slash(self, interaction: discord.Interaction):
        await self.handlers.handle_help_command(interaction, interaction)

    @app_commands.command(name="osuachievements", description="View all available achievements and your progress")
    async def osu_achievements_slash(self, interaction: discord.Interaction):
        """View all achievements and progress"""
        await self.handlers.handle_achievements_command(interaction)

    @app_commands.command(name="osustats", description="View osu gacha collection statistics and achievements")
    @app_commands.describe(user="User to check stats for (defaults to yourself)")
    async def osu_stats_slash(self, interaction: discord.Interaction, user: discord.User = None):
        """View collection statistics and achievements"""
        await self.handlers.handle_stats_command(interaction, user)

    @app_commands.command(name="osuopen", description="Open gacha crates")
    @app_commands.describe(
        crate_type="Type of crate to open",
        amount="Number of crates to open (1-10)"
    )
    async def osu_open_slash(self, interaction: discord.Interaction, crate_type: str, amount: int = 1):
        await self.handlers.handle_open_command(interaction, crate_type, amount, interaction)

    @app_commands.command(name="osudaily", description="Claim your daily rewards")
    async def osu_daily_slash(self, interaction: discord.Interaction):
        await self.handlers.handle_daily_command(interaction, interaction)

    @app_commands.command(name="osubalance", description="View your coins and collection stats")
    async def osu_balance_slash(self, interaction: discord.Interaction):
        await self.handlers.handle_balance_command(interaction, interaction)

    @app_commands.command(name="osusimulate", description="[ADMIN] Simulate opening crates")
    @app_commands.describe(
        crate_type="Type of crate to simulate",
        amount="Number of crates to simulate (1-100)"
    )
    @app_commands.default_permissions(administrator=True)
    async def osu_simulate_slash(self, interaction: discord.Interaction, crate_type: str, amount: int = 10):
        await self.handlers.handle_simulate_command(interaction, crate_type, amount, interaction)

    @app_commands.command(name="osucrates", description="View available crates and their contents")
    async def osu_crates_slash(self, interaction: discord.Interaction):
        await self.handlers.handle_crates_command(interaction, interaction)

    @app_commands.command(name="osupreview", description="Preview any player's card from top 10k with optional mutation")
    @app_commands.describe(
        search="Player name or rank to preview (e.g. 'mrekk' or '1')",
        mutation="Optional mutation to preview (e.g. 'rainbow', 'golden', 'shiny')"
    )
    @app_commands.choices(mutation=[
        app_commands.Choice(name="Shiny (2.0x value)", value="shiny"),
        app_commands.Choice(name="Holographic (2.5x value)", value="holographic"),
        app_commands.Choice(name="Crystalline (3.0x value)", value="crystalline"),
        app_commands.Choice(name="Shadow (1.8x value)", value="shadow"),
        app_commands.Choice(name="Golden (5.0x value)", value="golden"),
        app_commands.Choice(name="Rainbow (10x value)", value="rainbow"),
        app_commands.Choice(name="Cosmic (3.5x value)", value="cosmic"),
        app_commands.Choice(name="Shocked (2.2x value)", value="shocked"),
        app_commands.Choice(name="Spectral (2.8x value)", value="spectral"),
        app_commands.Choice(name="Immortal (50x value)", value="immortal"),
        app_commands.Choice(name="Flashback (???)", value="flashback")
    ])
    async def osu_preview_slash(self, interaction: discord.Interaction, search: str, mutation: str = None):
        await self.handlers._preview_command(interaction, search, mutation)

    @app_commands.command(name="osutoggle", description="Toggle confirmation prompts for gacha actions")
    async def osu_toggle_slash(self, interaction: discord.Interaction):
        await self.handlers.handle_toggle_confirmations(interaction)

    @app_commands.command(name="owipe", description="[OWNER] Wipe a user's gacha data completely")
    @app_commands.describe(target="User whose gacha data to wipe completely (Owner only)")
    @app_commands.default_permissions(administrator=True)
    async def owipe_slash(self, interaction: discord.Interaction, target: discord.Member = None):
        """Wipe a user's gacha data completely (Owner only)"""
        await self.handlers.handle_wipe_command(interaction, target)

    # PREFIX COMMANDS
    @commands.command(name="osutoggle", aliases=["otoggle", "toggle"])
    async def osu_toggle_prefix(self, ctx: commands.Context):
        await self.handlers.handle_toggle_confirmations(ctx)

    @commands.command(name="osugive", aliases=["ogive",])
    async def osu_give_prefix(self, ctx: commands.Context, target: discord.Member = None, amount_or_player: str = None, *, mutation: str = None):
        """Admin-only command to give coins or cards to players"""
        if not target or not amount_or_player:
            embed = discord.Embed(
                title="Usage",
                description="**Give Coins:** `!ogive @user 1000`\n"
                        "**Give Card:** `!ogive @user mrekk` (random mutation)\n"
                        "**Give Card with Mutation:** `!ogive @user mrekk immortal`",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        await self.handlers.handle_give_command(ctx, target, amount_or_player, mutation)

    @commands.command(name="owipe", aliases=["owiped", "owipeuser"])
    async def owipe_prefix(self, ctx: commands.Context, target: discord.Member = None):
        """Wipe a user's gacha data completely (Owner only)"""
        await self.handlers.handle_wipe_command(ctx, target)

    @commands.command(name="osuhelp", aliases=["ohelp", "oguide"])
    async def osu_help_prefix(self, ctx):
        await self.handlers.handle_help_command(ctx)

    @commands.command(name="osuachievements", aliases=["oachievements", "achievements", "achieve", "progress"])
    async def osu_achievements_prefix(self, ctx: commands.Context):
        """View all achievements and progress"""
        await self.handlers.handle_achievements_command(ctx)

    @commands.command(name="osustats", aliases=["ostats", "ocollection", "osucollection", "myosu", "osucol",])
    async def osu_stats_prefix(self, ctx: commands.Context, user: discord.User = None):
        """View osu gacha collection statistics and achievements"""
        await self.handlers.handle_stats_command(ctx, user)

    @commands.command(name="osuopen", aliases=["oopen", "open"])
    async def osu_open_prefix(self, ctx: commands.Context, crate_type: str = None, amount: int = 1):
        if not crate_type:
            await self.handlers.show_crate_help(ctx)
            return
        await self.handlers.handle_open_command(ctx, crate_type, amount)

    @commands.command(name="osudaily", aliases=["odaily", "daily"])
    async def osu_daily_prefix(self, ctx: commands.Context):
        await self.handlers.handle_daily_command(ctx)

    @commands.command(name="osubalance", aliases=["obalance", "balance", "obal", "bal"])
    async def osu_balance_prefix(self, ctx: commands.Context):
        await self.handlers.handle_balance_command(ctx)

    @commands.command(name="osusimulate", aliases=["osimulate", "simulate", "osim", "sim"])
    @commands.has_permissions(administrator=True)
    async def osu_simulate_prefix(self, ctx: commands.Context, crate_type: str = None, amount: int = 10):
        if not crate_type:
            await self.handlers.show_crate_help(ctx)
            return
        await self.handlers.handle_simulate_command(ctx, crate_type, amount)

    @commands.command(name="osucrates", aliases=["ocrates", "crates"])
    async def osu_crates_prefix(self, ctx: commands.Context):
        await self.handlers.handle_crates_command(ctx)

    @commands.command(name="osupreview", aliases=["opreview", "preview"])
    async def osu_preview_prefix(self, ctx: commands.Context, *, search: str = None):
        if not search:
            await ctx.send("❌ Please specify a player name or rank to preview\n**Examples:**\n• `!osupreview mrekk`\n• `!osupreview 1 rainbow`\n• `!osupreview cookiezi golden`")
            return
        await self.handlers._preview_command(ctx, search)

async def setup(bot):
    await bot.add_cog(OsuGachaCommandsCog(bot))