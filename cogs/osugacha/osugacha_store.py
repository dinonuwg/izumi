import discord
from discord.ext import commands
from discord import app_commands
import time
import asyncio
import random
from utils.helpers import *
from utils.config import *

# Import all the configuration and system
from .osugacha_config import *
from .osugacha_system import OsuGachaSystem

class SecureStoreView(discord.ui.View):
    """Base view with user security checks for store operations"""
    
    def __init__(self, user_id, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command user can interact with buttons"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You cannot interact with this command.", 
                ephemeral=True
            )
            return False
        return True

class CardSelectionView(SecureStoreView):
    """Secure view for card selection when selling"""
    
    def __init__(self, user_id, cog, player_name, matching_cards):
        super().__init__(user_id)
        self.cog = cog
        self.player_name = player_name
        self.matching_cards = matching_cards
        
        # Add selection buttons for each matching card
        for i, (card_id, card_data) in enumerate(matching_cards[:5]):  # Max 5 buttons
            player = card_data["player_data"]
            mutation_text = ""
            if card_data["mutation"]:
                mutation_name = self.cog.gacha_system.mutations[card_data["mutation"]]["name"]
                mutation_text = f" - {mutation_name.upper()}"
            
            button_label = f"{'⭐' * card_data['stars']} {player['username']}{mutation_text}"
            if len(button_label) > 80:  # Discord button label limit
                button_label = button_label[:77] + "..."
            
            button = discord.ui.Button(
                label=button_label,
                style=discord.ButtonStyle.secondary,
                custom_id=f"sell_{i}"
            )
            button.callback = self.create_callback(card_id, card_data)
            self.add_item(button)
    
    def create_callback(self, card_id, card_data):
        async def callback(interaction: discord.Interaction):
            await self.cog._handle_card_sell(interaction, card_id, card_data)
        return callback

class SellConfirmationView(SecureStoreView):
    """Secure view for sell confirmation"""
    
    def __init__(self, user_id, cog, card_id, card_data):
        super().__init__(user_id)
        self.cog = cog
        self.card_id = card_id
        self.card_data = card_data
    
    @discord.ui.button(label="Confirm Sale", style=discord.ButtonStyle.danger)
    async def confirm_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        # FIX: Pass None as ctx and interaction as the interaction parameter
        await self.cog._execute_card_sell(None, self.card_id, self.card_data, interaction)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Sale Cancelled",
            description="The card sale has been cancelled.",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class BulkSellConfirmationView(SecureStoreView):
    """Secure view for bulk sell confirmation"""
    
    def __init__(self, user_id, cog, cards_to_sell, total_value):
        super().__init__(user_id)
        self.cog = cog
        self.cards_to_sell = cards_to_sell
        self.total_value = total_value
    
    @discord.ui.button(label="Confirm Bulk Sale", style=discord.ButtonStyle.danger)
    async def confirm_bulk_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._execute_bulk_sell(interaction, self.cards_to_sell, self.total_value)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_bulk_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Bulk Sale Cancelled",
            description="The bulk sale has been cancelled.",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class SellAllConfirmationView(SecureStoreView):
    """Secure view for sell all confirmation"""
    
    def __init__(self, user_id, cog, rarity, cards_to_sell, total_value):
        super().__init__(user_id)
        self.cog = cog
        self.rarity = rarity
        self.cards_to_sell = cards_to_sell
        self.total_value = total_value
    
    @discord.ui.button(label="Confirm Sell All", style=discord.ButtonStyle.danger)
    async def confirm_sell_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._execute_sell_all(interaction, self.rarity, self.cards_to_sell, self.total_value)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_sell_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Sell All Cancelled",
            description="The sell all operation has been cancelled.",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class PurchaseConfirmationView(SecureStoreView):
    """Secure view for purchase confirmation"""
    
    def __init__(self, user_id, cog, crate_type, amount, total_cost):
        super().__init__(user_id)
        self.cog = cog
        self.crate_type = crate_type
        self.amount = amount
        self.total_cost = total_cost
    
    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.success)
    async def confirm_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._execute_purchase(interaction, self.crate_type, self.amount, self.total_cost)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Purchase Cancelled",
            description="The purchase has been cancelled.",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class QuickBuyModal(discord.ui.Modal):
    """Modal for selecting quantity to buy"""
    
    def __init__(self, cog, crate_type, available_stock, max_affordable):
        super().__init__(title=f"Buy {cog.gacha_system.crate_config[crate_type]['name']}")
        self.cog = cog
        self.crate_type = crate_type
        self.available_stock = available_stock
        self.max_affordable = max_affordable
        
        # Calculate max possible purchase
        max_possible = min(available_stock, max_affordable)
        
        self.quantity_input = discord.ui.TextInput(
            label="Quantity to Buy",
            placeholder=f"Enter amount (1-{max_possible}) - You have {available_stock} available",
            default="",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity_input.value)
            
            if quantity < 1:
                await interaction.response.send_message("❌ Quantity must be at least 1.", ephemeral=True)
                return
            
            if quantity > self.available_stock:
                await interaction.response.send_message(
                    f"❌ Not enough stock. You can buy up to {self.available_stock} crates.", 
                    ephemeral=True
                )
                return
            
            if quantity > self.max_affordable:
                await interaction.response.send_message(
                    f"❌ Not enough coins. You can afford up to {self.max_affordable} crates.", 
                    ephemeral=True
                )
                return
            
            # Execute the purchase
            await self.cog._execute_quick_buy(interaction, self.crate_type, quantity)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number.", ephemeral=True)

class EventBuyModal(discord.ui.Modal):
    """Modal for selecting quantity of event items to buy"""
    
    def __init__(self, events_cog, item_index, item_data, available_purchases, max_affordable):
        super().__init__(title=f"Buy {item_data['name']}")
        self.events_cog = events_cog
        self.item_index = item_index
        self.item_data = item_data
        self.available_purchases = available_purchases
        self.max_affordable = max_affordable
        
        # Calculate max possible purchase
        max_possible = min(available_purchases, max_affordable)
        
        self.quantity_input = discord.ui.TextInput(
            label="Quantity to Buy",
            placeholder=f"Enter amount (1-{max_possible}) - You can buy {available_purchases} more",
            default="",
            min_length=1,
            max_length=3,
            required=True
        )
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity_input.value)
            
            if quantity < 1:
                await interaction.response.send_message("❌ Quantity must be at least 1.", ephemeral=True)
                return
            
            if quantity > self.available_purchases:
                await interaction.response.send_message(
                    f"❌ You can only buy {self.available_purchases} more of this item.", 
                    ephemeral=True
                )
                return
            
            if quantity > self.max_affordable:
                await interaction.response.send_message(
                    f"❌ Not enough coins. You can afford up to {self.max_affordable} items.", 
                    ephemeral=True
                )
                return
            
            # Execute the bulk event purchase
            await self.events_cog._handle_event_item_bulk_purchase(interaction, self.item_index, quantity)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number.", ephemeral=True)

class QuickBuyView(SecureStoreView):
    """View for quick buy buttons in store announcements"""
    
    def __init__(self, cog, global_inventory):
        super().__init__(user_id=None, timeout=None)
        self.cog = cog
        self.global_inventory = global_inventory
        self._create_buttons()
    
    def _create_buttons(self):
        """Create the quick buy buttons"""
        crate_order = ["copper", "tin", "common", "uncommon", "rare", "epic", "legendary"]
        
        for crate_type in crate_order:
            if crate_type in self.global_inventory and self.global_inventory[crate_type] > 0:
                if crate_type in self.cog.gacha_system.crate_config:
                    crate_info = self.cog.gacha_system.crate_config[crate_type]
                    
                    # Set button style based on crate tier
                    if crate_type in ["copper", "tin"]:
                        button_style = discord.ButtonStyle.secondary
                    elif crate_type in ["common", "uncommon", "rare"]:
                        button_style = discord.ButtonStyle.success
                    elif crate_type in ["epic", "legendary"]:
                        button_style = discord.ButtonStyle.primary
                    else:
                        button_style = discord.ButtonStyle.secondary
                    
                    # Show stock in button label
                    stock_count = self.global_inventory[crate_type]
                    button = discord.ui.Button(
                        label=f"{crate_info['emoji']} {crate_info['name']} ({stock_count})",
                        style=button_style,
                        custom_id=f"quickbuy_{crate_type}"
                    )
                    button.callback = self.create_buy_callback(crate_type)
                    self.add_item(button)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True
    
    def create_buy_callback(self, crate_type):
        async def callback(interaction: discord.Interaction):
            await self.handle_quick_buy(interaction, crate_type)
        return callback
    
    async def handle_quick_buy(self, interaction: discord.Interaction, crate_type):
        """Handle quick buy button press - instant buy if low stock, modal otherwise"""
        user_id = interaction.user.id
        user_data = self.cog.get_user_gacha_data(user_id)
        
        # Get current store data
        store_data = self.cog.generate_global_store_stock()
        global_inventory = store_data["global_inventory"]
        current_period = store_data["period"]
        individual_stock = self.cog.get_user_remaining_stock(user_id, global_inventory, current_period)
        
        # Check if crate is available
        global_stock = global_inventory.get(crate_type, 0)
        if global_stock == 0:
            await interaction.response.send_message("❌ Out of stock.", ephemeral=True)
            return
        
        # Check user's personal stock
        available_stock = individual_stock.get(crate_type, 0)
        if available_stock == 0:
            await interaction.response.send_message("❌ You've reached your purchase limit.", ephemeral=True)
            return
        
        # Get crate info and calculate max affordable
        crate_info = self.cog.gacha_system.crate_config[crate_type]
        cost_per_crate = crate_info["price"]
        user_balance = user_data["currency"]
        max_affordable = user_balance // cost_per_crate
        
        if max_affordable == 0:
            await interaction.response.send_message(
                f"❌ Not enough coins. Need {cost_per_crate:,}, have {user_balance:,}.", 
                ephemeral=True
            )
            return
        
        # NEW: If global stock is less than 4, instantly buy 1 without modal
        if global_stock < 4:
            quantity = 1
            
            # Validate user can buy at least 1
            if available_stock < quantity:
                await interaction.response.send_message(
                    f"❌ Not enough stock. Available: {available_stock}", 
                    ephemeral=True
                )
                return
            
            if max_affordable < quantity:
                await interaction.response.send_message(
                    f"❌ Not enough coins. Need {cost_per_crate:,}, have {user_balance:,}.", 
                    ephemeral=True
                )
                return
            
            # Execute instant purchase
            await self.cog._execute_quick_buy(interaction, crate_type, quantity)
        else:
            # Original behavior: Show modal for quantity selection
            modal = QuickBuyModal(self.cog, crate_type, available_stock, max_affordable)
            await interaction.response.send_modal(modal)

