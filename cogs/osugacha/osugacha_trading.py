import discord
from discord.ext import commands
from discord import app_commands
import time
import asyncio
from utils.helpers import *
from utils.config import *

# Import all the configuration and system
from .osugacha_config import *
from .osugacha_system import OsuGachaSystem

class OsuGachaTradingCog(commands.Cog, name="Osu Gacha Trading"):
    """Advanced trading system for cards and coins"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Don't create new system - use the shared one
        if hasattr(bot, 'gacha_system'):
            self.gacha_system = bot.gacha_system
        else:
            # Fallback if system not loaded yet
            self.gacha_system = OsuGachaSystem()
            bot.gacha_system = self.gacha_system

    async def cog_load(self):
        """Called when the cog is loaded"""
        if not hasattr(self.bot, 'active_trades'):
            self.bot.active_trades = {}
        
        # Start cleanup task
        self.cleanup_task = self.bot.loop.create_task(self.periodic_cleanup())

    def cog_unload(self):
        """Called when the cog is unloaded"""
        if self.cleanup_task:
            self.cleanup_task.cancel()

    async def periodic_cleanup(self):
        """Periodically clean up expired trades every 30 minutes"""
        while True:
            try:
                await asyncio.sleep(1800)  # 30 minutes
                await self._cleanup_expired_trades()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in periodic trade cleanup: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _cleanup_expired_trades(self):
        """Remove trades that have been active for more than 10 minutes"""
        current_time = time.time()
        expired_trades = []
        
        for trade_id, trade_data in self.bot.active_trades.items():
            # Check if trade is older than 10 minutes (600 seconds)
            if current_time - trade_data["created_at"] > 600:
                expired_trades.append(trade_id)
        
        # Remove expired trades
        for trade_id in expired_trades:
            del self.bot.active_trades[trade_id]
            print(f"Cleaned up expired trade: {trade_id}")
        
        if expired_trades:
            print(f"Cleaned up {len(expired_trades)} expired trades")

    def get_user_gacha_data(self, user_id):
        """Get user's gacha data"""
        user_id_str = str(user_id)
        if user_id_str not in self.bot.osu_gacha_data:
            self.bot.osu_gacha_data[user_id_str] = {
                "currency": GAME_CONFIG["default_starting_coins"],
                "cards": {},
                "crates": {},
                "daily_last_claimed": 0,
                "total_opens": 0,
                "achievements": {},
                "achievement_stats": {},
                "favorites": [],
                "confirmations_enabled": GAME_CONFIG["default_confirmations_enabled"],  # NEW
                "party_stats": {
                    "bg_guesses_correct": 0,
                    "bg_games_won": 0,
                    "bg_games_played": 0
                }
            }
            save_json(FILE_PATHS["gacha_data"], self.bot.osu_gacha_data)

        # Add confirmation setting to existing users who don't have it
        if "confirmations_enabled" not in self.bot.osu_gacha_data[user_id_str]:
            self.bot.osu_gacha_data[user_id_str]["confirmations_enabled"] = GAME_CONFIG["default_confirmations_enabled"]

        return self.bot.osu_gacha_data[user_id_str]

    def save_user_data(self):
        """Save user data to file"""
        save_json(FILE_PATHS["gacha_data"], self.bot.osu_gacha_data)

    # SLASH COMMANDS
    @app_commands.command(name="osutrade", description="Trade cards and coins with another player")
    @app_commands.describe(
        player="Player to trade with",
        action="Trade action to perform"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Start New Trade", value="start"),
        app_commands.Choice(name="View Active Trade", value="view"),
        app_commands.Choice(name="Cancel Trade", value="cancel")
    ])
    async def osu_trade_slash(self, interaction: discord.Interaction, player: discord.Member, action: str = "start"):
        await self._trade_command(interaction, player, action)

    # PREFIX COMMANDS
    @commands.command(name="osutrade", aliases=["otrade", "trade"])
    async def osu_trade_prefix(self, ctx: commands.Context, player: discord.Member = None, action: str = "start"):
        if not player:
            await ctx.send("Please specify a player to trade with\nExample: `!osutrade @user`")
            return
        await self._trade_command(ctx, player, action)

    # SHARED COMMAND IMPLEMENTATION
    async def _trade_command(self, ctx, player, action):
        """Handle trading system with enhanced card selection"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        
        if player.bot:
            embed = discord.Embed(
                title="Invalid Trade Target",
                description="You can't trade with bots!",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return

        if player.id == user_id:
            embed = discord.Embed(
                title="Invalid Trade Target",
                description="You can't trade with yourself!",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return

        # Clean up any expired trades first
        await self._cleanup_expired_trades()

        # Create unique trade ID
        trade_id = f"{user_id}_{player.id}_{int(time.time())}"
        
        if action == "start":
            # Cancel any existing trades involving either user
            trades_to_cancel = []
            for existing_trade_id, trade_data in self.bot.active_trades.items():
                if user_id in [trade_data["initiator"], trade_data["partner"]] or player.id in [trade_data["initiator"], trade_data["partner"]]:
                    trades_to_cancel.append(existing_trade_id)
            
            # Cancel and notify about existing trades
            for trade_id_to_cancel in trades_to_cancel:
                del self.bot.active_trades[trade_id_to_cancel]
                print(f"Auto-cancelled existing trade {trade_id_to_cancel} to start new trade")

            # Start new trade
            trade_data = {
                "initiator": user_id,
                "partner": player.id,
                "initiator_items": {"cards": [], "coins": 0},
                "partner_items": {"cards": [], "coins": 0},
                "initiator_ready": False,
                "partner_ready": False,
                "created_at": time.time()
            }
            
            self.bot.active_trades[trade_id] = trade_data
            
            view = EnhancedTradeView(trade_data, self.bot, self.get_user_gacha_data, user_id, player.id, trade_id, self.gacha_system)
            
            embed = discord.Embed(
                title="Trade Started",
                description=f"Trade between **{ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name}** and **{player.display_name}**",
                color=discord.Color.blue()
            )
            
            # Add notification if trades were cancelled
            if trades_to_cancel:
                embed.add_field(
                    name="Previous Trades Cancelled",
                    value=f"Automatically cancelled {len(trades_to_cancel)} existing trade(s) to start this new one.",
                    inline=False
                )
            
            embed.add_field(
                name="Instructions",
                value="• Click **Add Cards** to search for cards by player name\n• Click **Add Coins** to add coins to your offer\n• Both players must **Ready Up** to complete the trade\n• Trade expires in 10 minutes",
                inline=False
            )
            
            embed.add_field(
                name="Trade Safety",
                value="• Favorited cards are protected and cannot be traded\n• Trade values are automatically calculated\n• Both parties must confirm before execution",
                inline=False
            )
            
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(embed=embed, view=view)
                message = await ctx.original_response()
                view.message = message
            else:
                message = await ctx.send(embed=embed, view=view)
                view.message = message
                
        elif action == "view":
            # Clean up expired trades first
            await self._cleanup_expired_trades()
            
            # Find active trade with this player
            active_trade = None
            for trade_id, trade_data in self.bot.active_trades.items():
                if {user_id, player.id} == {trade_data["initiator"], trade_data["partner"]}:
                    active_trade = (trade_id, trade_data)
                    break
            
            if not active_trade:
                embed = discord.Embed(
                    title="No Active Trade",
                    description=f"No active trade found with {player.display_name}",
                    color=discord.Color.red()
                )
                
                if hasattr(ctx, 'response'):
                    await ctx.response.send_message(embed=embed, ephemeral=True)
                else:
                    await ctx.send(embed=embed)
                return
            
            # Show current trade status
            trade_id, trade_data = active_trade
            view = EnhancedTradeView(trade_data, self.bot, self.get_user_gacha_data, trade_data["initiator"], trade_data["partner"], trade_id, self.gacha_system)
            
            embed = await view._build_detailed_trade_embed()
            
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(embed=embed, view=view)
                message = await ctx.original_response()
                view.message = message
            else:
                message = await ctx.send(embed=embed, view=view)
                view.message = message
                
        elif action == "cancel":
            # Clean up expired trades first
            await self._cleanup_expired_trades()
            
            # Find and cancel active trade
            trade_to_cancel = None
            for trade_id, trade_data in self.bot.active_trades.items():
                if {user_id, player.id} == {trade_data["initiator"], trade_data["partner"]}:
                    trade_to_cancel = trade_id
                    break
            
            if not trade_to_cancel:
                embed = discord.Embed(
                    title="No Active Trade",
                    description=f"No active trade found with {player.display_name}",
                    color=discord.Color.red()
                )
                
                if hasattr(ctx, 'response'):
                    await ctx.response.send_message(embed=embed, ephemeral=True)
                else:
                    await ctx.send(embed=embed)
                return
            
            # Cancel trade
            del self.bot.active_trades[trade_to_cancel]
            
            embed = discord.Embed(
                title="Trade Cancelled",
                description=f"Trade with {player.display_name} has been cancelled",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)

# ENHANCED TRADE VIEW WITH AUTO-UPDATES AND CARD SELECTION
class EnhancedTradeView(discord.ui.View):
    def __init__(self, trade_data, bot, get_user_data_func, initiator_id, partner_id, trade_id, gacha_system):
        super().__init__(timeout=600)  # 10 minute timeout
        self.trade_data = trade_data
        self.bot = bot
        self.get_user_data = get_user_data_func
        self.initiator_id = initiator_id
        self.partner_id = partner_id
        self.trade_id = trade_id
        self.gacha_system = gacha_system
        self.last_update_hash = self._get_trade_hash() # Initialize with current hash
        self.message = None # Will be set after the message is sent

    @discord.ui.button(label="Add Cards", style=discord.ButtonStyle.primary)
    async def add_cards(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.initiator_id, self.partner_id]:
            await interaction.response.send_message("Only trade participants can interact!", ephemeral=True)
            return
        
        user_data = self.get_user_data(interaction.user.id)
        
        if not user_data["cards"]:
            await interaction.response.send_message("You have no cards to trade!", ephemeral=True)
            return
        
        # Show enhanced card selection modal
        modal = EnhancedCardTradeModal(self.trade_data, interaction.user.id, self.initiator_id, self.partner_id, self.get_user_data, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Add Coins", style=discord.ButtonStyle.primary)
    async def add_coins(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.initiator_id, self.partner_id]:
            await interaction.response.send_message("Only trade participants can interact!", ephemeral=True)
            return
        
        modal = EnhancedCoinTradeModal(self.trade_data, interaction.user.id, self.initiator_id, self.partner_id, self.get_user_data, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Ready Up", style=discord.ButtonStyle.success)
    async def ready_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.initiator_id, self.partner_id]:
            await interaction.response.send_message("Only trade participants can interact!", ephemeral=True)
            return
        
        # Toggle ready status
        if interaction.user.id == self.initiator_id:
            self.trade_data["initiator_ready"] = not self.trade_data["initiator_ready"]
        else:
            self.trade_data["partner_ready"] = not self.trade_data["partner_ready"]
        
        # Check if both are ready
        if self.trade_data["initiator_ready"] and self.trade_data["partner_ready"]:
            await self._execute_trade(interaction) # interaction is fine here for the final response
        else:
            # For ready up, we are directly interacting with the main trade view,
            # so editing its own message via interaction.response.edit_message is correct.
            embed = await self._build_detailed_trade_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            self.last_update_hash = self._get_trade_hash() # Update hash after successful edit

    @discord.ui.button(label="Remove Items", style=discord.ButtonStyle.secondary)
    async def remove_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.initiator_id, self.partner_id]:
            await interaction.response.send_message("Only trade participants can interact!", ephemeral=True)
            return
        
        modal = RemoveItemsModal(self.trade_data, interaction.user.id, self.initiator_id, self.partner_id, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel Trade", style=discord.ButtonStyle.danger)
    async def cancel_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.initiator_id, self.partner_id]:
            await interaction.response.send_message("Only trade participants can interact!", ephemeral=True)
            return
        
        # Remove trade from active trades
        if self.trade_id in self.bot.active_trades:
            del self.bot.active_trades[self.trade_id]
        
        embed = discord.Embed(
            title="Trade Cancelled",
            description="The trade has been cancelled by one of the participants.",
            color=discord.Color.red()
        )
        
        # interaction.response.edit_message is correct here as it's a direct action on the view
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop() # Stop the view

    async def on_timeout(self):
        """Called when the view times out after 10 minutes"""
        try:
            # Remove trade from active trades
            if self.trade_id in self.bot.active_trades:
                del self.bot.active_trades[self.trade_id]
            
            # Update the message to show it expired
            if self.message:
                try:
                    embed = discord.Embed(
                        title="Trade Expired",
                        description="This trade has expired after 10 minutes of inactivity.\n\nUse `/osutrade @user start` to begin a new trade.",
                        color=discord.Color.red()
                    )
                    await self.message.edit(embed=embed, view=None)
                except (discord.NotFound, discord.Forbidden):
                    # Message was deleted or bot lacks permissions
                    pass
            
            print(f"Trade {self.trade_id} expired and was automatically cancelled")
            
        except Exception as e:
            print(f"Error handling trade timeout: {e}")

    async def auto_update_trade_embed(self): # Renamed and removed interaction parameter
        """Auto-update the trade display if something changed by editing self.message"""
        if not self.message:
            print(f"TradeView {self.trade_id}: self.message is not set. Cannot update embed.")
            return

        current_hash = self._get_trade_hash()
        if current_hash != self.last_update_hash:
            self.last_update_hash = current_hash
            embed = await self._build_detailed_trade_embed()
            
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.NotFound:
                print(f"Trade message {self.message.id} not found. Trade ID: {self.trade_id}. Stopping view.")
                if self.trade_id in self.bot.active_trades:
                    del self.bot.active_trades[self.trade_id]
                self.stop()
            except discord.Forbidden:
                print(f"Bot lacks permission to edit trade message {self.message.id}. Trade ID: {self.trade_id}")
            except Exception as e:
                print(f"Error editing trade message {self.message.id}: {e}. Trade ID: {self.trade_id}")


    def _get_trade_hash(self):
        """Generate a hash of the current trade state for change detection"""
        import hashlib
        trade_str = str(self.trade_data)
        return hashlib.md5(trade_str.encode()).hexdigest()

    async def _build_detailed_trade_embed(self):
        """Build detailed trade embed showing actual cards with thumbnails"""
        initiator = self.bot.get_user(self.initiator_id)
        partner = self.bot.get_user(self.partner_id)
        
        initiator_data = self.get_user_data(self.initiator_id)
        partner_data = self.get_user_data(self.partner_id)
        
        embed = discord.Embed(
            title="Trade Window",
            description=f"Trade between **{initiator.display_name}** and **{partner.display_name}**",
            color=discord.Color.blue()
        )
        
        # Initiator's offer
        initiator_items = self.trade_data["initiator_items"]
        initiator_cards_text = []
        
        if initiator_items["cards"]:
            for card_id in initiator_items["cards"]:
                if card_id in initiator_data["cards"]:
                    card = initiator_data["cards"][card_id]
                    player = card["player_data"]
                    
                    mutation_text = ""
                    if card["mutation"]:
                        mutation_name = card["mutation"].replace("_", " ").title()
                        mutation_text = f" - {mutation_name.upper()}"
                    
                    card_text = f"{'⭐' * card['stars']} {player['username']}{mutation_text}"
                    card_text += f"\n#{player['rank']:,} • {card['price']:,} coins"
                    initiator_cards_text.append(card_text)
        
        initiator_offer = []
        if initiator_cards_text:
            initiator_offer.append(f"**Cards ({len(initiator_cards_text)}):**\n" + "\n\n".join(initiator_cards_text))
        if initiator_items["coins"] > 0:
            initiator_offer.append(f"**Coins:** {initiator_items['coins']:,}")
        
        if not initiator_offer:
            initiator_offer.append("*No items offered*")
        
        ready_status_initiator = "✅ Ready" if self.trade_data["initiator_ready"] else "⏳ Not Ready"
        
        embed.add_field(
            name=f"{initiator.display_name}'s Offer {ready_status_initiator}",
            value="\n".join(initiator_offer),
            inline=True
        )
        
        # Partner's offer
        partner_items = self.trade_data["partner_items"]
        partner_cards_text = []
        
        if partner_items["cards"]:
            for card_id in partner_items["cards"]:
                if card_id in partner_data["cards"]:
                    card = partner_data["cards"][card_id]
                    player = card["player_data"]
                    
                    mutation_text = ""
                    if card["mutation"]:
                        mutation_name = card["mutation"].replace("_", " ").title()
                        mutation_text = f" - {mutation_name.upper()}"
                    
                    card_text = f"{'⭐' * card['stars']} {player['username']}{mutation_text}"
                    card_text += f"\n#{player['rank']:,} • {card['price']:,} coins"
                    partner_cards_text.append(card_text)
        
        partner_offer = []
        if partner_cards_text:
            partner_offer.append(f"**Cards ({len(partner_cards_text)}):**\n" + "\n\n".join(partner_cards_text))
        if partner_items["coins"] > 0:
            partner_offer.append(f"**Coins:** {partner_items['coins']:,}")
        
        if not partner_offer:
            partner_offer.append("*No items offered*")
        
        ready_status_partner = "✅ Ready" if self.trade_data["partner_ready"] else "⏳ Not Ready"
        
        embed.add_field(
            name=f"{partner.display_name}'s Offer {ready_status_partner}",
            value="\n".join(partner_offer),
            inline=True
        )
        
        # Trade status
        if self.trade_data["initiator_ready"] and self.trade_data["partner_ready"]:
            status_text = "🔄 Executing trade..."
        elif self.trade_data["initiator_ready"] or self.trade_data["partner_ready"]:
            status_text = "⏳ Waiting for both players to ready up"
        else:
            status_text = "📝 Add items and ready up to trade"
        
        embed.add_field(
            name="Trade Status",
            value=status_text,
            inline=False
        )
        
        # Calculate trade values
        initiator_value = initiator_items["coins"]
        partner_value = partner_items["coins"]
        
        for card_id in initiator_items["cards"]:
            if card_id in initiator_data["cards"]:
                initiator_value += initiator_data["cards"][card_id]["price"]
        
        for card_id in partner_items["cards"]:
            if card_id in partner_data["cards"]:
                partner_value += partner_data["cards"][card_id]["price"]
        
        embed.add_field(
            name="Trade Values",
            value=f"**{initiator.display_name}:** {initiator_value:,} coins\n**{partner.display_name}:** {partner_value:,} coins",
            inline=True
        )
        
        # Time remaining
        elapsed = time.time() - self.trade_data["created_at"]
        remaining = max(0, 600 - elapsed)  # 10 minutes
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        
        embed.add_field(
            name="Time Remaining",
            value=f"{minutes}:{seconds:02d}",
            inline=True
        )
        
        embed.set_footer(text="Both players must ready up to complete the trade")
        
        return embed

    async def _execute_trade(self, interaction):
        """Execute the trade with extensive validation and proper stat/achievement tracking"""
        try:
            initiator_data = self.get_user_data(self.initiator_id)
            partner_data = self.get_user_data(self.partner_id)
            
            initiator_items = self.trade_data["initiator_items"]
            partner_items = self.trade_data["partner_items"]
            
            # Validate trade is still possible
            if initiator_data["currency"] < initiator_items["coins"]:
                await interaction.response.send_message("Trade failed: Initiator doesn't have enough coins!", ephemeral=True)
                return
            
            if partner_data["currency"] < partner_items["coins"]:
                await interaction.response.send_message("Trade failed: Partner doesn't have enough coins!", ephemeral=True)
                return
            
            # Check favorited cards
            favorited_cards_messages = []
            for card_id in initiator_items["cards"]:
                if card_id in initiator_data["cards"] and initiator_data["cards"][card_id].get("is_favorite", False):
                    favorited_cards_messages.append(f"{initiator_data['cards'][card_id]['player_data']['username']} (Initiator's card)")
            for card_id in partner_items["cards"]:
                if card_id in partner_data["cards"] and partner_data["cards"][card_id].get("is_favorite", False):
                    favorited_cards_messages.append(f"{partner_data['cards'][card_id]['player_data']['username']} (Partner's card)")
            if favorited_cards_messages:
                await interaction.response.send_message(f"Trade failed: Favorited cards cannot be traded: {', '.join(favorited_cards_messages)}", ephemeral=True)
                return
            
            # Check cards still exist
            for card_id in initiator_items["cards"]:
                if card_id not in initiator_data["cards"]:
                    await interaction.response.send_message("Trade failed: Some of the initiator's offered cards no longer exist!", ephemeral=True)
                    return
            for card_id in partner_items["cards"]:
                if card_id not in partner_data["cards"]:
                    await interaction.response.send_message("Trade failed: Some of the partner's offered cards no longer exist!", ephemeral=True)
                    return
            
            # Execute trade
            # Transfer coins
            initiator_data["currency"] -= initiator_items["coins"]
            initiator_data["currency"] += partner_items["coins"]
            partner_data["currency"] -= partner_items["coins"]
            partner_data["currency"] += initiator_items["coins"]

            store_cog = self.bot.get_cog('Osu Gacha Store')
            if store_cog:
                store_cog.update_achievement_stats(initiator_data)
                store_cog.update_achievement_stats(partner_data)
            
            # Transfer cards
            for card_id in initiator_items["cards"]:
                card_data = initiator_data["cards"][card_id]
                del initiator_data["cards"][card_id]
                partner_data["cards"][card_id] = card_data
                if store_cog:
                    store_cog.update_achievement_stats(partner_data, card_data, "add")
            for card_id in partner_items["cards"]:
                card_data = partner_data["cards"][card_id]
                del partner_data["cards"][card_id]
                initiator_data["cards"][card_id] = card_data
                if store_cog:
                    store_cog.update_achievement_stats(initiator_data, card_data, "add")

            # --- Proper trade stat tracking for achievements and leaderboards ---
            for user_data in (initiator_data, partner_data):
                # Track in trading_stats for leaderboard/achievements
                if "trading_stats" not in user_data:
                    user_data["trading_stats"] = {}
                user_data["trading_stats"]["completed_trades"] = user_data["trading_stats"].get("completed_trades", 0) + 1

                # (Optional) Also increment legacy achievement_stats for compatibility
                if "achievement_stats" not in user_data:
                    user_data["achievement_stats"] = {}
                user_data["achievement_stats"]["trades_completed"] = user_data["achievement_stats"].get("trades_completed", 0) + 1

                # Instantly check for new achievements
                if hasattr(self.gacha_system, "check_and_award_achievements"):
                    self.gacha_system.check_and_award_achievements(user_data, user_data.get("user_id", None))

            # Save data
            trading_cog = self.bot.get_cog("Osu Gacha Trading")
            if trading_cog:
                trading_cog.save_user_data()
            else:
                print("Error: OsuGachaTradingCog not found for saving data.")
            
            # Remove trade from active trades
            if self.trade_id in self.bot.active_trades:
                del self.bot.active_trades[self.trade_id]
            
            # Get user objects for display
            initiator = self.bot.get_user(self.initiator_id)
            partner = self.bot.get_user(self.partner_id)
            
            # Success message
            embed = discord.Embed(
                title="Trade Completed Successfully!",
                description=f"Trade between **{initiator.display_name}** and **{partner.display_name}** has been completed!",
                color=discord.Color.green()
            )
            embed.add_field(
                name=f"{initiator.display_name} Received",
                value=f"**Cards:** {len(partner_items['cards'])}\n**Coins:** {partner_items['coins']:,}",
                inline=True
            )
            embed.add_field(
                name=f"{partner.display_name} Received",
                value=f"**Cards:** {len(initiator_items['cards'])}\n**Coins:** {initiator_items['coins']:,}",
                inline=True
            )
            embed.set_footer(text="Thank you for trading! Use /osucards to view your new collection.")
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception as e:
            print(f"Trade execution error: {e}")
            await interaction.response.send_message("Trade failed due to an unexpected error!", ephemeral=True)

# ENHANCED CARD SELECTION MODAL WITH DETAILED CARD CHOICES
class EnhancedCardTradeModal(discord.ui.Modal):
    def __init__(self, trade_data, user_id, initiator_id, partner_id, get_user_data_func, trade_view):
        super().__init__(title="Add Cards to Trade")
        self.trade_data = trade_data
        self.user_id = user_id
        self.initiator_id = initiator_id
        self.partner_id = partner_id
        self.get_user_data = get_user_data_func
        self.trade_view = trade_view

    player_names = discord.ui.TextInput(
        label="Player Names (comma-separated)",
        placeholder="e.g., mrekk, whitecat, vaxei",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_data = self.get_user_data(self.user_id)
            search_names = [name.strip().lower() for name in self.player_names.value.split(",")]
            
            # Find matching cards
            matching_cards = {}
            for card_id, card_data in user_data.get("cards", {}).items():
                player = card_data["player_data"]
                
                # Skip favorited cards
                if card_data.get("is_favorite", False):
                    continue
                
                # Check if any search name matches
                for search_name in search_names:
                    if search_name in player["username"].lower():
                        if search_name not in matching_cards:
                            matching_cards[search_name] = []
                        matching_cards[search_name].append((card_id, card_data))
                        break
            
            if not matching_cards:
                await interaction.response.send_message("No matching cards found! (Favorited cards cannot be traded)", ephemeral=True)
                return
            
            # Show detailed card selection if multiple versions of same player exist
            cards_needing_selection = {}
            cards_to_add_directly = []
            
            for player_name, cards in matching_cards.items():
                if len(cards) > 1:
                    cards_needing_selection[player_name] = cards
                else:
                    cards_to_add_directly.append(cards[0][0])
            
            # Add cards that don't need selection
            if cards_to_add_directly:
                if self.user_id == self.initiator_id:
                    existing_cards = self.trade_data["initiator_items"]["cards"]
                    new_cards = [card for card in cards_to_add_directly if card not in existing_cards]
                    self.trade_data["initiator_items"]["cards"].extend(new_cards)
                else:
                    existing_cards = self.trade_data["partner_items"]["cards"]
                    new_cards = [card for card in cards_to_add_directly if card not in existing_cards]
                    self.trade_data["partner_items"]["cards"].extend(new_cards)
            
            if cards_needing_selection:
                # Show detailed selection view for duplicate players
                view = DetailedCardSelectionView(cards_needing_selection, self.trade_data, self.user_id, self.initiator_id, self.partner_id, self.trade_view)
                
                embed = discord.Embed(
                    title="Multiple Card Versions Found",
                    description="You have multiple cards for some players. Select which ones to trade:",
                    color=discord.Color.blue()
                )
                
                for player_name, cards in cards_needing_selection.items():
                    card_list = []
                    for i, (card_id, card) in enumerate(cards[:3], 1):  # Show first 3
                        player = card["player_data"]
                        mutation_text = ""
                        if card["mutation"]:
                            mutation_name = card["mutation"].replace("_", " ").title()
                            mutation_text = f" - {mutation_name.upper()}"
                        
                        card_text = f"{i}. {'⭐' * card['stars']} {player['username']}{mutation_text}"
                        card_text += f"\n   #{player['rank']:,} • {card['price']:,} coins"
                        card_list.append(card_text)
                    
                    if len(cards) > 3:
                        card_list.append(f"... and {len(cards) - 3} more")
                    
                    embed.add_field(
                        name=f"{player_name.title()} ({len(cards)} cards)",
                        value="\n".join(card_list),
                        inline=True
                    )
                
                if cards_to_add_directly:
                    success_msg = f"✅ Added {len(cards_to_add_directly)} cards directly.\n"
                else:
                    success_msg = ""
                
                success_msg += "Choose specific cards for players with multiple versions:"
                embed.add_field(
                    name="Next Step",
                    value=success_msg,
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                # All cards added successfully
                await interaction.response.send_message(f"✅ Added **{len(cards_to_add_directly)}** cards to trade!", ephemeral=True)
            
            # Auto-update trade display
            await self.trade_view.auto_update_trade_embed()
            
        except Exception as e:
            print(f"Card trade modal error: {e}")
            await interaction.response.send_message("Error adding cards to trade!", ephemeral=True)

# DETAILED CARD SELECTION VIEW FOR DUPLICATE PLAYERS
class DetailedCardSelectionView(discord.ui.View):
    def __init__(self, cards_needing_selection, trade_data, user_id, initiator_id, partner_id, trade_view):
        super().__init__(timeout=300)
        self.cards_needing_selection = cards_needing_selection
        self.trade_data = trade_data
        self.user_id = user_id
        self.initiator_id = initiator_id
        self.partner_id = partner_id
        self.trade_view = trade_view
        
        # Add buttons for each player with multiple cards
        for player_name, cards in cards_needing_selection.items():
            button = discord.ui.Button(
                label=f"Select {player_name.title()} Card",
                style=discord.ButtonStyle.secondary,
                custom_id=f"select_{player_name}"
            )
            button.callback = self.create_player_callback(player_name, cards)
            self.add_item(button)
    
    def create_player_callback(self, player_name, cards):
        async def callback(interaction: discord.Interaction):
            # Show individual card selection for this player
            view = IndividualCardSelectionView(player_name, cards, self.trade_data, self.user_id, self.initiator_id, self.partner_id, self.trade_view)
            
            embed = discord.Embed(
                title=f"Select {player_name.title()} Card",
                description="Choose which specific card to add to the trade:",
                color=discord.Color.blue()
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
        
        return callback

# INDIVIDUAL CARD SELECTION FOR ONE PLAYER
class IndividualCardSelectionView(discord.ui.View):
    def __init__(self, player_name, cards, trade_data, user_id, initiator_id, partner_id, trade_view):
        super().__init__(timeout=300)
        self.player_name = player_name
        self.cards = cards
        self.trade_data = trade_data
        self.user_id = user_id
        self.initiator_id = initiator_id
        self.partner_id = partner_id
        self.trade_view = trade_view
        
        # Add buttons for each individual card
        for i, (card_id, card_data) in enumerate(cards[:5]):  # Max 5 buttons
            player = card_data["player_data"]
            
            mutation_text = ""
            if card_data["mutation"]:
                mutation_name = card_data["mutation"].replace("_", " ").title()
                mutation_text = f" - {mutation_name.upper()}"
            
            button_label = f"{'⭐' * card_data['stars']} {player['username']}{mutation_text}"
            if len(button_label) > 80:  # Discord button label limit
                button_label = button_label[:77] + "..."
            
            button = discord.ui.Button(
                label=button_label,
                style=discord.ButtonStyle.primary,
                custom_id=f"card_{i}"
            )
            button.callback = self.create_card_callback(card_id, card_data)
            self.add_item(button)
    
    def create_card_callback(self, card_id, card_data):
        async def callback(interaction: discord.Interaction):
            # Add the selected card to trade
            if self.user_id == self.initiator_id:
                if card_id not in self.trade_data["initiator_items"]["cards"]:
                    self.trade_data["initiator_items"]["cards"].append(card_id)
            else:
                if card_id not in self.trade_data["partner_items"]["cards"]:
                    self.trade_data["partner_items"]["cards"].append(card_id)
            
            player = card_data["player_data"]
            mutation_text = ""
            if card_data["mutation"]:
                mutation_name = card_data["mutation"].replace("_", " ").title()
                mutation_text = f" - {mutation_name.upper()}"
            
            embed = discord.Embed(
                title="Card Added!",
                description=f"Added **{'⭐' * card_data['stars']} {player['username']}{mutation_text}** to trade!",
                color=discord.Color.green()
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Auto-update trade display
            await self.trade_view.auto_update_trade_embed()
        
        return callback

# ENHANCED COIN MODAL WITH AUTO-UPDATE
class EnhancedCoinTradeModal(discord.ui.Modal):
    def __init__(self, trade_data, user_id, initiator_id, partner_id, get_user_data_func, trade_view):
        super().__init__(title="Add Coins to Trade")
        self.trade_data = trade_data
        self.user_id = user_id
        self.initiator_id = initiator_id
        self.partner_id = partner_id
        self.get_user_data = get_user_data_func
        self.trade_view = trade_view

    coin_amount = discord.ui.TextInput(
        label="Coin Amount",
        placeholder="Enter amount of coins to trade (e.g., 10000)",
        style=discord.TextStyle.short,
        max_length=20,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.coin_amount.value.replace(",", ""))
            
            if amount <= 0:
                await interaction.response.send_message("Coin amount must be positive!", ephemeral=True)
                return
            
            user_data = self.get_user_data(self.user_id)
            
            if amount > user_data["currency"]:
                await interaction.response.send_message(f"You only have {user_data['currency']:,} coins!", ephemeral=True)
                return
            
            # Add coins to trade
            if self.user_id == self.initiator_id:
                current_coins = self.trade_data["initiator_items"]["coins"]
                if current_coins + amount > user_data["currency"]:
                    await interaction.response.send_message("Cannot add more coins than you have!", ephemeral=True)
                    return
                self.trade_data["initiator_items"]["coins"] = current_coins + amount
            else:
                current_coins = self.trade_data["partner_items"]["coins"]
                if current_coins + amount > user_data["currency"]:
                    await interaction.response.send_message("Cannot add more coins than you have!", ephemeral=True)
                    return
                self.trade_data["partner_items"]["coins"] = current_coins + amount
            
            await interaction.response.send_message(f"✅ Added **{amount:,}** coins to trade!", ephemeral=True)
            
            # Auto-update trade display
            await self.trade_view.auto_update_trade_embed()
            
        except ValueError:
            await interaction.response.send_message("Invalid coin amount! Please enter a number.", ephemeral=True)
        except Exception as e:
            print(f"Coin trade modal error: {e}")
            await interaction.response.send_message("Error adding coins to trade!", ephemeral=True)

# REMOVE ITEMS MODAL
class RemoveItemsModal(discord.ui.Modal):
    def __init__(self, trade_data, user_id, initiator_id, partner_id, trade_view):
        super().__init__(title="Remove Items from Trade")
        self.trade_data = trade_data
        self.user_id = user_id
        self.initiator_id = initiator_id
        self.partner_id = partner_id
        self.trade_view = trade_view

    remove_type = discord.ui.TextInput(
        label="What to remove?",
        placeholder="Type 'cards' to remove all cards, 'coins' to remove all coins, or 'all' for everything",
        style=discord.TextStyle.short,
        max_length=20,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            remove_what = self.remove_type.value.lower().strip()
            
            if self.user_id == self.initiator_id:
                items = self.trade_data["initiator_items"]
            else:
                items = self.trade_data["partner_items"]
            
            removed_items = []
            
            if remove_what in ["cards", "all"]:
                if items["cards"]:
                    removed_items.append(f"{len(items['cards'])} cards")
                    items["cards"] = []
            
            if remove_what in ["coins", "all"]:
                if items["coins"] > 0:
                    removed_items.append(f"{items['coins']:,} coins")
                    items["coins"] = 0
            
            if removed_items:
                await interaction.response.send_message(f"✅ Removed {' and '.join(removed_items)} from trade!", ephemeral=True)
            else:
                await interaction.response.send_message("Nothing to remove!", ephemeral=True)
            
            # Auto-update trade display
            await self.trade_view.auto_update_trade_embed()
            
        except Exception as e:
            print(f"Remove items modal error: {e}")
            await interaction.response.send_message("Error removing items from trade!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(OsuGachaTradingCog(bot))