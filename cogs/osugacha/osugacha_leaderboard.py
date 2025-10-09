import discord
from discord.ext import commands
from discord import app_commands
import time
from utils.helpers import *
from utils.config import *

# Import all the configuration and system
from .osugacha_config import *
from .osugacha_system import OsuGachaSystem

class OsuGachaLeaderboardsCog(commands.Cog, name="Osu Gacha Leaderboards"):
    """Comprehensive leaderboard system for gacha collection stats"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Don't create new system - use the shared one
        if hasattr(bot, 'gacha_system'):
            self.gacha_system = bot.gacha_system
        else:
            # Fallback if system not loaded yet
            self.gacha_system = OsuGachaSystem()
            bot.gacha_system = self.gacha_system

    # SLASH COMMANDS
    @app_commands.command(name="osuleaderboard", description="View collection leaderboards")
    @app_commands.describe(
        board_type="Type of leaderboard to view"
    )
    @app_commands.choices(board_type=[
        app_commands.Choice(name="Richest Players", value="currency"),
        app_commands.Choice(name="Most Cards", value="total_cards"),
        app_commands.Choice(name="Highest Collection Value", value="total_value"),
        app_commands.Choice(name="Most 5★ Cards", value="five_star"),
        app_commands.Choice(name="Most Mutations", value="mutations"),
        app_commands.Choice(name="Most Crates Opened", value="opens"),
        app_commands.Choice(name="Best Win Rate", value="win_rate"),
        app_commands.Choice(name="Most Gambles", value="total_gambles"),
        app_commands.Choice(name="Best Profit", value="gambling_profit"),
        app_commands.Choice(name="Most Achievements", value="achievements"),
        app_commands.Choice(name="Daily Streak", value="daily_streak"),
        app_commands.Choice(name="Most Trades", value="total_trades")
    ])
    async def osu_leaderboard_slash(self, interaction: discord.Interaction, board_type: str = "currency"):
        await self._leaderboard_command(interaction, board_type)

    # PREFIX COMMANDS
    @commands.command(name="osuleaderboard", aliases=["oleaderboard", "olb", "otop", "oranks", "orank"])
    async def osu_leaderboard_prefix(self, ctx: commands.Context, board_type: str = "currency"):
        """Show collection leaderboards
        
        Available types:
        richest, cards, collection, value, five_star, mutations, opens, 
        win_rate, gambles, profit, achievements, daily_streak, trades
        
        Examples:
        !olb richest - Show richest players
        !olb cards - Show most cards
        !olb collection - Same as cards
        !olb mutations - Show most mutations
        """
        
        # Handle common aliases
        aliases = {
            "rich": "currency", "richest": "currency", "coins": "currency", "money": "currency",
            "cards": "total_cards", "collection": "total_cards", "total": "total_cards",
            "value": "total_value", "worth": "total_value", "wealth": "total_value",
            "five": "five_star", "5star": "five_star", "5": "five_star", "elite": "five_star",
            "mutations": "mutations", "mutation": "mutations", "mutants": "mutations", "special": "mutations",
            "opens": "opens", "crates": "opens", "opened": "opens",
            "winrate": "win_rate", "wins": "win_rate", "win": "win_rate", "gambling": "win_rate",
            "gambles": "total_gambles", "gamble": "total_gambles", "bets": "total_gambles", "games": "total_gambles",
            "profit": "gambling_profit", "earnings": "gambling_profit", "net": "gambling_profit",
            "achievements": "achievements", "achievement": "achievements", "achieve": "achievements", "unlocks": "achievements",
            "daily": "daily_streak", "streak": "daily_streak", "days": "daily_streak",
            "trades": "total_trades", "trade": "total_trades", "trading": "total_trades", "deals": "total_trades"
        }
        
        resolved_type = aliases.get(board_type.lower(), board_type.lower())
        await self._leaderboard_command(ctx, resolved_type)

    # SHARED COMMAND IMPLEMENTATION
    async def _leaderboard_command(self, ctx, board_type):
        """Show collection leaderboards"""
        try:
            if hasattr(ctx, 'response'):
                await ctx.response.defer()
            else:
                message = await ctx.send("Calculating leaderboard...")

            # Calculate stats for all users
            user_stats = []
            
            for user_id_str, user_data in self.bot.osu_gacha_data.items():
                try:
                    user_id = int(user_id_str)
                    user = self.bot.get_user(user_id)
                    
                    if not user:
                        continue
                    
                    cards = user_data.get("cards", {})
                    
                    # Calculate various stats
                    total_cards = len(cards)
                    total_value = sum(card.get("price", 0) for card in cards.values())
                    five_star_count = sum(1 for card in cards.values() if card.get("stars", 1) == 5)
                    mutation_count = sum(1 for card in cards.values() if card.get("mutation"))
                    currency = user_data.get("currency", 0)
                    total_opens = user_data.get("total_opens", 0)
                    
                    # Gambling stats
                    gambling_stats = user_data.get("gambling_stats", {})
                    total_gambles = gambling_stats.get("total_games", 0)
                    gambling_wins = gambling_stats.get("wins", 0)
                    gambling_profit = gambling_stats.get("net_profit", 0)
                    win_rate = (gambling_wins / total_gambles * 100) if total_gambles > 0 else 0

                    # Add PvP stats
                    pvp_stats = user_data.get("pvp_stats", {})
                    pvp_games = pvp_stats.get("total_games", 0)
                    pvp_wins = pvp_stats.get("wins", 0)
                    pvp_profit = pvp_stats.get("net_profit", 0)
                                        
                    # Other stats
                    achievement_count = len(user_data.get("achievements", {}))
                    daily_count = user_data.get("daily_count", 0)
                    
                    # Trading stats (if implemented)
                    trading_stats = user_data.get("trading_stats", {})
                    total_trades = trading_stats.get("completed_trades", 0)
                    
                    user_stats.append({
                        "user": user,
                        "user_id": user_id,
                        "total_cards": total_cards,
                        "total_value": total_value,
                        "five_star": five_star_count,
                        "mutations": mutation_count,
                        "currency": currency,
                        "opens": total_opens,
                        "total_gambles": total_gambles,
                        "win_rate": win_rate,
                        "gambling_profit": gambling_profit,
                        "pvp_games": pvp_games,
                        "pvp_wins": pvp_wins,
                        "pvp_profit": pvp_profit,
                        "achievements": achievement_count,
                        "daily_streak": daily_count,
                        "total_trades": total_trades
                    })
                except:
                    continue
            
            # Sort by requested stat
            sort_key_map = {
                "total_cards": "total_cards",
                "total_value": "total_value", 
                "five_star": "five_star",
                "mutations": "mutations",
                "currency": "currency",
                "opens": "opens",
                "total_gambles": "total_gambles",
                "win_rate": "win_rate",
                "gambling_profit": "gambling_profit",
                "pvp_games": "pvp_games",
                "pvp_wins": "pvp_wins", 
                "pvp_profit": "pvp_profit",
                "achievements": "achievements",
                "daily_streak": "daily_streak",
                "total_trades": "total_trades"
            }
            
            sort_key = sort_key_map.get(board_type, "currency")
            sorted_stats = sorted(user_stats, key=lambda x: x[sort_key], reverse=True)
            
            # Filter out users with 0 in the category (except currency and profit)
            if board_type not in ["currency", "gambling_profit"]:
                sorted_stats = [s for s in sorted_stats if s[sort_key] > 0]
            
            if not sorted_stats:
                embed = discord.Embed(
                    title="Leaderboard",
                    description="No data available for this leaderboard yet!",
                    color=discord.Color.blue()
                )
                
                if hasattr(ctx, 'edit_original_response'):
                    await ctx.edit_original_response(embed=embed)
                else:
                    await message.edit(embed=embed)
                return
            
            # Create leaderboard embed
            board_names = {
                "total_cards": "Most Cards",
                "total_value": "Highest Collection Value",
                "five_star": "Most 5★ Cards",
                "mutations": "Most Mutations",
                "currency": "Richest Players",
                "opens": "Most Crates Opened",
                "total_gambles": "Most Gambles",
                "win_rate": "Best Win Rate",
                "gambling_profit": "Best Gambling Profit",
                "pvp_games": "Most PvP Games",
                "pvp_wins": "Most PvP Wins",
                "pvp_profit": "Best PvP Profit",
                "achievements": "Most Achievements",
                "daily_streak": "Longest Daily Streak",
                "total_trades": "Most Trades"
            }
            
            embed = discord.Embed(
                title=f"{board_names[board_type]}",
                description=f"Top {min(10, len(sorted_stats))} players",
                color=discord.Color.gold()
            )
            
            # Current user's position
            current_user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
            current_user_pos = None
            current_user_value = None
            
            for i, stats in enumerate(sorted_stats, 1):
                if stats["user_id"] == current_user_id:
                    current_user_pos = i
                    current_user_value = stats[sort_key]
                    break
            
            # Show top 10
            leaderboard_text = []
            for i, stats in enumerate(sorted_stats[:10], 1):
                user = stats["user"]
                value = stats[sort_key]
                
                # Format value based on type
                if board_type in ["currency", "total_value", "gambling_profit"]:
                    if board_type == "gambling_profit" and value < 0:
                        value_text = f"-{abs(value):,} coins"
                    else:
                        value_text = f"{value:,} coins"
                elif board_type == "win_rate":
                    value_text = f"{value:.1f}%" if stats["total_gambles"] >= 10 else f"{value:.1f}% ({stats['total_gambles']} games)"
                else:
                    value_text = f"{value:,}"
                
                # Position indicator (minimal)
                if i <= 3:
                    position = f"**{i}.**"
                else:
                    position = f"{i}."
                
                leaderboard_text.append(f"{position} {user.display_name} - {value_text}")
            
            embed.add_field(
                name="Top Players",
                value="\n".join(leaderboard_text),
                inline=False
            )
            
            # Show current user's position if not in top 10
            if current_user_pos and current_user_pos > 10:
                if board_type in ["currency", "total_value", "gambling_profit"]:
                    if board_type == "gambling_profit" and current_user_value < 0:
                        value_text = f"-{abs(current_user_value):,} coins"
                    else:
                        value_text = f"{current_user_value:,} coins"
                elif board_type == "win_rate":
                    user_gambles = next(s["total_gambles"] for s in sorted_stats if s["user_id"] == current_user_id)
                    value_text = f"{current_user_value:.1f}%" if user_gambles >= 10 else f"{current_user_value:.1f}% ({user_gambles} games)"
                else:
                    value_text = f"{current_user_value:,}"
                
                embed.add_field(
                    name="Your Position",
                    value=f"#{current_user_pos} - {value_text}",
                    inline=True
                )
            elif current_user_pos and current_user_pos <= 10:
                embed.add_field(
                    name="Your Position",
                    value=f"#{current_user_pos} (in top 10)",
                    inline=True
                )
            
            # Add some stats
            total_users = len([s for s in user_stats if s[sort_key] > 0]) if board_type not in ["currency", "gambling_profit"] else len(user_stats)
            
            embed.add_field(
                name="Total Players",
                value=f"{total_users}",
                inline=True
            )
            
            # Add category-specific info
            if board_type == "win_rate":
                embed.set_footer(text="Win rate requires at least 10 games for accuracy")
            elif board_type == "gambling_profit":
                embed.set_footer(text="Profit can be negative • Gamble responsibly")
            elif board_type == "mutations":
                embed.set_footer(text="Mutations are rare special card variants")
            elif board_type == "five_star":
                embed.set_footer(text="5★ cards are the highest rarity (Top 50 players)")
            elif board_type == "daily_streak":
                embed.set_footer(text="Daily streak shows total daily claims")
            else:
                embed.set_footer(text="Data updates in real-time")
            
            # Send result
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=embed)
            else:
                await message.edit(embed=embed)
                
        except Exception as e:
            print(f"Error in leaderboard: {e}")
            embed = discord.Embed(
                title="Error",
                description="There was an error loading the leaderboard. Please try again later.",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=embed)
            elif hasattr(ctx, 'response'):
                await ctx.response.edit_message(embed=embed)
            else:
                await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(OsuGachaLeaderboardsCog(bot))