class EmergencyPurchaseView(SecureStoreView):
    """Confirmation view for emergency cardboard box purchase"""
    
    def __init__(self, user_id, cog, cost):
        super().__init__(user_id)
        self.cog = cog
        self.cost = cost
    
    @discord.ui.button(label="Buy Emergency Crate", style=discord.ButtonStyle.green, emoji="📦")
    async def confirm_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_data = self.cog.get_user_gacha_data(interaction.user.id)
        current_balance = user_data['currency']
        
        try:
            # Deduct ALL remaining coins
            user_data['currency'] = max(0, user_data['currency'] - self.cost) 
            
            # Add copper crate (which is your cardboard box)
            if 'crates' not in user_data:
                user_data['crates'] = {}
            
            user_data['crates']['copper'] = user_data['crates'].get('copper', 0) + 1
            
            # Save data
            self.cog.save_user_data()
            
            embed = discord.Embed(
                title="📦 Emergency Crate Purchased!",
                description=f"✅ **Purchase successful!**\n\n"
                           f"**Cost:** {self.cost:,} coins (all remaining)\n"
                           f"**New Balance:** 0 coins\n"
                           f"**Cardboard Boxes:** {user_data['crates']['copper']:,}\n\n"
                           f"Use `/osuopen copper 1` to open it!",
                color=discord.Color.green()
            )
            
            embed.set_footer(text="Remember: Use /osudaily for more coins tomorrow!")
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            print(f"❌ Emergency purchase error: {e}")
            await interaction.response.send_message("❌ Purchase failed! Please try again.", ephemeral=True)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Purchase Cancelled",
            description="Emergency purchase cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class StoreWithEventsView(SecureStoreView):
    """Combined view with quick buy buttons for regular crates and event items"""
    
    def __init__(self, cog, global_inventory, active_event, events_cog):
        super().__init__(user_id=None, timeout=None)
        self.cog = cog
        self.global_inventory = global_inventory
        self.active_event = active_event
        self.events_cog = events_cog
        self._create_buttons()
    
    def _create_buttons(self):
        """Create both regular crate buttons and event item buttons"""
        # First add regular crate buttons (limited to make room for event items)
        crate_order = ["copper", "tin", "common", "uncommon", "rare", "epic", "legendary"]
        button_count = 0
        max_buttons = 20  # Discord limit is 25, leave room for event items
        
        for crate_type in crate_order:
            if button_count >= max_buttons:
                break
                
            if crate_type in self.global_inventory and self.global_inventory[crate_type] > 0:
                if crate_type in self.cog.gacha_system.crate_config:
                    crate_info = self.cog.gacha_system.crate_config[crate_type]
                    
                    # Set button style based on crate tier
                    if crate_type in ["copper", "tin"]:
                        button_style = discord.ButtonStyle.secondary
                    elif crate_type in ["common", "uncommon", "rare"]:
                        button_style = discord.ButtonStyle.success
                    elif crate_type in ["epic", "legendary"]:
                        button_style = discord.ButtonStyle.primary
                    else:
                        button_style = discord.ButtonStyle.secondary
                    
                    # Show stock in button label
                    stock_count = self.global_inventory[crate_type]
                    button = discord.ui.Button(
                        label=f"{crate_info['emoji']} {crate_info['name']} ({stock_count})",
                        style=button_style,
                        custom_id=f"quickbuy_{crate_type}"
                    )
                    button.callback = self.create_buy_callback(crate_type)
                    self.add_item(button)
                    button_count += 1
        
        # Add event item buttons
        if 'store_items' in self.active_event.get('definition', {}):
            for i, item_data in enumerate(self.active_event['definition']['store_items']):
                if button_count >= 25:  # Discord absolute limit
                    break
                    
                # Check remaining stock
                remaining = item_data['max_per_user']
                if remaining > 0:
                    button = discord.ui.Button(
                        label=f"⭐ {item_data['name']} ({remaining})",
                        style=discord.ButtonStyle.danger,  # Special color for event items
                        custom_id=f"event_{i}"
                    )
                    button.callback = self.create_event_buy_callback(i)
                    self.add_item(button)
                    button_count += 1
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True
    
    def create_buy_callback(self, crate_type):
        """Create callback for regular crate purchases"""
        async def callback(interaction: discord.Interaction):
            await self.handle_quick_buy(interaction, crate_type)
        return callback
    
    def create_event_buy_callback(self, item_index):
        """Create callback for event item purchases"""
        async def callback(interaction: discord.Interaction):
            await self.handle_event_buy(interaction, item_index)
        return callback
    
    async def handle_quick_buy(self, interaction: discord.Interaction, crate_type):
        """Handle regular crate quick buy (same as QuickBuyView)"""
        user_id = interaction.user.id
        user_data = self.cog.get_user_gacha_data(user_id)
        
        # Get current store data
        store_data = self.cog.generate_global_store_stock()
        global_inventory = store_data["global_inventory"]
        current_period = store_data["period"]
        individual_stock = self.cog.get_user_remaining_stock(user_id, global_inventory, current_period)
        
        # Check if crate is available
        global_stock = global_inventory.get(crate_type, 0)
        if global_stock == 0:
            await interaction.response.send_message("❌ Out of stock.", ephemeral=True)
            return
        
        # Check user's personal stock
        available_stock = individual_stock.get(crate_type, 0)
        if available_stock == 0:
            await interaction.response.send_message("❌ You've reached your purchase limit.", ephemeral=True)
            return
        
        # Get crate info and calculate max affordable
        crate_info = self.cog.gacha_system.crate_config[crate_type]
        cost_per_crate = crate_info["price"]
        user_balance = user_data["currency"]
        max_affordable = user_balance // cost_per_crate
        
        if max_affordable == 0:
            await interaction.response.send_message(
                f"❌ Not enough coins. Need {cost_per_crate:,}, have {user_balance:,}.", 
                ephemeral=True
            )
            return
        
        # If global stock is less than 4, instantly buy 1 without modal
        if global_stock < 4:
            quantity = 1
            
            # Validate user can buy at least 1
            if available_stock < quantity:
                await interaction.response.send_message(
                    f"❌ Not enough stock. Available: {available_stock}", 
                    ephemeral=True
                )
                return
            
            if max_affordable < quantity:
                await interaction.response.send_message(
                    f"❌ Not enough coins. Need {cost_per_crate:,}, have {user_balance:,}.", 
                    ephemeral=True
                )
                return
            
            # Execute instant purchase
            await self.cog._execute_quick_buy(interaction, crate_type, quantity)
        else:
            # Show modal for quantity selection
            modal = QuickBuyModal(self.cog, crate_type, available_stock, max_affordable)
            await interaction.response.send_modal(modal)
    
    async def handle_event_buy(self, interaction: discord.Interaction, item_index):
        """Handle event item purchase with quantity selection"""
        user_id = interaction.user.id
        
        # Check if event is still active
        if not self.events_cog.get_active_event():
            await interaction.response.send_message("❌ Event has ended.", ephemeral=True)
            return
        
        # Get current event data
        active_event = self.events_cog.get_active_event_for_guild(interaction.guild_id)
        if not active_event:
            await interaction.response.send_message("❌ No active event found!", ephemeral=True)
            return
        
        # Check if item exists in event
        store_items = active_event.get('definition', {}).get('store_items', [])
        if item_index >= len(store_items) or item_index < 0:
            await interaction.response.send_message("❌ Event item not found!", ephemeral=True)
            return
        
        item_data = store_items[item_index]
        
        # Get user data to check purchases and balance
        store_cog = self.cog
        user_data = store_cog.get_user_gacha_data(user_id)
        
        # Check user's current purchases
        user_purchases = active_event.get('user_purchases', {})
        user_purchase_data = user_purchases.get(str(user_id), {})
        purchased_count = user_purchase_data.get(str(item_index), 0)
        
        # Calculate how many more they can buy
        available_purchases = item_data['max_per_user'] - purchased_count
        
        if available_purchases <= 0:
            await interaction.response.send_message(
                f"❌ You've already purchased the maximum amount of **{item_data['name']}** ({item_data['max_per_user']})!",
                ephemeral=True
            )
            return
        
        # Calculate how many they can afford
        user_balance = user_data['currency']
        max_affordable = user_balance // item_data['price']
        
        if max_affordable == 0:
            await interaction.response.send_message(
                f"❌ Not enough coins! You need {item_data['price']:,} but have {user_balance:,}.",
                ephemeral=True
            )
            return
        
        # If they can only buy 1 or stock is very low, buy instantly
        max_possible = min(available_purchases, max_affordable)
        if max_possible == 1:
            # Execute single purchase
            await self.events_cog._handle_event_item_purchase(interaction, item_index)
        else:
            # Show modal for quantity selection
            modal = EventBuyModal(self.events_cog, item_index, item_data, available_purchases, max_affordable)
            await interaction.response.send_modal(modal)

