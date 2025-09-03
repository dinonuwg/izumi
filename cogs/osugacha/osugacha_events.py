import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import time
from datetime import datetime, timezone, timedelta
import random
from typing import Dict, Any, Optional

class OsuGachaEvents(commands.Cog):
    """Special limited-time OSU Gacha events system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.events_file = 'data/osu_events.json'
        self.config_file = 'data/event_config.json'
        self.active_events = self.load_events()
        self.config = self.load_config()
        self.event_cleanup_task.start()
    
    def load_config(self) -> Dict[str, Any]:
        """Load event configuration"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Default configuration
            default_config = {
                "notification_roles": {}  # guild_id: role_id
            }
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config_data: Dict[str, Any] = None):
        """Save event configuration"""
        if config_data is None:
            config_data = self.config
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    def load_events(self) -> Dict[str, Any]:
        """Load active events from file"""
        try:
            with open(self.events_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_events(self):
        """Save active events to file"""
        with open(self.events_file, 'w') as f:
            json.dump(self.active_events, f, indent=2)
    
    def get_event_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Define all available events with realistic pricing based on your system"""
        return {
            "rainbow_rush": {
                "name": "🌈 Rainbow Rush",
                "description": "Limited Rainbow Crates available with boosted drop rates!",
                "duration_hours": 24,
                "store_items": [
                    {
                        "name": "Rainbow Crate",
                        "price": 5000000,  # Same as normal rainbow crate
                        "max_per_user": 50,
                        "emoji": "🌈",
                        "type": "legendary",  # Use existing system
                    }
                ]
            }
        }
    
    @tasks.loop(minutes=5)
    async def event_cleanup_task(self):
        """Clean up expired events"""
        current_time = time.time()
        expired_events = []
        
        for event_id, event_data in self.active_events.items():
            if current_time >= event_data['end_time']:
                expired_events.append(event_id)
        
        for event_id in expired_events:
            await self.end_event(event_id)
    
    async def end_event(self, event_id: str):
        """End an active event"""
        if event_id not in self.active_events:
            return
        
        event_data = self.active_events[event_id]
        
        # Send notification to the channel where event was started
        try:
            channel = self.bot.get_channel(event_data['channel_id'])
            if channel:
                embed = discord.Embed(
                    title="🔚 Event Ended!",
                    description=f"**{event_data['name']}** has ended!\n\nThanks for participating! 🎉",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                await channel.send(embed=embed)
        except Exception:
            pass
        
        # Remove event
        del self.active_events[event_id]
        self.save_events()
    
    def get_active_event_for_guild(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get active event for a guild"""
        for event_id, event_data in self.active_events.items():
            if event_data['guild_id'] == guild_id:
                return event_data
        return None
    
    def get_active_event(self, guild_id=None):
        """Get active event for a specific guild or any active event if no guild specified"""
        if guild_id:
            return self.get_active_event_for_guild(guild_id)
        else:
            # Return any active event (for backwards compatibility with store view)
            for event_id, event_data in self.active_events.items():
                return event_data  # Return first active event found
            return None
    
    def format_time_remaining(self, end_time: float) -> str:
        """Format remaining time nicely"""
        remaining = int(end_time - time.time())
        if remaining <= 0:
            return "Expired"
        
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    @app_commands.command(name="osuevent", description="Start a special OSU Gacha event (Owner only)")
    @app_commands.describe(
        event_type="The type of event to start",
        duration_override="Override duration in hours (optional)"
    )
    @app_commands.choices(event_type=[
        app_commands.Choice(name="🌈 Rainbow Rush", value="rainbow_rush"),
    ])
    async def start_event(self, interaction: discord.Interaction, event_type: str, duration_override: int = None):
        """Start a special gacha event"""
        # Check if user is bot owner (you'll need to replace this ID with your Discord ID)
        bot_owner_id = 959102594071007273  # REPLACE THIS WITH YOUR ACTUAL DISCORD USER ID
        
        if interaction.user.id != bot_owner_id:
            await interaction.response.send_message("❌ Only the bot owner can start events!", ephemeral=True)
            return
        
        # Check if there's already an active event in this guild
        existing_event = self.get_active_event_for_guild(interaction.guild_id)
        if existing_event:
            await interaction.response.send_message(
                f"❌ Event **{existing_event['name']}** is already active in this server!\n"
                f"Ends in: {self.format_time_remaining(existing_event['end_time'])}",
                ephemeral=True
            )
            return
        
        # Get event definition
        event_definitions = self.get_event_definitions()
        if event_type not in event_definitions:
            await interaction.response.send_message("❌ Invalid event type!", ephemeral=True)
            return
        
        event_def = event_definitions[event_type]
        
        # Calculate duration
        duration_hours = duration_override if duration_override else event_def['duration_hours']
        end_time = time.time() + (duration_hours * 3600)
        
        # Create event data
        event_id = f"{interaction.guild_id}_{event_type}_{int(time.time())}"
        event_data = {
            'id': event_id,
            'type': event_type,
            'name': event_def['name'],
            'description': event_def['description'],
            'guild_id': interaction.guild_id,
            'channel_id': interaction.channel_id,
            'start_time': time.time(),
            'end_time': end_time,
            'duration_hours': duration_hours,
            'definition': event_def
        }
        
        # Save event
        self.active_events[event_id] = event_data
        self.save_events()
        
        # Create announcement embed
        embed = discord.Embed(
            title=f"🎉 {event_def['name']} Started!",
            description=event_def['description'],
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="⏰ Duration",
            value=f"{duration_hours} hours\n*(Ends {discord.utils.format_dt(datetime.fromtimestamp(end_time), 'R')})*",
            inline=True
        )
        
        # Add store items info
        if 'store_items' in event_def:
            store_info = []
            for item in event_def['store_items']:
                store_info.append(
                    f"{item['emoji']} **{item['name']}**\n"
                    f"💰 {item['price']:,} credits\n"
                    f"📦 Max {item['max_per_user']} per person"
                )
            
            embed.add_field(
                name="🛒 Limited Store Items",
                value="\n\n".join(store_info),
                inline=False
            )
        
        # Add global effects info
        if 'global_effects' in event_def:
            effects = []
            for effect, value in event_def['global_effects'].items():
                if 'multiplier' in effect:
                    effects.append(f"• {effect.replace('_', ' ').title()}: **{value}x**")
                else:
                    effects.append(f"• {effect.replace('_', ' ').title()}: **+{int(value*100)}%**")
            
            embed.add_field(
                name="🌟 Global Effects",
                value="\n".join(effects),
                inline=False
            )
        
        embed.add_field(
            name="📍 How to Participate",
            value="Use `/osu store` to access the limited event store!\nAll effects are automatically applied!",
            inline=False
        )
        
        embed.set_footer(text=f"Event ID: {event_id}")
        
        # Get notification role for this guild
        guild_id = str(interaction.guild_id)
        notification_text = ""
        
        if guild_id in self.config["notification_roles"]:
            role_id = self.config["notification_roles"][guild_id]
            role = interaction.guild.get_role(role_id)
            if role:
                notification_text = f"{role.mention}"
            else:
                notification_text = "🎉"  # Fallback if role not found
        else:
            notification_text = "🎉"  # No role configured
        
        await interaction.response.send_message(notification_text, embed=embed)
    
    @app_commands.command(name="eventstatus", description="Check current event status")
    async def event_status(self, interaction: discord.Interaction):
        """Check current event status"""
        event_data = self.get_active_event_for_guild(interaction.guild_id)
        
        if not event_data:
            embed = discord.Embed(
                title="📅 No Active Events",
                description="There are currently no active events in this server.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        time_remaining = self.format_time_remaining(event_data['end_time'])
        
        embed = discord.Embed(
            title=f"🎪 {event_data['name']}",
            description=event_data['description'],
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="⏰ Time Remaining",
            value=time_remaining,
            inline=True
        )
        
        embed.add_field(
            name="📅 Started",
            value=discord.utils.format_dt(datetime.fromtimestamp(event_data['start_time']), 'R'),
            inline=True
        )
        
        embed.add_field(
            name="🔚 Ends",
            value=discord.utils.format_dt(datetime.fromtimestamp(event_data['end_time']), 'R'),
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="endevent", description="End current event early (Owner only)")
    async def end_event_command(self, interaction: discord.Interaction):
        """End current event early"""
        # Check if user is bot owner (same ID as above)
        bot_owner_id = 959102594071007273  # REPLACE THIS WITH YOUR ACTUAL DISCORD USER ID
        
        if interaction.user.id != bot_owner_id:
            await interaction.response.send_message("❌ Only the bot owner can end events!", ephemeral=True)
            return
        
        event_data = self.get_active_event_for_guild(interaction.guild_id)
        if not event_data:
            await interaction.response.send_message("❌ No active event to end!", ephemeral=True)
            return
        
        await self.end_event(event_data['id'])
        
        embed = discord.Embed(
            title="🔚 Event Ended",
            description=f"**{event_data['name']}** has been ended early by the bot owner.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_event_item_purchase(self, interaction: discord.Interaction, item_index: int):
        """Handle the purchase of an event item from buttons"""
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        
        # Get active event
        active_event = self.get_active_event_for_guild(guild_id)
        if not active_event:
            await interaction.response.send_message("❌ No active event found!", ephemeral=True)
            return
        
        # Check if item exists in event
        store_items = active_event.get('definition', {}).get('store_items', [])
        if item_index >= len(store_items) or item_index < 0:
            await interaction.response.send_message("❌ Event item not found!", ephemeral=True)
            return
        
        item_data = store_items[item_index]
        
        # Check if user has already purchased maximum amount of this item
        user_purchases = active_event.get('user_purchases', {})
        user_purchase_data = user_purchases.get(str(user_id), {})
        purchased_count = user_purchase_data.get(str(item_index), 0)
        
        if purchased_count >= item_data['max_per_user']:
            await interaction.response.send_message(
                f"❌ You've already purchased the maximum amount of **{item_data['name']}** ({item_data['max_per_user']})!",
                ephemeral=True
            )
            return
        
        # Get gacha system and user data
        store_cog = self.bot.get_cog("Osu Gacha Store")
        if not store_cog:
            await interaction.response.send_message("❌ Store system not available!", ephemeral=True)
            return
        
        user_data = store_cog.get_user_gacha_data(user_id)
        
        # Check if user can afford the item
        if user_data['currency'] < item_data['price']:
            await interaction.response.send_message(
                f"❌ Not enough coins! You need {item_data['price']:,} but have {user_data['currency']:,}.",
                ephemeral=True
            )
            return
        
        # Execute purchase
        user_data['currency'] -= item_data['price']
        
        # Add crates to regular inventory with special tracking
        if 'crates' not in user_data:
            user_data['crates'] = {}
        if 'event_crate_sources' not in user_data:
            user_data['event_crate_sources'] = {}
        
        # Map event items to regular crate types for seamless integration
        crate_type = item_data.get('type', 'legendary')  # Default to legendary
        user_data['crates'][crate_type] = user_data['crates'].get(crate_type, 0) + 1
        
        # Track which crates came from events for bonus application
        if crate_type not in user_data['event_crate_sources']:
            user_data['event_crate_sources'][crate_type] = []
        user_data['event_crate_sources'][crate_type].append({
            'event_id': active_event['id'],
            'item_index': item_index,
            'purchased_at': time.time()
        })
        
        # Update purchase tracking
        if 'user_purchases' not in active_event:
            active_event['user_purchases'] = {}
        if str(user_id) not in active_event['user_purchases']:
            active_event['user_purchases'][str(user_id)] = {}
        
        active_event['user_purchases'][str(user_id)][str(item_index)] = purchased_count + 1
        
        # Update global item stock tracking (reduce max_per_user for display)
        remaining_purchases = item_data['max_per_user'] - (purchased_count + 1)
        
        # Save data
        store_cog.save_user_data()
        self.save_events()
        
        # Create success embed
        embed = discord.Embed(
            title="⭐ Event Purchase Successful!",
            description=f"✅ **{item_data['name']}** purchased!\n\n"
                       f"**Cost:** {item_data['price']:,} coins\n"
                       f"**Your remaining purchases:** {remaining_purchases}/{item_data['max_per_user']}\n"
                       f"**New balance:** {user_data['currency']:,} coins",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📦 Crate Added",
            value=f"Added 1x {item_data['name']} (as {crate_type.title()} Crate)\nUse `/osuopen {crate_type} 1` to open it with event bonuses!",
            inline=False
        )
        
        embed.add_field(
            name="⭐ Event",
            value=f"{active_event['name']}\nEnds <t:{int(active_event['end_time'])}:R>",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _handle_event_item_bulk_purchase(self, interaction: discord.Interaction, item_index: int, quantity: int):
        """Handle bulk purchase of event items"""
        user_id = interaction.user.id
        guild_id = interaction.guild_id
        
        # Get active event
        active_event = self.get_active_event_for_guild(guild_id)
        if not active_event:
            await interaction.response.send_message("❌ No active event found!", ephemeral=True)
            return
        
        # Check if item exists in event
        store_items = active_event.get('definition', {}).get('store_items', [])
        if item_index >= len(store_items) or item_index < 0:
            await interaction.response.send_message("❌ Event item not found!", ephemeral=True)
            return
        
        item_data = store_items[item_index]
        
        # Check if user has already purchased maximum amount of this item
        user_purchases = active_event.get('user_purchases', {})
        user_purchase_data = user_purchases.get(str(user_id), {})
        purchased_count = user_purchase_data.get(str(item_index), 0)
        
        # Validate quantity
        available_purchases = item_data['max_per_user'] - purchased_count
        if quantity > available_purchases:
            await interaction.response.send_message(
                f"❌ You can only buy {available_purchases} more of **{item_data['name']}**!",
                ephemeral=True
            )
            return
        
        # Get gacha system and user data
        store_cog = self.bot.get_cog("Osu Gacha Store")
        if not store_cog:
            await interaction.response.send_message("❌ Store system not available!", ephemeral=True)
            return
        
        user_data = store_cog.get_user_gacha_data(user_id)
        
        # Calculate total cost
        total_cost = item_data['price'] * quantity
        
        # Check if user can afford the items
        if user_data['currency'] < total_cost:
            await interaction.response.send_message(
                f"❌ Not enough coins! You need {total_cost:,} but have {user_data['currency']:,}.",
                ephemeral=True
            )
            return
        
        # Execute bulk purchase
        user_data['currency'] -= total_cost
        
        # Add crates to regular inventory with special tracking
        if 'crates' not in user_data:
            user_data['crates'] = {}
        if 'event_crate_sources' not in user_data:
            user_data['event_crate_sources'] = {}
        
        # Map event items to regular crate types for seamless integration
        crate_type = item_data.get('type', 'legendary')  # Default to legendary
        user_data['crates'][crate_type] = user_data['crates'].get(crate_type, 0) + quantity
        
        # Track which crates came from events for bonus application
        if crate_type not in user_data['event_crate_sources']:
            user_data['event_crate_sources'][crate_type] = []
        
        # Add multiple entries for bulk purchase
        for _ in range(quantity):
            user_data['event_crate_sources'][crate_type].append({
                'event_id': active_event['id'],
                'item_index': item_index,
                'purchased_at': time.time()
            })
        
        # Update purchase tracking
        if 'user_purchases' not in active_event:
            active_event['user_purchases'] = {}
        if str(user_id) not in active_event['user_purchases']:
            active_event['user_purchases'][str(user_id)] = {}
        
        active_event['user_purchases'][str(user_id)][str(item_index)] = purchased_count + quantity
        
        # Calculate remaining purchases
        remaining_purchases = item_data['max_per_user'] - (purchased_count + quantity)
        
        # Save data
        store_cog.save_user_data()
        self.save_events()
        
        # Create success embed
        embed = discord.Embed(
            title="⭐ Bulk Event Purchase Successful!",
            description=f"✅ **{quantity}x {item_data['name']}** purchased!\n\n"
                       f"**Total Cost:** {total_cost:,} coins\n"
                       f"**Your remaining purchases:** {remaining_purchases}/{item_data['max_per_user']}\n"
                       f"**New balance:** {user_data['currency']:,} coins",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📦 Crates Added",
            value=f"Added {quantity}x {item_data['name']} (as {quantity}x {crate_type.title()} Crate{'s' if quantity > 1 else ''})\nUse `/osuopen {crate_type} {quantity}` to open them with event bonuses!",
            inline=False
        )
        
        embed.add_field(
            name="⭐ Event",
            value=f"{active_event['name']}\nEnds <t:{int(active_event['end_time'])}:R>",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="eventnotificationrole", description="Set the role to ping for event announcements")
    @app_commands.describe(role="The role to ping for event announcements (leave empty to remove)")
    async def set_notification_role(self, interaction: discord.Interaction, role: discord.Role = None):
        """Set the role to ping for event announcements"""
        
        # Check if user is bot owner or has admin permissions
        if interaction.user.id != self.bot.owner_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need to be the bot owner or have administrator permissions to use this command!", ephemeral=True)
            return
        
        guild_id = str(interaction.guild_id)
        
        if role is None:
            # Remove notification role
            if guild_id in self.config["notification_roles"]:
                del self.config["notification_roles"][guild_id]
                self.save_config()
                await interaction.response.send_message("✅ Event notification role removed. Events will not ping any role.", ephemeral=True)
            else:
                await interaction.response.send_message("ℹ️ No notification role was set.", ephemeral=True)
        else:
            # Set notification role
            self.config["notification_roles"][guild_id] = role.id
            self.save_config()
            await interaction.response.send_message(f"✅ Event notification role set to {role.mention}!", ephemeral=True)
    
    @app_commands.command(name="eventconfig", description="View current event configuration")
    async def view_event_config(self, interaction: discord.Interaction):
        """View current event configuration"""
        
        # Check if user is bot owner or has admin permissions
        if interaction.user.id != self.bot.owner_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need to be the bot owner or have administrator permissions to use this command!", ephemeral=True)
            return
        
        guild_id = str(interaction.guild_id)
        
        embed = discord.Embed(
            title="⚙️ Event Configuration",
            color=discord.Color.blue()
        )
        
        # Notification role
        if guild_id in self.config["notification_roles"]:
            role_id = self.config["notification_roles"][guild_id]
            role = interaction.guild.get_role(role_id)
            if role:
                embed.add_field(
                    name="🔔 Notification Role",
                    value=f"{role.mention} (ID: {role_id})",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🔔 Notification Role",
                    value=f"⚠️ Role not found (ID: {role_id})",
                    inline=False
                )
        else:
            embed.add_field(
                name="🔔 Notification Role",
                value="Not set (no pings will be sent)",
                inline=False
            )
        
        embed.set_footer(text="Use /eventnotificationrole to change the notification role")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(OsuGachaEvents(bot))