class OsuGachaStoreCog(commands.Cog, name="Osu Gacha Store"):
    """Store and selling system cog with advanced global stock system"""

    def save_store_config(self):
        """Save store configuration to file"""
        try:
            save_json('data/store_config.json', STORE_ANNOUNCEMENT_CONFIG)
        except Exception as e:
            print(f"Error saving store config: {e}")

    def load_store_config(self):
        """Load store configuration from file"""
        try:
            config_data = load_json('data/store_config.json')
            if config_data:
                STORE_ANNOUNCEMENT_CONFIG.update(config_data)
                print(f"✅ Loaded store config: {STORE_ANNOUNCEMENT_CONFIG}")
                
                # Schedule message restoration for when the bot is ready
                if "last_message_id" in STORE_ANNOUNCEMENT_CONFIG and "channel_id" in STORE_ANNOUNCEMENT_CONFIG:
                    # We can't await in __init__, so we'll schedule it for later
                    self._needs_message_restore = True
        except FileNotFoundError:
            print("📁 No store config file found, using defaults")
        except Exception as e:
            print(f"Error loading store config: {e}")
    
    async def restore_tracked_message(self):
        """Restore message tracking after bot restart"""
        try:
            channel_id = STORE_ANNOUNCEMENT_CONFIG.get("channel_id")
            message_id = STORE_ANNOUNCEMENT_CONFIG.get("last_message_id")
            
            if channel_id and message_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(message_id)
                        self.store_announcement_message = message
                        print(f"✅ Restored tracked store message (ID: {message_id})")
                    except discord.NotFound:
                        print("⚠️ Previous store message not found, will create new one")
                        STORE_ANNOUNCEMENT_CONFIG.pop("last_message_id", None)
                        self.save_store_config()
        except Exception as e:
            print(f"Error restoring tracked message: {e}")
    
    def __init__(self, bot):
        self.bot = bot
        
        # Don't create new system - use the shared one
        if hasattr(bot, 'gacha_system'):
            self.gacha_system = bot.gacha_system
        else:
            # Fallback if system not loaded yet
            self.gacha_system = OsuGachaSystem()
            bot.gacha_system = self.gacha_system
        
        # Initialize flags
        self._needs_message_restore = False
        
        # Load store config from file
        self.load_store_config()
        
        # Store monitoring
        self.last_store_period = None
        self.store_monitor_task = None
        self.store_announcement_message = None  # NEW: Track the announcement message
        
        # Initialize current store period on startup to prevent missed refreshes
        current_time = int(time.time())
        refresh_interval = STORE_CONFIG["refresh_interval_minutes"] * 60
        self.last_store_period = current_time // refresh_interval
        
        # Start store monitoring if enabled
        if STORE_ANNOUNCEMENT_CONFIG.get("enabled", False):
            self.store_monitor_task = self.bot.loop.create_task(self.monitor_store_refresh())
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        # Restore message tracking after bot restart if needed
        if self._needs_message_restore:
            await self.restore_tracked_message()
            self._needs_message_restore = False

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

    def update_achievement_stats(self, user_data, card_data=None, operation="add"):
        """Update achievement stats when cards are added/removed"""
        if "achievement_stats" not in user_data:
            user_data["achievement_stats"] = {}
        
        stats = user_data["achievement_stats"]
        
        if operation == "add" and card_data:
            # Track when card is obtained
            player = card_data["player_data"]
            
            # Update best rank ever
            current_best = stats.get("best_rank_ever", float('inf'))
            if player["rank"] < current_best:
                stats["best_rank_ever"] = player["rank"]
            
            # Update highest card value ever
            current_highest = stats.get("highest_card_value", 0)
            if card_data["price"] > current_highest:
                stats["highest_card_value"] = card_data["price"]
            
            # Track countries visited
            if "countries_ever" not in stats:
                stats["countries_ever"] = []
            if player["country"] not in stats["countries_ever"]:
                stats["countries_ever"].append(player["country"])
            
            # Track mutations found
            if card_data.get("mutation"):
                if "mutations_ever" not in stats:
                    stats["mutations_ever"] = []
                if card_data["mutation"] not in stats["mutations_ever"]:
                    stats["mutations_ever"].append(card_data["mutation"])
        
        # Always update current maximums
        cards = user_data.get("cards", {})
        currency = user_data.get("currency", 0)
        
        if cards:
            # Update max cards ever
            current_cards = len(cards)
            stats["max_cards"] = max(stats.get("max_cards", 0), current_cards)
            
            # Update max collection value ever
            current_value = sum(card.get("price", 0) for card in cards.values())
            stats["max_collection_value"] = max(stats.get("max_collection_value", 0), current_value)
        
        # Update max currency ever
        stats["max_currency"] = max(stats.get("max_currency", 0), currency)

    async def monitor_store_refresh(self):
        """Monitor for store refreshes and send announcements"""
        await self.bot.wait_until_ready()
        print(f"🏪 Store monitor started - Current period: {self.last_store_period}")
        
        while not self.bot.is_closed():
            try:
                # Get current store data
                store_data = self.generate_global_store_stock()
                current_period = store_data["period"]
                
                # Check if store has refreshed
                if self.last_store_period is not None and current_period != self.last_store_period:
                    print(f"🔄 Store refresh detected: Period {self.last_store_period} → {current_period}")
                    await self.send_store_announcement(store_data)
                
                self.last_store_period = current_period
                
                # Wait 10 seconds before checking again
                await asyncio.sleep(10)
                
            except Exception as e:
                print(f"Error in store monitor: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def send_store_announcement(self, store_data):
        """Send or edit store refresh announcement with events included"""
        channel_id = STORE_ANNOUNCEMENT_CONFIG.get("channel_id")
        if not channel_id:
            return
        
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                print(f"Store announcement channel {channel_id} not found")
                return
            
            # Generate announcement embed (now includes events)
            embed = self.generate_store_announcement_embed()
            
            # Create view with quick buy buttons and event items
            view = None
            events_cog = self.bot.get_cog("OsuGachaEvents")
            if events_cog:
                # Get any active event for any guild (announcements are global)
                active_event = events_cog.get_active_event()
                if active_event and 'store_items' in active_event.get('definition', {}):
                    # Use combined view with event items
                    view = StoreWithEventsView(self, store_data["global_inventory"], active_event, events_cog)
                else:
                    # Use regular view
                    view = QuickBuyView(self, store_data["global_inventory"])
            else:
                # Fallback to regular view
                view = QuickBuyView(self, store_data["global_inventory"])
            
            # Optional role mention
            content = ""
            role_id = STORE_ANNOUNCEMENT_CONFIG.get("mention_role_id")
            if role_id:
                content = f"<@&{role_id}> "
            
            # Try to edit existing message first
            if self.store_announcement_message:
                try:
                    await self.store_announcement_message.edit(content=content, embed=embed, view=view)
                   # print(f"✅ Store announcement updated in #{channel.name}")
                    return
                except (discord.NotFound, discord.HTTPException):
                    # Message was deleted or can't be edited, create new one
                    self.store_announcement_message = None
                    STORE_ANNOUNCEMENT_CONFIG.pop("last_message_id", None)
            
            # Clear previous 5 messages before sending new announcement
            try:
                # Fetch recent messages (limit to reasonable amount to avoid rate limits)
                messages = []
                async for message in channel.history(limit=10):
                    messages.append(message)
                
                # Delete up to 5 most recent messages
                messages_to_delete = messages[:5]
                for msg in messages_to_delete:
                    try:
                        await msg.delete()
                        await asyncio.sleep(0.5)  # Small delay to avoid rate limits
                    except (discord.NotFound, discord.HTTPException):
                        # Message might already be deleted or we lack permissions
                        pass
                
            except Exception as e:
                print(f"Warning: Could not clear previous messages: {e}")
            
            # Send new message if no existing message or edit failed
            self.store_announcement_message = await channel.send(content=content, embed=embed, view=view)
            
            # Save message ID for persistence through restarts
            STORE_ANNOUNCEMENT_CONFIG["last_message_id"] = self.store_announcement_message.id
            self.save_store_config()
           # print(f"✅ New store announcement sent to #{channel.name}")
            
        except Exception as e:
            print(f"Error sending store announcement: {e}")

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        if self.store_monitor_task:
            self.store_monitor_task.cancel()

    def generate_store_announcement_embed(self):
        """Generate a global store announcement embed (not user-specific)"""
        store_data = self.generate_global_store_stock()
        global_inventory = store_data["global_inventory"]
        refresh_time = store_data["refresh_time"]
        
        refresh_timestamp = f"<t:{refresh_time}:R>"
        
        embed = discord.Embed(
            title="🏪 Global Crate Store",
            description=f"**Current Inventory** • Next refresh {refresh_timestamp}",
            color=discord.Color.blue()
        )
        
        # Group crates by tier
        tier_groups = {
            "Starter Crates": ["copper", "tin"],
            "Standard Crates": ["common", "uncommon"], 
            "Premium Crates": ["rare", "epic"],
            "Elite Crates": ["legendary"]
        }
        
        for tier_name, crate_types in tier_groups.items():
            tier_text = ""
            
            for crate_type in crate_types:
                if crate_type not in self.gacha_system.crate_config:
                    continue
                    
                crate_info = self.gacha_system.crate_config[crate_type]
                global_amount = global_inventory.get(crate_type, 0)
                
                if global_amount == 0:
                    continue
                
                description = STORE_DESCRIPTIONS.get(crate_type, "A standard crate.")
                
                # Status indicator based on stock
                if global_amount >= 3:
                    status = "🟢 High Stock"
                elif global_amount >= 1:
                    status = "🟡 Medium Stock"
                elif global_amount > 0:
                    status = "🟠 Low Stock"
                else:
                    status = "🔴 Out of Stock"
                
                tier_text += f"{crate_info['emoji']} **{crate_info['name']}**\n"
                if STORE_ANNOUNCEMENT_CONFIG.get("include_descriptions", True):
                    tier_text += f"{description}\n"
                tier_text += f"**Price:** {crate_info['price']:,} coins\n"
                tier_text += f"**Stock:** {global_amount} available\n{status}\n\n"
            
            if tier_text:
                embed.add_field(
                    name=tier_name,
                    value=tier_text,
                    inline=True
                )
        
        # Add instructions
        embed.add_field(
            name="How to Purchase",
            value="• **Click buttons below** to buy crates (choose quantity)\n"
                "• Use `/osustore` to view your personal limits\n" 
                "• Use `/osubuy [crate] [amount]` for command purchases\n"
                "• Use `/osudaily` for free coins and crates!",
            inline=False
        )
        
        # Add active event section if there's an event
        events_cog = self.bot.get_cog("OsuGachaEvents")
        if events_cog:
            active_event = events_cog.get_active_event()
            if active_event and 'store_items' in active_event.get('definition', {}):
                event_text = ""
                
                for item_data in active_event['definition']['store_items']:
                    # Check remaining stock (from active event tracking)
                    item_name = item_data['name']
                    remaining = item_data['max_per_user']  # This will be updated during purchases
                    
                    if remaining > 0:
                        # Format price consistently with regular crates
                        if item_data['price'] >= 1000000:
                            price_text = f"{item_data['price'] // 1000000}M"
                        elif item_data['price'] >= 1000:
                            price_text = f"{item_data['price'] // 1000}K"
                        else:
                            price_text = f"{item_data['price']:,}"
                        
                        # Status based on stock (same as regular crates)
                        if remaining >= 50:
                            status = "🟢 High Stock"
                        elif remaining >= 20:
                            status = "🟡 Medium Stock" 
                        elif remaining > 0:
                            status = "🟠 Low Stock"
                        else:
                            status = "🔴 Out of Stock"
                        
                        event_text += f"**{item_data['name']}**\n"
                        if STORE_ANNOUNCEMENT_CONFIG.get("include_descriptions", True):
                            description = item_data.get('description', 'Special event item.')
                            event_text += f"{description}\n"
                        event_text += f"**Price:** {price_text} coins\n"
                        event_text += f"**Stock:** {remaining} available\n{status}\n\n"
                
                if event_text:
                    # Use Unix timestamp for event end time (no need to update)
                    end_timestamp = int(active_event['end_time'])
                    embed.add_field(
                        name=f"⭐ {active_event['name']} - Ends <t:{end_timestamp}:R>",
                        value=event_text,
                        inline=False
                    )
        
        embed.set_footer(text=f"🔄 Store refreshes every {STORE_CONFIG['refresh_interval_minutes']} minutes • Click buttons to purchase!")
        
        return embed

    def generate_global_store_stock(self):
        """Generate global store inventory (same for all users)"""
        current_time = int(time.time())
        refresh_interval = STORE_CONFIG["refresh_interval_minutes"] * 60
        
        # Calculate current refresh period
        current_period = current_time // refresh_interval
        next_refresh = (current_period + 1) * refresh_interval
        
        # Use ONLY the period as seed for consistent global inventory
        random.seed(f"global_store_{current_period}")
        
        global_inventory = {}
        
        for crate_type in self.gacha_system.crate_config.keys():
            # NEW: Use advanced appearance system
            stock_amount = self._determine_crate_stock(crate_type)
            if stock_amount > 0:
                global_inventory[crate_type] = stock_amount
        
        # Reset random seed
        random.seed()
        
        return {
            "global_inventory": global_inventory,
            "refresh_time": next_refresh,
            "period": current_period
        }
    
    def _determine_crate_stock(self, crate_type):
        """Determine how many crates of this type should appear in store"""
        import random
        
        # Check if advanced system is enabled
        advanced_config = STORE_CONFIG.get("advanced_appearance", {})
        if not advanced_config.get("enabled", False):
            # Use simple system (original behavior)
            if random.random() <= STORE_CONFIG["appearance_weights"][crate_type]:
                min_stock, max_stock = STORE_CONFIG["stock_ranges"][crate_type]
                return random.randint(min_stock, max_stock)
            return 0
        
        # Use advanced system
        mode = advanced_config.get("mode", "decay")
        min_stock, max_stock = STORE_CONFIG["stock_ranges"][crate_type]
        
        if mode == "fixed":
            return self._calculate_fixed_rates(crate_type, min_stock, max_stock, advanced_config)
        elif mode == "decay":
            return self._calculate_decay_rates(crate_type, min_stock, max_stock, advanced_config)
        else:
            # Fallback to simple
            if random.random() <= STORE_CONFIG["appearance_weights"][crate_type]:
                return random.randint(min_stock, max_stock)
            return 0
        
    async def _execute_quick_buy(self, interaction, crate_type, quantity):
        """Execute quick buy with specified quantity"""
        user_id = interaction.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Get current store data
        store_data = self.generate_global_store_stock()
        global_inventory = store_data["global_inventory"]
        current_period = store_data["period"]
        individual_stock = self.get_user_remaining_stock(user_id, global_inventory, current_period)
        
        # Final validation
        available_stock = individual_stock.get(crate_type, 0)
        crate_info = self.gacha_system.crate_config[crate_type]
        total_cost = crate_info["price"] * quantity
        
        if available_stock < quantity:
            await interaction.response.send_message(
                f"❌ Not enough stock. Available: {available_stock}", 
                ephemeral=True
            )
            return
        
        if user_data["currency"] < total_cost:
            await interaction.response.send_message(
                f"❌ Not enough coins. Need {total_cost:,}, have {user_data['currency']:,}.", 
                ephemeral=True
            )
            return
        
        try:
            # Execute purchase
            user_data["currency"] -= total_cost
            
            if "crates" not in user_data:
                user_data["crates"] = {}
            user_data["crates"][crate_type] = user_data["crates"].get(crate_type, 0) + quantity
            
            # Update purchase history
            if "purchase_history" not in user_data:
                user_data["purchase_history"] = {}
            
            period_key = str(current_period)
            if period_key not in user_data["purchase_history"]:
                user_data["purchase_history"][period_key] = {}
            
            user_data["purchase_history"][period_key][crate_type] = \
                user_data["purchase_history"][period_key].get(crate_type, 0) + quantity
            
            # Update achievement stats
            user_data["achievement_stats"]["crates_bought"] = \
                user_data["achievement_stats"].get("crates_bought", 0) + quantity
            self.update_achievement_stats(user_data)
            
            # Save data
            self.save_user_data()
            
            # Get updated stock for display
            updated_individual_stock = self.get_user_remaining_stock(user_id, global_inventory, current_period)
            remaining_stock = updated_individual_stock.get(crate_type, 0)
            
            # Success message
            await interaction.response.send_message(
                f"✅ Bought **{quantity}x {crate_info['name']}** {crate_info['emoji']} for **{total_cost:,}** coins!\n"
                f"💰 Balance: **{user_data['currency']:,}** coins\n"
                f"📦 Your stock: **{remaining_stock}** remaining\n"
                f"🎁 Total crates: **{user_data['crates'][crate_type]}** {crate_info['name']}",
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Quick buy error: {e}")
            await interaction.response.send_message("❌ Purchase failed. Please try again.", ephemeral=True)

    def _calculate_fixed_rates(self, crate_type, min_stock, max_stock, advanced_config):
        """Calculate stock using fixed rates per quantity"""
        import random
        
        fixed_rates = advanced_config.get("fixed_rates", {})
        if crate_type not in fixed_rates:
            # Fallback to simple rate
            if random.random() <= STORE_CONFIG["appearance_weights"][crate_type]:
                return random.randint(min_stock, max_stock)
            return 0
        
        # Check each quantity from highest to lowest
        crate_rates = fixed_rates[crate_type]
        for quantity in range(max_stock, min_stock - 1, -1):
            if quantity in crate_rates:
                chance = crate_rates[quantity]
                if random.random() <= chance:
                    return quantity
        
        return 0

    def _calculate_decay_rates(self, crate_type, min_stock, max_stock, advanced_config):
        """Calculate stock using decay rate system - sequential rolling"""
        import random
        
        decay_rates = advanced_config.get("decay_rates", {})
        if crate_type not in decay_rates:
            # Fallback to simple rate
            if random.random() <= STORE_CONFIG["appearance_weights"][crate_type]:
                return random.randint(min_stock, max_stock)
            return 0
        
        crate_config = decay_rates[crate_type]
        base_chance = crate_config.get("base", 0.5)
        decay_rate = crate_config.get("decay_rate", 0.1)
        
        # Sequential rolling - start with 0 crates
        quantity = 0
        
        # Roll for each quantity sequentially
        for q in range(min_stock, max_stock + 1):
            # Calculate chance for this quantity: base_chance * (1 - decay_rate) ** (q - 1)
            chance = base_chance * (1 - decay_rate) ** (q - 1)
            
            # Roll for this quantity
            if random.random() <= chance:
                quantity = q
            else:
                # Failed to get this quantity, stop rolling
                break
        
        return quantity

    def get_user_remaining_stock(self, user_id, global_inventory, current_period):
        """Calculate user's remaining stock based on their purchases"""
        user_data = self.get_user_gacha_data(user_id)
        
        # Use the persistent purchase_history from user data instead of memory
        purchase_history = user_data.get("purchase_history", {})
        period_key = str(current_period)
        user_purchases = purchase_history.get(period_key, {})
        
        individual_stock = {}
        for crate_type, global_amount in global_inventory.items():
            purchased_amount = user_purchases.get(crate_type, 0)
            remaining_stock = max(0, global_amount - purchased_amount)
            individual_stock[crate_type] = remaining_stock
        
        return individual_stock

    # SLASH COMMANDS
    @app_commands.command(name="osustorerefresh", description="[ADMIN] Force refresh store inventory")
    @app_commands.default_permissions(administrator=True)
    async def store_force_refresh_slash(self, interaction: discord.Interaction):
        """Force an immediate store refresh"""
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return
        
        try:
            # Temporarily pause monitor to prevent conflicts
            monitor_was_running = self.store_monitor_task is not None
            if monitor_was_running:
                self.store_monitor_task.cancel()
            
            # Get current time info
            current_time = int(time.time())
            refresh_interval = STORE_CONFIG["refresh_interval_minutes"] * 60
            current_period = current_time // refresh_interval
            
            # Force advance to next period (this triggers immediate refresh)
            next_period = current_period + 1
            next_refresh_time = (next_period + 1) * refresh_interval
            
            # Generate new store inventory for the next period
            import random
            random.seed(f"global_store_{next_period}")
            
            new_inventory = {}
            for crate_type in self.gacha_system.crate_config.keys():
                stock_amount = self._determine_crate_stock(crate_type)
                if stock_amount > 0:
                    new_inventory[crate_type] = stock_amount
            
            random.seed()  # Reset seed
            
            # Create store data for the new period
            new_store_data = {
                "global_inventory": new_inventory,
                "refresh_time": next_refresh_time,
                "period": next_period
            }
            
            # Update internal tracking
            self.last_store_period = next_period
            
            # Send store announcement with new inventory
            await self.send_store_announcement(new_store_data)
            
            # Restart monitor if it was running
            if monitor_was_running:
                self.store_monitor_task = self.bot.loop.create_task(self.monitor_store_refresh())
            
            await interaction.response.send_message(
                f"✅ **Store refreshed instantly!**\n"
                f"**Period:** {current_period} → {next_period}\n"
                f"**Next refresh:** <t:{next_refresh_time}:R>\n"
                f"New inventory has been generated and announced!", 
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @app_commands.command(name="osustoreconfig", description="[ADMIN] Configure store announcements")
    @app_commands.describe(
        channel="Channel for store announcements",
        role="Role to mention (optional)",
        enabled="Enable/disable announcements"
    )
    @app_commands.default_permissions(administrator=True)
    async def store_config_slash(self, interaction: discord.Interaction, 
                                channel: discord.TextChannel = None, 
                                role: discord.Role = None,
                                enabled: bool = None):
        
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return
        
        changes = []
        
        if channel is not None:
            STORE_ANNOUNCEMENT_CONFIG["channel_id"] = channel.id
            changes.append(f"📢 Channel set to {channel.mention}")
        
        if role is not None:
            STORE_ANNOUNCEMENT_CONFIG["mention_role_id"] = role.id
            changes.append(f"👥 Mention role set to {role.mention}")
        
        if enabled is not None:
            STORE_ANNOUNCEMENT_CONFIG["enabled"] = enabled
            if enabled:
                changes.append("✅ Store announcements enabled")
                # Restart monitoring task
                if self.store_monitor_task:
                    self.store_monitor_task.cancel()
                self.store_monitor_task = self.bot.loop.create_task(self.monitor_store_refresh())
            else:
                changes.append("❌ Store announcements disabled")
                if self.store_monitor_task:
                    self.store_monitor_task.cancel()
        
        # Save changes to file
        self.save_store_config()
        
        if not changes:
            # Show current config
            channel_id = STORE_ANNOUNCEMENT_CONFIG.get("channel_id")
            role_id = STORE_ANNOUNCEMENT_CONFIG.get("mention_role_id")
            is_enabled = STORE_ANNOUNCEMENT_CONFIG.get("enabled", False)
            
            embed = discord.Embed(
                title="Store Announcement Configuration",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Status",
                value="✅ Enabled" if is_enabled else "❌ Disabled",
                inline=True
            )
            
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                embed.add_field(
                    name="Channel",
                    value=f"<#{channel_id}>" if channel else f"Unknown ({channel_id})",
                    inline=True
                )
            else:
                embed.add_field(
                    name="Channel",
                    value="Not configured",
                    inline=True
                )
            
            if role_id:
                embed.add_field(
                    name="Mention Role",
                    value=f"<@&{role_id}>",
                    inline=True
                )
            else:
                embed.add_field(
                    name="Mention Role", 
                    value="None",
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Store Configuration Updated",
                description="\n".join(changes),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="osustoretest", description="[ADMIN] Test store announcement")
    @app_commands.default_permissions(administrator=True)
    async def store_test_slash(self, interaction: discord.Interaction):
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permissions required.", ephemeral=True)
            return
        
        channel_id = STORE_ANNOUNCEMENT_CONFIG.get("channel_id")
        if not channel_id:
            await interaction.response.send_message("❌ No announcement channel configured. Use `/osustoreconfig` first.", ephemeral=True)
            return
        
        try:
            # Send test announcement
            store_data = self.generate_global_store_stock()
            await self.send_store_announcement(store_data)
            
            await interaction.response.send_message("✅ Test store announcement sent!", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error sending test announcement: {str(e)}", ephemeral=True)

    @app_commands.command(name="osustore", description="Browse the osu! crate store")
    async def osu_store_slash(self, interaction: discord.Interaction):
        ctx = await self.bot.get_context(interaction)
        await self._store_command(ctx, interaction)

    @app_commands.command(name="osubuy", description="Buy crates from the store")
    @app_commands.describe(
        crate_type="Type of crate to buy",
        amount="Amount to buy (default: 1)"
    )
    @app_commands.choices(crate_type=[
        app_commands.Choice(name="Copper Crate", value="copper"),
        app_commands.Choice(name="Tin Crate", value="tin"), 
        app_commands.Choice(name="Bronze Crate", value="common"),
        app_commands.Choice(name="Silver Crate", value="uncommon"),
        app_commands.Choice(name="Gold Crate", value="rare"),
        app_commands.Choice(name="Diamond Crate", value="epic"),
        app_commands.Choice(name="Rainbow Crate", value="legendary")
    ])
    async def osu_buy_slash(self, interaction: discord.Interaction, crate_type: str, amount: int = 1):
        ctx = await self.bot.get_context(interaction)
        await self._buy_command(ctx, crate_type, amount, interaction)

    @app_commands.command(name="osueventbuy", description="Buy limited event items")
    @app_commands.describe(
        item_name="Name of the event item to buy",
        amount="Amount to buy (default: 1)"
    )
    async def osu_event_buy_slash(self, interaction: discord.Interaction, item_name: str, amount: int = 1):
        """Buy event items"""
        # Check for active event
        events_cog = self.bot.get_cog("OsuGachaEvents")
        if not events_cog:
            await interaction.response.send_message("❌ Events system not loaded!", ephemeral=True)
            return
        
        active_event = events_cog.get_active_event_for_guild(interaction.guild_id)
        if not active_event:
            await interaction.response.send_message("❌ No active event in this server!", ephemeral=True)
            return
        
        if 'store_items' not in active_event['definition']:
            await interaction.response.send_message("❌ Current event has no store items!", ephemeral=True)
            return
        
        # Find the item
        event_item = None
        for item in active_event['definition']['store_items']:
            if item['name'].lower() == item_name.lower():
                event_item = item
                break
        
        if not event_item:
            available_items = [item['name'] for item in active_event['definition']['store_items']]
            await interaction.response.send_message(
                f"❌ Item not found! Available items:\n• {', '.join(available_items)}", 
                ephemeral=True
            )
            return
        
        # Process the purchase
        user_id = interaction.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Check user's event purchases
        event_purchases = user_data.get('event_purchases', {})
        event_id = active_event['id']
        user_event_data = event_purchases.get(event_id, {})
        purchased_amount = user_event_data.get(event_item['name'], 0)
        
        # Validate purchase
        remaining = event_item['max_per_user'] - purchased_amount
        if amount > remaining:
            await interaction.response.send_message(
                f"❌ You can only buy {remaining} more {event_item['name']}(s)! "
                f"(You've already bought {purchased_amount}/{event_item['max_per_user']})",
                ephemeral=True
            )
            return
        
        total_cost = event_item['price'] * amount
        if user_data['currency'] < total_cost:
            await interaction.response.send_message(
                f"❌ Not enough coins! You need {total_cost:,} coins but only have {user_data['currency']:,}.",
                ephemeral=True
            )
            return
        
        # Process purchase
        user_data['currency'] -= total_cost
        
        # Update event purchases tracking
        if 'event_purchases' not in user_data:
            user_data['event_purchases'] = {}
        if event_id not in user_data['event_purchases']:
            user_data['event_purchases'][event_id] = {}
        
        user_data['event_purchases'][event_id][event_item['name']] = purchased_amount + amount
        
        # Add event crates to inventory as special crates
        if 'event_crates' not in user_data:
            user_data['event_crates'] = {}
        if event_item['name'] not in user_data['event_crates']:
            user_data['event_crates'][event_item['name']] = 0
        
        user_data['event_crates'][event_item['name']] += amount
        
        # Save data
        self.bot.pending_saves = True
        
        # Success message
        embed = discord.Embed(
            title="🎉 Event Purchase Successful!",
            description=f"You bought **{amount}x {event_item['name']}** {event_item['emoji']}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="💰 Cost", 
            value=f"{total_cost:,} coins",
            inline=True
        )
        
        embed.add_field(
            name="💳 Balance", 
            value=f"{user_data['currency']:,} coins",
            inline=True
        )
        
        new_remaining = remaining - amount
        embed.add_field(
            name="📦 Remaining", 
            value=f"{new_remaining}/{event_item['max_per_user']}",
            inline=True
        )
        
        embed.add_field(
            name="🎪 Event",
            value=f"{active_event['name']}\nEnds in {events_cog.format_time_remaining(active_event['end_time'])}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="osusell", description="Sell a specific card")
    @app_commands.describe(player_name="Name of the player card to sell")
    async def osu_sell_slash(self, interaction: discord.Interaction, player_name: str):
        ctx = await self.bot.get_context(interaction)
        await self._sell_command(ctx, player_name, interaction)

    @app_commands.command(name="osusellbulk", description="Sell multiple cards at once")
    @app_commands.describe(player_names="Comma-separated list of player names")
    async def osu_sell_bulk_slash(self, interaction: discord.Interaction, player_names: str):
        ctx = await self.bot.get_context(interaction)
        await self._sell_bulk_command(ctx, player_names, interaction)

    @app_commands.command(name="osusellall", description="Sell all cards of a specific rarity")
    @app_commands.describe(
        rarity="Star rating (1-6)"
    )
    @app_commands.choices(rarity=[
        app_commands.Choice(name="1 Star", value="1"),
        app_commands.Choice(name="2 Stars", value="2"),
        app_commands.Choice(name="3 Stars", value="3"),
        app_commands.Choice(name="4 Stars", value="4"),
        app_commands.Choice(name="5 Stars", value="5"),
        app_commands.Choice(name="6 Stars", value="6")
    ])
    async def osu_sell_all_slash(self, interaction: discord.Interaction, rarity: str):
        ctx = await self.bot.get_context(interaction)
        await self._sell_all_command(ctx, rarity, "yes", interaction)  # Auto-pass "yes"

    # PREFIX COMMANDS
    @commands.command(name="osustore", aliases=["ostore", "store"])
    async def osu_store_prefix(self, ctx: commands.Context):
        await self._store_command(ctx)

    @commands.command(name="osubuy", aliases=["obuy", "buy"])
    async def osu_buy_prefix(self, ctx: commands.Context, crate_type: str = None, amount: int = 1):
        if not crate_type:
            embed = discord.Embed(
                title="Missing Crate Type",
                description="Please specify a crate type to buy!\n\nExample: `!osubuy bronze 3`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        await self._buy_command(ctx, crate_type, amount)

    @commands.command(name="osusell", aliases=["osell", "sell"])
    async def osu_sell_prefix(self, ctx: commands.Context, *, player_name: str = None):
        if not player_name:
            embed = discord.Embed(
                title="Missing Player Name",
                description="Please specify a player name to sell!\n\nExample: `!osusell mrekk`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        await self._sell_command(ctx, player_name)

    @commands.command(name="osusellbulk", aliases=["osellbulk", "sellbulk"])
    async def osu_sell_bulk_prefix(self, ctx: commands.Context, *, player_names: str = None):
        if not player_names:
            embed = discord.Embed(
                title="Missing Player Names",
                description="Please specify player names to sell!\n\nExample: `!osusellbulk mrekk, whitecat, vaxei`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        await self._sell_bulk_command(ctx, player_names)

    @commands.command(name="osusellall", aliases=["osellall", "sellall"])
    async def osu_sell_all_prefix(self, ctx: commands.Context, rarity: str = None):
        if not rarity:
            embed = discord.Embed(
                title="Invalid Usage",
                description="Usage: `!osusellall <1-6>`\n\nExample: `!osusellall 1` (sells all 1-star cards)",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        await self._sell_all_command(ctx, rarity, "yes")  # Auto-pass "yes"

    # SHARED COMMAND IMPLEMENTATIONS
    async def _store_command(self, ctx, interaction=None):
        """Show the osu! crate store with advanced global stock system and event stores"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        confirmations_enabled = user_data.get("confirmations_enabled", True)
        
        # Check for active events
        events_cog = self.bot.get_cog("OsuGachaEvents")
        active_event = None
        if events_cog:
            active_event = events_cog.get_active_event_for_guild(ctx.guild.id)
        
        # Generate global store data
        store_data = self.generate_global_store_stock()
        global_inventory = store_data["global_inventory"]
        refresh_time = store_data["refresh_time"]
        current_period = store_data["period"]
        
        # Get user's remaining stock
        individual_stock = self.get_user_remaining_stock(user_id, global_inventory, current_period)
        
        # Create dynamic timestamp for Discord
        refresh_timestamp = f"<t:{refresh_time}:R>"
        
        # Check if we should show event store
        if active_event and 'store_items' in active_event['definition']:
            embed = discord.Embed(
                title=f"{active_event['name']} - LIMITED STORE! ⏰",
                description=f"**{active_event['description']}**\n\n"
                           f"⏰ **Event ends {events_cog.format_time_remaining(active_event['end_time'])}**\n"
                           f"🔄 Regular store refreshes {refresh_timestamp}",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="osugacha! Crate Store",
                description=f"**Global Inventory** • Refreshes {refresh_timestamp}",
                color=discord.Color.gold()
            )
        
        # Player's current balance
        embed.add_field(
            name="Your Balance",
            value=f"**{user_data['currency']:,} coins**",
            inline=False
        )
        
        # Add event store items if active
        if active_event and 'store_items' in active_event['definition']:
            event_items_text = ""
            for item in active_event['definition']['store_items']:
                # Get user's event purchase data
                event_purchases = user_data.get('event_purchases', {})
                event_id = active_event['id']
                user_event_data = event_purchases.get(event_id, {})
                purchased_amount = user_event_data.get(item['name'], 0)
                remaining = item['max_per_user'] - purchased_amount
                
                can_afford = user_data['currency'] >= item['price'] and remaining > 0
                status_emoji = "✅" if can_afford else "❌" if remaining > 0 else "🚫"
                
                # Format price nicely
                if item['price'] >= 1000000:
                    price_text = f"{item['price'] // 1000000}M"
                elif item['price'] >= 1000:
                    price_text = f"{item['price'] // 1000}K"
                else:
                    price_text = str(item['price'])
                
                event_items_text += f"**{item['name']}** {item['emoji']}\n"
                event_items_text += f"💰 **{price_text}** coins\n"
                event_items_text += f"📦 **{remaining}**/{item['max_per_user']} left {status_emoji}\n\n"
            
            embed.add_field(
                name="🌟 LIMITED EVENT STORE",
                value=event_items_text,
                inline=False
            )
        
        # Create clean layout - show crates in order of rarity
        crate_types = ["copper", "tin", "common", "uncommon", "rare", "epic", "legendary"]
        
        # Row 1: Copper + Tin (if they exist)
        row1_text = ""
        for crate_type in crate_types[:2]:
            if crate_type not in self.gacha_system.crate_config:
                continue
                
            crate_info = self.gacha_system.crate_config[crate_type]
            individual_amount = individual_stock.get(crate_type, 0)
            global_amount = global_inventory.get(crate_type, 0)
            description = STORE_DESCRIPTIONS.get(crate_type, "A standard crate.")
            
            # Check if user can afford it and has stock
            user_balance = user_data['currency']
            
            # Special handling for copper (cardboard box) dynamic pricing
            if crate_type == "copper":
                user_crates = user_data.get('crates', {})
                total_crates = sum(user_crates.values())
                user_cards = user_data.get('cards', {})
                total_cards = len(user_cards)
                opening_cooldown = self.gacha_system.check_cooldown(user_id)  # ✅ NEW
                
                # Check if user needs dynamic pricing AND has no crates AND no cards AND no opening cooldown
                if user_balance < 500 and total_crates == 0 and total_cards == 0 and opening_cooldown == 0:
                    # Show dynamic pricing
                    cardboard_price = max(0, user_balance)
                    can_afford = individual_amount > 0
                    
                    if can_afford:
                        status_emoji = "✅"
                    else:
                        status_emoji = ""
                    
                    # Show individual/global stock
                    if individual_amount > 0:
                        stock_text = f"Your Stock: **{individual_amount}**/{global_amount}"
                    else:
                        stock_text = f"Out of Stock (Global: {global_amount})"
                    
                    if cardboard_price == 0:
                        price_text = "**FREE** (Emergency!)"
                    else:
                        price_text = f"**{cardboard_price:,} coins (ALL YOUR COINS!)**"
                    
                    row1_text += f"**{crate_info['name']}** {crate_info['emoji']}\n"
                    row1_text += f"*Emergency option - uses all remaining coins*\n"
                    row1_text += f"{price_text}\n{stock_text} {status_emoji}\n\n"
                else:
                    # Show normal pricing (either they have 500+ coins OR have existing crates OR have cards)
                    crate_price = crate_info['price']
                    can_afford = user_balance >= crate_price and individual_amount > 0
                    
                    if can_afford:
                        status_emoji = "✅"
                    else:
                        status_emoji = ""
                    
                    # Show individual/global stock
                    if individual_amount > 0:
                        stock_text = f"Your Stock: **{individual_amount}**/{global_amount}"
                    else:
                        stock_text = f"Out of Stock (Global: {global_amount})"
                    
                    row1_text += f"**{crate_info['name']}** {crate_info['emoji']}\n"
                    row1_text += f"{description}\n"
                    row1_text += f"**{crate_info['price']:,}**:- coins\n{stock_text} {status_emoji}\n\n"
                    
                    # ✅ UPDATED: Show helpful message for different scenarios
                    if user_balance < 500:
                        if opening_cooldown > 0:
                            row1_text += f"*Emergency pricing blocked: {opening_cooldown:.1f}s cooldown*\n\n"
                        elif total_cards > 0:
                            row1_text += f"*You have {total_cards} cards - sell some for regular pricing!*\n\n"
                        elif total_crates > 0:
                            row1_text += f"*You have {total_crates} crates to open first!*\n\n"
            else:
                # Regular crate handling for tin
                crate_price = crate_info['price']
                can_afford = user_balance >= crate_price and individual_amount > 0
                
                if can_afford:
                    status_emoji = "✅"
                else:
                    status_emoji = ""
                
                # Show individual/global stock
                if individual_amount > 0:
                    stock_text = f"Your Stock: **{individual_amount}**/{global_amount}"
                else:
                    stock_text = f"Out of Stock (Global: {global_amount})"
                
                row1_text += f"**{crate_info['name']}** {crate_info['emoji']}\n"
                row1_text += f"{description}\n"
                row1_text += f"**{crate_info['price']:,}**:- coins\n{stock_text} {status_emoji}\n\n"
        
        if row1_text:
            embed.add_field(
                name="",
                value=row1_text,
                inline=True
            )
        
        # Row 2: Bronze + Silver (common + uncommon)
        row2_text = ""
        for crate_type in ["common", "uncommon"]:
            if crate_type not in self.gacha_system.crate_config:
                continue
                
            crate_info = self.gacha_system.crate_config[crate_type]
            individual_amount = individual_stock.get(crate_type, 0)
            global_amount = global_inventory.get(crate_type, 0)
            description = STORE_DESCRIPTIONS.get(crate_type, "A standard crate.")
            
            # Check if user can afford it and has stock
            user_balance = user_data['currency']
            crate_price = crate_info['price']
            can_afford = user_balance >= crate_price and individual_amount > 0
            
            if can_afford:
                status_emoji = "✅"
            else:
                status_emoji = ""
            
            # Show individual/global stock
            if individual_amount > 0:
                stock_text = f"Your Stock: **{individual_amount}**/{global_amount}"
            else:
                stock_text = f"Out of Stock (Global: {global_amount})"
            
            row2_text += f"**{crate_info['name']}** {crate_info['emoji']}\n"
            row2_text += f"{description}\n"
            row2_text += f"**{crate_info['price']:,}**:- coins\n{stock_text} {status_emoji}\n\n"
        
        if row2_text:
            embed.add_field(
                name="",
                value=row2_text,
                inline=True
            )
        
        # Row 3: Gold + Diamond (rare + epic)
        row3_text = ""
        for crate_type in ["rare", "epic"]:
            if crate_type not in self.gacha_system.crate_config:
                continue
                
            crate_info = self.gacha_system.crate_config[crate_type]
            individual_amount = individual_stock.get(crate_type, 0)
            global_amount = global_inventory.get(crate_type, 0)
            description = STORE_DESCRIPTIONS.get(crate_type, "A premium crate.")
            
            # Check if user can afford it and has stock
            user_balance = user_data['currency']
            crate_price = crate_info['price']
            can_afford = user_balance >= crate_price and individual_amount > 0
            
            if can_afford:
                status_emoji = "✅"
            else:
                status_emoji = ""
            
            # Show individual/global stock
            if individual_amount > 0:
                stock_text = f"Your Stock: **{individual_amount}**/{global_amount}"
            else:
                stock_text = f"Out of Stock (Global: {global_amount})"
            
            row3_text += f"**{crate_info['name']}** {crate_info['emoji']}\n"
            row3_text += f"{description}\n"
            row3_text += f"**{crate_info['price']:,}**:- coins\n{stock_text} {status_emoji}\n\n"
        
        if row3_text:
            embed.add_field(
                name="",
                value=row3_text,
                inline=True
            )
        
        # Rainbow crate (special section)
        if "legendary" in self.gacha_system.crate_config:
            legendary_info = self.gacha_system.crate_config["legendary"]
            individual_amount = individual_stock.get("legendary", 0)
            global_amount = global_inventory.get("legendary", 0)
            legendary_description = STORE_DESCRIPTIONS.get("legendary", "The ultimate crate containing the best players!")
            
            # Check if user can afford it
            user_balance = user_data['currency']
            crate_price = legendary_info['price']
            can_afford = user_balance >= crate_price and individual_amount > 0
            
            if can_afford:
                legendary_emoji = "✅"
            else:
                legendary_emoji = ""
            
            # Show individual/global stock
            if individual_amount > 0:
                legendary_stock_text = f"Your Stock: **{individual_amount}**/{global_amount}"
            else:
                legendary_stock_text = f"Out of Stock (Global: {global_amount})"
            
            legendary_text = f"**{legendary_info['name']}** {legendary_info['emoji']}\n"
            legendary_text += f"{legendary_description}\n"
            legendary_text += f"**{legendary_info['price']:,}**:- coins\n{legendary_stock_text} {legendary_emoji}"
            
            embed.add_field(
                name="",
                value=legendary_text,
                inline=False
            )
        
        # Footer with instructions
        embed.set_footer(text=f"Use /osubuy <crate> <amount> to purchase • Global inventory resets every 10 minutes\nConfirmations: {'ON' if confirmations_enabled else 'OFF'} • Use /osutoggle to change")
        
        # Create view with event items if available
        view = None
        events_cog = self.bot.get_cog("OsuGachaEvents")
        if events_cog:
            active_event = events_cog.get_active_event()
            if active_event and 'store_items' in active_event.get('definition', {}):
                # Create a combined view with both regular crates and event items
                view = StoreWithEventsView(self, global_inventory, active_event, events_cog)
        
        if interaction:
            if view:
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed)
        else:
            if view:
                await ctx.send(embed=embed, view=view)
            else:
                await ctx.send(embed=embed)

    async def _buy_command(self, ctx, crate_type, amount, interaction=None):
        """Buy crates from the store with global stock validation"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)

            # Check user's confirmation preference
        confirmations_enabled = user_data.get("confirmations_enabled", True)

        # Handle copper with dynamic pricing
        if crate_type.lower() in ["copper", "card", "cardboard"]:
            user_balance = user_data['currency']
            user_crates = user_data.get('crates', {})
            total_crates = sum(user_crates.values())
            user_cards = user_data.get('cards', {})
            total_cards = len(user_cards)
            
            # ✅ NEW: Check if user is on opening cooldown (prevents crate opening abuse)
            opening_cooldown = self.gacha_system.check_cooldown(user_id)
            
            # Only allow emergency pricing if they're truly broke AND have no crates AND no cards AND not opening crates
            if user_balance < 500 and total_crates == 0 and total_cards == 0 and amount == 1 and opening_cooldown == 0:
                # Use dynamic pricing - they pay all their coins (can be 0 or negative)
                actual_cost = max(0, user_balance)
                
                # Show confirmation (no minimum coin check)
                embed = discord.Embed(
                    title="Confirm Emergency Purchase",
                    description=f"📦 **Cardboard Box** - {actual_cost:,} coins\n\n"
                            f"⚠️ **This will use ALL your remaining coins!**\n"
                            f"You'll get a lower-tier card but can continue playing.\n\n"
                            f"Confirm purchase?",
                    color=discord.Color.orange()
                )
                
                if actual_cost == 0:
                    # Special message for completely broke players
                    embed.description = (f"📦 **Cardboard Box** - FREE!\n\n"
                                        f"**Special offer for brokies!**\n"
                                        f"You'll get a card to continue playing.\n\n"
                                        f"Confirm purchase?")
                
                view = EmergencyPurchaseView(user_id, self, actual_cost)
                
                if interaction:
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                else:
                    await ctx.send(embed=embed, view=view)
                return
            
            # ✅ NEW: Block attempts to exploit emergency pricing - have cards
            elif user_balance < 500 and total_cards > 0:
                embed = discord.Embed(
                    title="Emergency Option Not Available",
                    description=f"You have {total_cards:,} cards in your collection!\n\n"
                            f"**Sell some cards first** to get regular pricing:\n"
                            f"• Use `/osucards` to see your collection\n"
                            f"• Use `/osusell [player]` to sell individual cards\n"
                            f"• Use `/osusellall [rarity]` to sell by star rating\n\n"
                            f"Emergency pricing is only for players with NO cards or crates.",
                    color=discord.Color.blue()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
            
            # ✅ UPDATED: Block attempts to exploit emergency pricing - have crates
            elif user_balance < 500 and total_crates > 0:
                embed = discord.Embed(
                    title="Emergency Option Not Available", 
                    description=f"You have {total_crates:,} crates to open first!\n\n"
                            f"📦 **Open your existing crates** before buying more:\n"
                            f"• Use `/osucrates` to see your crates\n"
                            f"• Use `/osuopen [crate] [amount]` to open them\n\n"
                            f"Emergency pricing is only for players with NO cards or crates.",
                    color=discord.Color.blue()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
            
            # ✅ SAME: Block attempts to buy multiple emergency crates
            elif user_balance < 500 and amount > 1:
                embed = discord.Embed(
                    title="Emergency Limit: 1 Crate Only",
                    description=f"You can only buy **1** emergency crate at a time when broke!\n\n"
                            f"💡 **Try:** `/osubuy copper 1`\n\n"
                            f"After opening it, you can earn more coins with `/osudaily`",
                    color=discord.Color.orange()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
            
            # ✅ NEW: Block emergency purchase if actively opening crates
            elif user_balance < 500 and opening_cooldown > 0:
                embed = discord.Embed(
                    title="Emergency Option Temporarily Unavailable",
                    description=f"You recently opened a crate and must wait **{opening_cooldown:.1f} seconds** before using emergency pricing.\n\n"
                            f"⏱️ **This prevents exploitation during crate opening.**\n"
                            f"Please wait for the cooldown to finish, then try again.",
                    color=discord.Color.orange()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
        
        # Validate amount
        if amount < 1 or amount > 50:
            embed = discord.Embed(
                title="Invalid Amount",
                description="You can buy 1-50 crates at once.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Resolve crate type
        resolved_crate = self.gacha_system.get_crate_alias(crate_type)
        if not resolved_crate:
            user_balance = user_data['currency']
            error_msg = f"Unknown crate type: `{crate_type}`. Use `/osustore` to see available crates."
            
            # Suggest cardboard box for poor players
            if user_balance < 500:
                error_msg += f"\n\n💡 **Low on coins?** Try: `/osubuy cardboard 1`\nCosts {user_balance:,} coins (all your remaining coins)"
            
            embed = discord.Embed(
                title="Invalid Crate Type",
                description=error_msg,
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Get crate info and cost
        crate_info = self.gacha_system.crate_config[resolved_crate]
        total_cost = crate_info["price"] * amount
        
        # Check if user has enough coins
        if user_data["currency"] < total_cost:
            embed = discord.Embed(
                title="Insufficient Coins",
                description=f"You need **{total_cost:,}** coins but only have **{user_data['currency']:,}** coins.\n\nUse `/osudaily` to earn more coins!",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Check global store stock
        store_data = self.generate_global_store_stock()
        global_inventory = store_data["global_inventory"]
        current_period = store_data["period"]
        individual_stock = self.get_user_remaining_stock(user_id, global_inventory, current_period)

        available_stock = individual_stock.get(resolved_crate, 0)

        # Check if crate is even available in global inventory
        if global_inventory.get(resolved_crate, 0) == 0:
            embed = discord.Embed(
                title="Crate Not Available",
                description=f"{crate_info['name']} is not available in the current store rotation.\n\nStore refreshes <t:{store_data['refresh_time']}:R>",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        if available_stock < amount:
            embed = discord.Embed(
                title="Insufficient Stock",
                description=f"You can only buy **{available_stock}** more {crate_info['name']} from your personal stock.\n\nStore refreshes <t:{store_data['refresh_time']}:R>",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        # NEW: Additional validation - prevent any purchase if user stock is 0
        if available_stock == 0:
            embed = discord.Embed(
                title="Sold Out",
                description=f"You have reached your purchase limit for {crate_info['name']}.\n\nStore refreshes <t:{store_data['refresh_time']}:R>",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Show confirmation for large purchases OR if user has confirmations enabled
        should_confirm = (
            confirmations_enabled and (amount > 5 or total_cost > 5000000)
        ) or total_cost > 5000000  # Always confirm for very large purchases (5M+)

        if should_confirm:
            embed = discord.Embed(
                title="Confirm Purchase",
                description=f"Buy **{amount}x {crate_info['name']}** for **{total_cost:,}** coins?",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Stock Check",
                value=f"Your remaining stock: {available_stock}/{global_inventory.get(resolved_crate, 0)}",
                inline=True
            )
            
            view = PurchaseConfirmationView(user_id, self, resolved_crate, amount, total_cost)
            
            if interaction:
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await ctx.send(embed=embed, view=view)
        else:
            # Execute purchase directly without confirmation
            if interaction:
                await interaction.response.defer()
                await self._execute_purchase(interaction, resolved_crate, amount, total_cost)
            else:
                await self._execute_purchase(ctx, resolved_crate, amount, total_cost)


    async def _execute_purchase(self, ctx_or_interaction, crate_type, amount, total_cost):
        """Execute the actual purchase with stock tracking - handles both ctx and interaction"""
        
        # Determine if we have ctx or interaction
        if hasattr(ctx_or_interaction, 'user'):
            # It's an interaction
            user_id = ctx_or_interaction.user.id
            is_interaction = True
        else:
            # It's a ctx
            user_id = ctx_or_interaction.author.id if hasattr(ctx_or_interaction, 'author') else ctx_or_interaction.user.id
            is_interaction = False
        
        user_data = self.get_user_gacha_data(user_id)
        
        # Double-check stock availability before executing
        store_data = self.generate_global_store_stock()
        global_inventory = store_data["global_inventory"]
        current_period = store_data["period"]
        individual_stock = self.get_user_remaining_stock(user_id, global_inventory, current_period)

        available_stock = individual_stock.get(crate_type, 0)

        # NEW: Check if global inventory exists
        if global_inventory.get(crate_type, 0) == 0:
            embed = discord.Embed(
                title="Purchase Failed",
                description="This crate is no longer available in the store.",
                color=discord.Color.red()
            )
            
            if is_interaction:
                await ctx_or_interaction.response.edit_message(embed=embed, view=None)
            elif hasattr(ctx_or_interaction, 'edit_original_response'):
                await ctx_or_interaction.edit_original_response(embed=embed, view=None)
            else:
                await ctx_or_interaction.send(embed=embed)
            return

        if available_stock < amount:
            embed = discord.Embed(
                title="Purchase Failed",
                description="Stock changed during purchase. Please try again.",
                color=discord.Color.red()
            )
            
            if is_interaction:
                await ctx_or_interaction.response.edit_message(embed=embed, view=None)
            elif hasattr(ctx_or_interaction, 'edit_original_response'):
                await ctx_or_interaction.edit_original_response(embed=embed, view=None)
            else:
                await ctx_or_interaction.send(embed=embed)
            return

        # NEW: Additional zero stock check
        if available_stock == 0:
            embed = discord.Embed(
                title="Purchase Failed",
                description="You have no remaining stock for this crate.",
                color=discord.Color.red()
            )
            
            if is_interaction:
                await ctx_or_interaction.response.edit_message(embed=embed, view=None)
            elif hasattr(ctx_or_interaction, 'edit_original_response'):
                await ctx_or_interaction.edit_original_response(embed=embed, view=None)
            else:
                await ctx_or_interaction.send(embed=embed)
            return
        
        # Check if user still has enough currency
        if user_data["currency"] < total_cost:
            embed = discord.Embed(
                title="Purchase Failed",
                description="Insufficient funds. Please check your balance.",
                color=discord.Color.red()
            )
            
            if is_interaction:
                await ctx_or_interaction.response.edit_message(embed=embed, view=None)
            elif hasattr(ctx_or_interaction, 'edit_original_response'):
                await ctx_or_interaction.edit_original_response(embed=embed, view=None)
            else:
                await ctx_or_interaction.send(embed=embed)
            return
        
        # Execute purchase
        user_data["currency"] -= total_cost
        user_data["crates"][crate_type] = user_data["crates"].get(crate_type, 0) + amount

        # Update user's achievement stats
        user_data["achievement_stats"]["crates_bought"] = user_data["achievement_stats"].get("crates_bought", 0) + 1

        # Update achievement stats (currency change)
        self.update_achievement_stats(user_data)
        
        # Update user's purchase history for stock tracking
        if "purchase_history" not in user_data:
            user_data["purchase_history"] = {}
        
        period_key = str(current_period)
        if period_key not in user_data["purchase_history"]:
            user_data["purchase_history"][period_key] = {}
        
        user_data["purchase_history"][period_key][crate_type] = \
            user_data["purchase_history"][period_key].get(crate_type, 0) + amount
        
        # Save data
        self.save_user_data()
        
        # Get updated stock
        updated_stock = individual_stock[crate_type] - amount
        crate_info = self.gacha_system.crate_config[crate_type]
        
        embed = discord.Embed(
            title="Purchase Successful!",
            description=f"Bought **{amount}x {crate_info['name']}** {crate_info['emoji']}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Transaction",
            value=f"**Cost:** {total_cost:,} coins\n**Remaining Balance:** {user_data['currency']:,} coins",
            inline=True
        )
        
        embed.add_field(
            name="Your Crates",
            value=f"**{crate_info['name']}:** {user_data['crates'][crate_type]:,}\n**Remaining Stock:** {updated_stock}",
            inline=True
        )
        
        embed.set_footer(text="Use /osuopen to open your new crates!")
        
        # Handle response based on type
        if is_interaction:
            await ctx_or_interaction.response.edit_message(embed=embed, view=None)
        elif hasattr(ctx_or_interaction, 'edit_original_response'):
            await ctx_or_interaction.edit_original_response(embed=embed, view=None)
        else:
            await ctx_or_interaction.send(embed=embed)

    async def _sell_command(self, ctx, player_name, interaction=None):
        """Sell a specific card - full implementation with favorites protection"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Check user's confirmation preference
        confirmations_enabled = user_data.get("confirmations_enabled", True)
        
        cards = user_data.get("cards", {})
        if not cards:
            embed = discord.Embed(
                title="No Cards",
                description="You don't have any cards to sell!\n\n💡 Use `/osuopen` to get cards first",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Handle special "all" command
        if player_name.lower() == "all":
            # Sell all non-favorited cards
            cards_to_sell = []
            for card_id, card_data in cards.items():
                # Check multiple favorite field names for compatibility
                is_favorite = (
                    card_data.get("is_favorite", False) or 
                    card_data.get("favorite", False) or
                    card_data.get("favourited", False)
                )
                if not is_favorite:
                    cards_to_sell.append((card_id, card_data))
            
            if not cards_to_sell:
                embed = discord.Embed(
                    title="No Cards to Sell",
                    description="All your cards are favorited and protected from selling!",
                    color=discord.Color.orange()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
            
            # Calculate total value
            total_value = sum(int(card_data["price"] * 0.9) for card_id, card_data in cards_to_sell)

            # Check if confirmations are enabled or if it's a high-value sale (always confirm for 5M+ coins)
            should_confirm = confirmations_enabled or total_value > 5000000
            
            if should_confirm:
                # Show confirmation for bulk sell all
                embed = discord.Embed(
                    title="Confirm Sell All Cards",
                    description=f"Sell ALL **{len(cards_to_sell)}** non-favorited cards for **{total_value:,}** coins?",
                    color=discord.Color.red()
                )
                
                embed.add_field(
                    name="⚠️ Warning",
                    value="This will sell ALL your non-favorited cards!\nThis action cannot be undone!",
                    inline=False
                )
                
                embed.set_footer(text="You will receive 90% of each card's value • Favorited cards are protected")
                
                view = BulkSellConfirmationView(user_id, self, cards_to_sell, total_value)
                
                if interaction:
                    await interaction.response.send_message(embed=embed, view=view)
                else:
                    await ctx.send(embed=embed, view=view)
            else:
                # Execute sell all directly without confirmation - FIX: Call the direct method
                await self._execute_sell_all_direct(ctx, cards_to_sell, total_value)
            return
        
        # Find matching cards by player name
        matching_cards = []
        favorited_cards = []  # NEW: Track favorited cards separately

        for card_id, card_data in cards.items():
            player = card_data["player_data"]
            if player_name.lower() in player["username"].lower():
                # Check multiple favorite field names for compatibility
                is_favorite = (
                    card_data.get("is_favorite", False) or 
                    card_data.get("favorite", False) or
                    card_data.get("favourited", False)
                )
                if is_favorite:
                    favorited_cards.append(player["username"])  # NEW: Track favorited matches
                else:
                    matching_cards.append((card_id, card_data))

        # NEW: If no sellable cards but there are favorited matches, show clear message
        if not matching_cards and favorited_cards:
            embed = discord.Embed(
                title="❤️ You can't sell favorited cards!",
                description=f"Found matching cards for `{player_name}`, but they are all protected from selling.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="Protected Cards",
                value="\n".join(f"❤️ {name}" for name in favorited_cards[:5]),
                inline=False
            )
            
            embed.add_field(
                name="How to sell them",
                value="Use `/osufavorite [player]` to remove them from favorites first, then try selling again.",
                inline=False
            )
            
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        if not matching_cards:
            # Original no cards found message for when there are truly no matches
            embed = discord.Embed(
                title="No Cards Found",
                description=f"No sellable cards found for: `{player_name}`\n\n**Possible reasons:**\n• No cards with that player name\n• All matching cards are favorited (protected)\n• Typo in player name",
                color=discord.Color.red()
            )
            
            # Show some suggestions
            all_players = []
            for card_data in cards.values():
                is_favorite = (
                    card_data.get("is_favorite", False) or 
                    card_data.get("favorite", False) or
                    card_data.get("favourited", False)
                )
                if not is_favorite:
                    all_players.append(card_data["player_data"]["username"])
            
            if all_players:
                suggestions = list(set(all_players))[:5]  # Remove duplicates, show 5
                embed.add_field(
                    name="💡 Available Players",
                    value="\n".join(f"• {player}" for player in suggestions),
                    inline=False
                )
            
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        if len(matching_cards) == 1:
            # Only one card found, show confirmation directly
            card_id, card_data = matching_cards[0]
            await self._show_sell_confirmation(ctx, card_id, card_data, interaction)
        else:
            # Multiple cards found, show selection menu
            embed = discord.Embed(
                title="Multiple Cards Found",
                description=f"Found **{len(matching_cards)}** cards matching `{player_name}`. Select which one to sell:",
                color=discord.Color.blue()
            )
            
            # Show preview of found cards
            card_list = []
            for i, (card_id, card_data) in enumerate(matching_cards[:10]):  # Show max 10
                player = card_data["player_data"]
                mutation_text = ""
                if card_data.get("mutation"):
                    # Handle legacy mutations
                    if card_data["mutation"] in self.gacha_system.mutations:
                        mutation_name = self.gacha_system.mutations[card_data["mutation"]]["name"]
                        mutation_text = f" - {mutation_name.upper()}"
                    else:
                        # Legacy mutation handling
                        legacy_mutations = {
                            "rainbow": "RAINBOW (Legacy)",
                            "neon": "SHOCKED (Legacy)"
                        }
                        mutation_name = legacy_mutations.get(card_data["mutation"], card_data["mutation"].upper())
                        mutation_text = f" - {mutation_name}"
                
                card_text = f"`{i+1}.` {'⭐' * card_data['stars']} **{player['username']}**{mutation_text}\n"
                card_text += f"     Rank #{player['rank']:,} • {card_data['price']:,} coins"
                card_list.append(card_text)
            
            if len(matching_cards) > 10:
                card_list.append(f"... and {len(matching_cards) - 10} more cards")
            
            embed.add_field(
                name="Matching Cards",
                value="\n".join(card_list),
                inline=False
            )
            
            embed.set_footer(text="Use the buttons below to select a card to sell")
            
            view = CardSelectionView(user_id, self, player_name, matching_cards)
            
            if interaction:
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await ctx.send(embed=embed, view=view)

    async def _handle_card_sell(self, interaction, card_id, card_data):
        """Handle individual card sell from selection"""
        await self._show_sell_confirmation(interaction, card_id, card_data, interaction)

    async def _show_sell_confirmation(self, ctx, card_id, card_data, interaction=None):
        """Show sell confirmation for a specific card"""
        # Determine user_id from either ctx or interaction
        if hasattr(ctx, 'user'):
            # ctx is actually an interaction
            user_id = ctx.user.id
            actual_interaction = ctx
            ctx = None  # Clear ctx since we're using interaction
        elif hasattr(ctx, 'author'):
            # ctx is a real context
            user_id = ctx.author.id
            actual_interaction = interaction
        else:
            # fallback
            user_id = interaction.user.id if interaction else ctx.user.id
            actual_interaction = interaction
        
        user_data = self.get_user_gacha_data(user_id)
        player = card_data["player_data"]

        # Check if user has confirmations enabled
        confirmations_enabled = user_data.get("confirmations_enabled", True)
        
        # Double-check that card isn't favorited
        is_favorite = (
            card_data.get("is_favorite", False) or 
            card_data.get("favorite", False) or
            card_data.get("favourited", False)
        )
        
        if is_favorite:
            embed = discord.Embed(
                title="❤️ You can't sell favorited cards!",
                description=f"**{player['username']}** is protected from selling because it's in your favorites.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="How to sell this card",
                value=f"1. Use `/osufavorite {player['username']}` to remove from favorites\n2. Then use `/osusell {player['username']}` to sell it",
                inline=False
            )
            
            embed.add_field(
                name="Why cards are protected",
                value="Favorites prevent you from accidentally selling your best cards during bulk operations.",
                inline=False
            )
            
            embed.set_footer(text="💡 Tip: Only unfavorite cards you're sure you want to sell!")
            
            if actual_interaction:
                try:
                    await actual_interaction.response.edit_message(embed=embed, view=None)
                except discord.InteractionResponse:
                    await actual_interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return

        # Calculate sell price (90% of card value)
        sell_price = int(card_data["price"] * 0.9)
        
        # Always confirm for high-value cards (5M+ coins) or if confirmations enabled
        should_confirm = confirmations_enabled or sell_price > 5000000
        
        # Format mutation text with legacy support
        mutation_text = ""
        if card_data.get("mutation"):
            if card_data["mutation"] in self.gacha_system.mutations:
                mutation_name = self.gacha_system.mutations[card_data["mutation"]]["name"]
                mutation_text = f" - {mutation_name.upper()}"
            else:
                # Legacy mutation handling
                legacy_mutations = {
                    "rainbow": "RAINBOW (Legacy)",
                    "neon": "SHOCKED (Legacy)"
                }
                mutation_name = legacy_mutations.get(card_data["mutation"], card_data["mutation"].upper())
                mutation_text = f" - {mutation_name}"
        
        if should_confirm:
            embed = discord.Embed(
                title="Confirm Card Sale",
                description=f"Sell this card for **{sell_price:,}** coins?",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name=f"{'⭐' * card_data['stars']} {player['username']}{mutation_text}",
                value=f"**Rank:** #{player['rank']:,}\n**PP:** {player['pp']:,}\n**Country:** {player['country']}\n**Original Value:** {card_data['price']:,} coins",
                inline=False
            )
            
            embed.add_field(
                name="Sale Details",
                value=f"**You'll receive:** {sell_price:,} coins (90% of value)\n**Card will be:** Permanently removed",
                inline=False
            )
            
            embed.set_footer(text="⭐ Favorited cards are protected from selling")
            
            view = SellConfirmationView(user_id, self, card_id, card_data)
            
            if actual_interaction:
                try:
                    await actual_interaction.response.edit_message(embed=embed, view=view)
                except discord.InteractionResponse:
                    await actual_interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await ctx.send(embed=embed, view=view)
        else:
            # Execute sell directly without confirmation
            await self._execute_card_sell(ctx, card_id, card_data, actual_interaction)

    async def _execute_card_sell(self, ctx, card_id, card_data, interaction=None):
        """Execute the card sale with proper interaction handling"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id if hasattr(ctx, 'user') else interaction.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Check if card still exists (prevent KeyError)
        if card_id not in user_data.get("cards", {}):
            embed = discord.Embed(
                title="❌ Card Not Found",
                description="This card no longer exists in your collection. It may have been sold or traded already.",
                color=discord.Color.red()
            )
            
            if interaction:
                try:
                    await interaction.response.edit_message(embed=embed, view=None)
                except discord.InteractionResponse:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return
        
        # Double-check that card isn't favorited (safety check)
        current_card_data = user_data["cards"][card_id]
        is_favorite = (
            current_card_data.get("is_favorite", False) or 
            current_card_data.get("favorite", False) or
            current_card_data.get("favourited", False)
        )
        
        if is_favorite:
            embed = discord.Embed(
                title="❤️ Cannot Sell Favorited Card",
                description="This card is favorited and cannot be sold. Please unfavorite it first.",
                color=discord.Color.orange()
            )
            
            if interaction:
                try:
                    await interaction.response.edit_message(embed=embed, view=None)
                except discord.InteractionResponse:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return
        
        # Calculate sell price
        sell_price = int(card_data["price"] * 0.9)
        player = card_data["player_data"]
        
        # Remove card and add coins
        del user_data["cards"][card_id]
        user_data["currency"] = user_data.get("currency", 0) + sell_price
        
        # Save data
        self.save_user_data()
        
        # Create success embed
        mutation_text = ""
        if card_data.get("mutation"):
            if card_data["mutation"] in self.gacha_system.mutations:
                mutation_name = self.gacha_system.mutations[card_data["mutation"]]["name"]
                mutation_text = f" - {mutation_name.upper()}"
            else:
                # Legacy mutation handling
                legacy_mutations = {
                    "rainbow": "RAINBOW (Legacy)",
                    "neon": "SHOCKED (Legacy)"
                }
                mutation_name = legacy_mutations.get(card_data["mutation"], card_data["mutation"].upper())
                mutation_text = f" - {mutation_name}"
        
        embed = discord.Embed(
            title="💰 Card Sold Successfully!",
            description=f"**{'⭐' * card_data['stars']} {player['username']}{mutation_text}** sold for **{sell_price:,}** coins!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Transaction Details",
            value=f"**Received:** {sell_price:,} coins\n**New Balance:** {user_data['currency']:,} coins",
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: You can buy more crates with /osubuy")
        
        # Send response based on context type
        if interaction:
            try:
                await interaction.response.edit_message(embed=embed, view=None)
            except discord.InteractionResponse:
                await interaction.followup.send(embed=embed)
        else:
            await ctx.send(embed=embed)

    async def _sell_bulk_command(self, ctx, player_names, interaction=None):
        """Handle bulk selling of cards"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Check user's confirmation preference
        confirmations_enabled = user_data.get("confirmations_enabled", True)
        
        # Parse player names
        names = [name.strip() for name in player_names.split(",")]
        if len(names) > 20:
            embed = discord.Embed(
                title="Too Many Players",
                description="You can only sell cards for up to 20 players at once.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Find matching cards
        cards_to_sell = []
        total_value = 0
        favorited_found = []  # NEW: Track favorited cards found

        for name in names:
            found_favorited = False
            for card_id, card_data in user_data.get("cards", {}).items():
                player = card_data["player_data"]
                if name.lower() in player["username"].lower():
                    # Check multiple favorite field names for compatibility
                    is_favorite = (
                        card_data.get("is_favorite", False) or 
                        card_data.get("favorite", False) or
                        card_data.get("favourited", False)
                    )
                    if is_favorite:
                        favorited_found.append(player["username"])  # NEW: Track favorited
                        found_favorited = True
                    else:
                        cards_to_sell.append((card_id, card_data))
                        total_value += int(card_data["price"] * 0.9)
                        break  # Only sell one card per player name

        # NEW: If no sellable cards but found favorited ones
        if not cards_to_sell and favorited_found:
            embed = discord.Embed(
                title="❤️ You can't sell favorited cards!",
                description="All matching cards are protected from selling.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="Protected Cards",
                value="\n".join(f"❤️ {name}" for name in favorited_found[:10]),
                inline=False
            )
            
            embed.add_field(
                name="How to sell them",
                value="Use `/osufavorite [player]` to remove cards from favorites first.",
                inline=False
            )
            
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        if not cards_to_sell:
            # Original no cards found message
            embed = discord.Embed(
                title="No Cards Found",
                description="No sellable cards found for the specified players.\n\nNote: Favorited cards cannot be sold.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        # Check if confirmations are enabled or if it's a high-value sale (always confirm for 5M+ coins)
        should_confirm = confirmations_enabled or total_value > 5000000
        
        if should_confirm:
            # Show confirmation
            embed = discord.Embed(
                title="Confirm Bulk Sale",
                description=f"Sell **{len(cards_to_sell)}** cards for **{total_value:,}** coins?",
                color=discord.Color.orange()
            )
            
            # Show first few cards
            card_list = []
            for card_id, card_data in cards_to_sell[:5]:
                player = card_data["player_data"]
                mutation_text = ""
                if card_data["mutation"]:
                    mutation_name = self.gacha_system.mutations[card_data["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"
                card_list.append(f"{'⭐' * card_data['stars']} {player['username']}{mutation_text}")
            
            if len(cards_to_sell) > 5:
                card_list.append(f"... and {len(cards_to_sell) - 5} more")
            
            embed.add_field(
                name="Cards to Sell",
                value="\n".join(card_list),
                inline=False
            )
            
            embed.set_footer(text="You will receive 90% of each card's value")
            
            view = BulkSellConfirmationView(user_id, self, cards_to_sell, total_value)
            
            if interaction:
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await ctx.send(embed=embed, view=view)
        else:
            await self._execute_bulk_sell_direct(ctx, cards_to_sell, total_value)

    async def _execute_bulk_sell(self, interaction, cards_to_sell, total_value):
        """Execute the bulk sale with favorites protection"""
        user_id = interaction.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Remove cards and add coins (double-check favorites)
        cards_sold = 0
        actual_value = 0
        
        for card_id, card_data in cards_to_sell:
            if card_id in user_data.get("cards", {}):
                current_card = user_data["cards"][card_id]
                # Check multiple favorite field names
                is_favorite = (
                    current_card.get("is_favorite", False) or 
                    current_card.get("favorite", False) or
                    current_card.get("favourited", False)
                )
                
                if not is_favorite:
                    del user_data["cards"][card_id]
                    cards_sold += 1
                    actual_value += int(card_data["price"] * 0.9)
        
        user_data["currency"] = user_data.get("currency", 0) + actual_value
        

        # Update achievement stats (currency change)
        self.update_achievement_stats(user_data)

        # Save data
        self.save_user_data()
        
        # Success message
        embed = discord.Embed(
            title="Bulk Sale Successful!",
            description=f"Sold **{cards_sold}** cards for **{actual_value:,}** coins",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="New Balance",
            value=f"{user_data['currency']:,} coins",
            inline=True
        )
        
        if cards_sold != len(cards_to_sell):
            skipped = len(cards_to_sell) - cards_sold
            embed.add_field(
                name="⚠️ Protected Cards",
                value=f"{skipped} favorited cards were protected",
                inline=True
            )
        
        await interaction.response.edit_message(embed=embed, view=None)

    async def _execute_bulk_sell_direct(self, ctx, cards_to_sell, total_value):
        """Execute bulk sale directly for prefix commands"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Remove cards and add coins (double-check favorites)
        cards_sold = 0
        actual_value = 0
        
        for card_id, card_data in cards_to_sell:
            if card_id in user_data.get("cards", {}):
                current_card = user_data["cards"][card_id]
                # Check multiple favorite field names
                is_favorite = (
                    current_card.get("is_favorite", False) or 
                    current_card.get("favorite", False) or
                    current_card.get("favourited", False)
                )
                
                if not is_favorite:
                    del user_data["cards"][card_id]
                    cards_sold += 1
                    actual_value += int(card_data["price"] * 0.9)
        
        user_data["currency"] = user_data.get("currency", 0) + actual_value
        
        # Update achievement stats (currency change)
        self.update_achievement_stats(user_data)

        # Save data
        self.save_user_data()
        
        # Success message
        embed = discord.Embed(
            title="Bulk Sale Successful!",
            description=f"Sold **{cards_sold}** cards for **{actual_value:,}** coins",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="New Balance",
            value=f"{user_data['currency']:,} coins",
            inline=True
        )
        
        if cards_sold != len(cards_to_sell):
            skipped = len(cards_to_sell) - cards_sold
            embed.add_field(
                name="⚠️ Protected Cards",
                value=f"{skipped} favorited cards were protected",
                inline=True
            )
        
        await ctx.send(embed=embed)

    # Update the _sell_all_command method around line 1389-1420:
    async def _sell_all_command(self, ctx, rarity, confirm="yes", interaction=None):
        """Sell all cards of a specific rarity"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Check user's confirmation preference
        confirmations_enabled = user_data.get("confirmations_enabled", True)
        
        # Validate rarity
        try:
            rarity_int = int(rarity)
            if rarity_int < 1 or rarity_int > 6:
                raise ValueError
        except ValueError:
            embed = discord.Embed(
                title="Invalid Rarity",
                description="Rarity must be a number between 1-6.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Find matching cards
        cards_to_sell = []
        total_value = 0
        
        for card_id, card_data in user_data.get("cards", {}).items():
            if card_data["stars"] == rarity_int:
                # Check multiple favorite field names for compatibility
                is_favorite = (
                    card_data.get("is_favorite", False) or 
                    card_data.get("favorite", False) or
                    card_data.get("favourited", False)
                )
                if not is_favorite:
                    cards_to_sell.append((card_id, card_data))
                    total_value += int(card_data["price"] * 0.9)
        
        if not cards_to_sell:
            embed = discord.Embed(
                title="No Cards Found",
                description=f"No sellable {rarity_int}-star cards found.\n\nNote: Favorited cards cannot be sold.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Check if confirmations are enabled or if it's a high-value sale (always confirm for 5M+ coins)
        should_confirm = confirmations_enabled or total_value > 5000000

        if should_confirm:
            # Show confirmation
            embed = discord.Embed(
                title="Confirm Sell All",
                description=f"Sell ALL **{len(cards_to_sell)}** {rarity_int}-star cards for **{total_value:,}** coins?",
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="Warning",
                value="This action cannot be undone!",
                inline=False
            )
            
            embed.set_footer(text="You will receive 90% of each card's value")
            
            view = SellAllConfirmationView(user_id, self, rarity_int, cards_to_sell, total_value)
            
            if interaction:
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await ctx.send(embed=embed, view=view)
        else:
            await self._execute_sell_all_rarity_direct(ctx, rarity_int, cards_to_sell, total_value)

    async def _execute_sell_all_rarity_direct(self, ctx, rarity, cards_to_sell, total_value):
        """Execute sell all by rarity directly for prefix commands"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Remove cards and add coins
        cards_sold = 0
        for card_id, card_data in cards_to_sell:
            if card_id in user_data.get("cards", {}):
                current_card = user_data["cards"][card_id]
                # Check multiple favorite field names for compatibility
                is_favorite = (
                    current_card.get("is_favorite", False) or 
                    current_card.get("favorite", False) or
                    current_card.get("favourited", False)
                )
                if not is_favorite:
                    del user_data["cards"][card_id]
                    cards_sold += 1
        
        user_data["currency"] = user_data.get("currency", 0) + total_value
        
        # Save data
        self.save_user_data()
        
        # Success message
        embed = discord.Embed(
            title="Sell All Successful!",
            description=f"Sold all **{cards_sold}** {rarity}-star cards for **{total_value:,}** coins",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="New Balance",
            value=f"{user_data['currency']:,} coins",
            inline=True
        )
        
        await ctx.send(embed=embed)

    async def _execute_sell_all_direct(self, ctx, cards_to_sell, total_value):
        """Execute sell all operation directly for prefix commands"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Remove cards and add coins (double-check favorites)
        cards_sold = 0
        actual_value = 0
        
        for card_id, card_data in cards_to_sell:
            if card_id in user_data.get("cards", {}):
                current_card = user_data["cards"][card_id]
                # Check multiple favorite field names
                is_favorite = (
                    current_card.get("is_favorite", False) or 
                    current_card.get("favorite", False) or
                    current_card.get("favourited", False)
                )
                
                if not is_favorite:
                    del user_data["cards"][card_id]
                    cards_sold += 1
                    actual_value += int(card_data["price"] * 0.9)
        
        user_data["currency"] = user_data.get("currency", 0) + actual_value
        
        # Update achievement stats (currency change)
        self.update_achievement_stats(user_data)

        # Save data
        self.save_user_data()
        
        # Success message
        embed = discord.Embed(
            title="Sell All Successful!",
            description=f"Sold **{cards_sold}** cards for **{actual_value:,}** coins",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="New Balance",
            value=f"{user_data['currency']:,} coins",
            inline=True
        )
        
        if cards_sold != len(cards_to_sell):
            skipped = len(cards_to_sell) - cards_sold
            embed.add_field(
                name="⚠️ Protected Cards",
                value=f"{skipped} favorited cards were protected",
                inline=True
            )
        
        await ctx.send(embed=embed)


    async def _execute_sell_all(self, interaction, rarity, cards_to_sell, total_value):
        """Execute the sell all operation"""
        user_id = interaction.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Remove cards and add coins
        cards_sold = 0
        for card_id, card_data in cards_to_sell:
            if card_id in user_data.get("cards", {}):
                current_card = user_data["cards"][card_id]
                # Check multiple favorite field names for compatibility
                is_favorite = (
                    current_card.get("is_favorite", False) or 
                    current_card.get("favorite", False) or
                    current_card.get("favourited", False)
                )
                if not is_favorite:
                    del user_data["cards"][card_id]
                    cards_sold += 1
        
        user_data["currency"] = user_data.get("currency", 0) + total_value
        
        # Save data
        self.save_user_data()
        
        # Success message
        embed = discord.Embed(
            title="Sell All Successful!",
            description=f"Sold all **{cards_sold}** {rarity}-star cards for **{total_value:,}** coins",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="New Balance",
            value=f"{user_data['currency']:,} coins",
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

async def setup(bot):
    await bot.add_cog(OsuGachaStoreCog(bot))