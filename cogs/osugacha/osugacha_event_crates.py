import discord
from discord.ext import commands
from discord import app_commands
import random
import time
from typing import Dict, Any, List
from .osugacha_system import OsuGachaSystem

class OsuGachaEventCrates(commands.Cog):
    """Special event crate opening system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.gacha_system = bot.gacha_system if hasattr(bot, 'gacha_system') else OsuGachaSystem()
    
    def get_user_gacha_data(self, user_id):
        """Get user's gacha data"""
        user_id_str = str(user_id)
        if user_id_str not in self.bot.osu_gacha_data:
            self.bot.osu_gacha_data[user_id_str] = {
                "currency": 1000,
                "cards": {},
                "crates": {},
                "event_crates": {},
                "event_purchases": {},
                "daily_reset": 0
            }
        return self.bot.osu_gacha_data[user_id_str]
    
    def apply_event_effects(self, base_rarity_chances: Dict[str, float], event_item: Dict[str, Any]) -> Dict[str, float]:
        """Apply event-specific rarity boosts"""
        modified_chances = base_rarity_chances.copy()
        
        if 'rarity_boosts' in event_item:
            for rarity, boost_percent in event_item['rarity_boosts'].items():
                if rarity in modified_chances:
                    # Convert percentage to multiplier (15% = 0.15 increase)
                    multiplier = 1.0 + (boost_percent / 100.0)
                    modified_chances[rarity] *= multiplier
        
        # Normalize to ensure total is still 100%
        total = sum(modified_chances.values())
        if total > 0:
            for rarity in modified_chances:
                modified_chances[rarity] = (modified_chances[rarity] / total) * 100.0
        
        return modified_chances
    
    def get_event_special_cards(self, event_item: Dict[str, Any]) -> List[str]:
        """Get special cards for this event"""
        return event_item.get('special_cards', [])
    
    def open_event_crate(self, user_id: int, event_item: Dict[str, Any], active_event: Dict[str, Any]) -> Dict[str, Any]:
        """Open a single event crate with special effects"""
        
        # Get base rarity chances
        base_chances = {
            "common": 60.0,
            "uncommon": 25.0,
            "rare": 10.0,
            "epic": 4.0,
            "legendary": 1.0
        }
        
        # Apply event-specific boosts
        modified_chances = self.apply_event_effects(base_chances, event_item)
        
        # Apply global event effects if any
        if 'global_effects' in active_event['definition']:
            global_effects = active_event['definition']['global_effects']
            if 'all_crate_bonus' in global_effects:
                bonus = global_effects['all_crate_bonus']
                # Boost rare+ rarities
                for rarity in ['rare', 'epic', 'legendary']:
                    if rarity in modified_chances:
                        modified_chances[rarity] *= (1.0 + bonus)
        
        # Normalize again after global effects
        total = sum(modified_chances.values())
        if total > 0:
            for rarity in modified_chances:
                modified_chances[rarity] = (modified_chances[rarity] / total) * 100.0
        
        # Roll for rarity
        roll = random.uniform(0, 100)
        cumulative = 0
        selected_rarity = "common"
        
        for rarity, chance in modified_chances.items():
            cumulative += chance
            if roll <= cumulative:
                selected_rarity = rarity
                break
        
        # Check for special event cards
        special_cards = self.get_event_special_cards(event_item)
        is_special_card = False
        
        if special_cards and random.random() < 0.15:  # 15% chance for special card
            is_special_card = True
            card_name = random.choice(special_cards)
        else:
            # Get regular cards for this rarity
            rarity_cards = self.gacha_system.get_cards_by_rarity(selected_rarity)
            if not rarity_cards:
                rarity_cards = self.gacha_system.get_cards_by_rarity("common")
            
            card_name = random.choice(rarity_cards)
        
        # Check for special effects
        result = {
            'rarity': selected_rarity,
            'card_name': card_name,
            'is_special': is_special_card,
            'bonus_credits': 0,
            'extra_cards': []
        }
        
        # Apply special effects
        if 'special_effects' in event_item:
            effects = event_item['special_effects']
            
            # Bonus credits
            if 'bonus_credits' in effects:
                result['bonus_credits'] = effects['bonus_credits']
            
            # Duplicate chance
            if 'duplicate_chance' in effects:
                if random.random() < effects['duplicate_chance']:
                    result['extra_cards'].append({
                        'rarity': selected_rarity,
                        'card_name': card_name,
                        'is_special': is_special_card
                    })
            
            # Triple chance
            if 'triple_chance' in effects:
                if random.random() < effects['triple_chance']:
                    # Add 2 more cards
                    for _ in range(2):
                        extra_rarity_cards = self.gacha_system.get_cards_by_rarity(selected_rarity)
                        if extra_rarity_cards:
                            extra_card = random.choice(extra_rarity_cards)
                            result['extra_cards'].append({
                                'rarity': selected_rarity,
                                'card_name': extra_card,
                                'is_special': False
                            })
        
        return result
    
    @app_commands.command(name="osueventopen", description="Open event crates")
    @app_commands.describe(
        crate_name="Name of the event crate to open",
        amount="Amount to open (default: 1, max: 10)"
    )
    async def open_event_crate_command(self, interaction: discord.Interaction, crate_name: str, amount: int = 1):
        """Open event crates"""
        
        # Validate amount
        if amount < 1 or amount > 10:
            await interaction.response.send_message("❌ You can only open 1-10 crates at once!", ephemeral=True)
            return
        
        # Get user data
        user_id = interaction.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Check if user has event crates
        event_crates = user_data.get('event_crates', {})
        if crate_name not in event_crates or event_crates[crate_name] < amount:
            available = event_crates.get(crate_name, 0)
            await interaction.response.send_message(
                f"❌ You don't have enough {crate_name}! You have {available}, need {amount}.",
                ephemeral=True
            )
            return
        
        # Get current event to find the crate definition
        events_cog = self.bot.get_cog("OsuGachaEvents")
        if not events_cog:
            await interaction.response.send_message("❌ Events system not loaded!", ephemeral=True)
            return
        
        active_event = events_cog.get_active_event_for_guild(interaction.guild_id)
        if not active_event:
            await interaction.response.send_message("❌ No active event! Event crates can't be opened.", ephemeral=True)
            return
        
        # Find the crate definition
        event_item = None
        for item in active_event['definition'].get('store_items', []):
            if item['name'] == crate_name:
                event_item = item
                break
        
        if not event_item:
            await interaction.response.send_message("❌ Crate definition not found for current event!", ephemeral=True)
            return
        
        # Open crates
        results = []
        total_bonus_credits = 0
        
        for _ in range(amount):
            result = self.open_event_crate(user_id, event_item, active_event)
            results.append(result)
            
            # Add main card
            self.gacha_system.add_card_to_collection(user_data, result['card_name'], result['rarity'])
            
            # Add extra cards if any
            for extra_card in result['extra_cards']:
                self.gacha_system.add_card_to_collection(user_data, extra_card['card_name'], extra_card['rarity'])
            
            # Add bonus credits
            total_bonus_credits += result['bonus_credits']
        
        # Deduct crates and add credits
        event_crates[crate_name] -= amount
        user_data['currency'] += total_bonus_credits
        
        # Save data
        self.bot.pending_saves = True
        
        # Create result embed
        embed = discord.Embed(
            title=f"🎊 {crate_name} Results! {event_item['emoji']}",
            description=f"Opened **{amount}** {crate_name}(s) from **{active_event['name']}**!",
            color=discord.Color.purple()
        )
        
        # Group results by rarity for display
        rarity_counts = {}
        special_cards = []
        all_cards = []
        
        for result in results:
            # Main card
            rarity = result['rarity']
            if rarity not in rarity_counts:
                rarity_counts[rarity] = 0
            rarity_counts[rarity] += 1
            
            if result['is_special']:
                special_cards.append(f"✨ **{result['card_name']}** (Special!)")
            else:
                all_cards.append(f"**{result['card_name']}** ({rarity.title()})")
            
            # Extra cards
            for extra in result['extra_cards']:
                rarity = extra['rarity']
                rarity_counts[rarity] += 1
                if extra['is_special']:
                    special_cards.append(f"✨ **{extra['card_name']}** (Special Bonus!)")
                else:
                    all_cards.append(f"**{extra['card_name']}** ({rarity.title()} Bonus)")
        
        # Add rarity summary
        if rarity_counts:
            rarity_text = []
            rarity_emojis = {
                "common": "⚪",
                "uncommon": "🟢", 
                "rare": "🔵",
                "epic": "🟣",
                "legendary": "🟡"
            }
            
            for rarity, count in rarity_counts.items():
                emoji = rarity_emojis.get(rarity, "⚫")
                rarity_text.append(f"{emoji} {rarity.title()}: {count}")
            
            embed.add_field(
                name="📊 Rarity Summary",
                value="\n".join(rarity_text),
                inline=True
            )
        
        # Add special cards if any
        if special_cards:
            embed.add_field(
                name="🌟 Special Event Cards",
                value="\n".join(special_cards[:5]) + (f"\n...and {len(special_cards)-5} more!" if len(special_cards) > 5 else ""),
                inline=False
            )
        
        # Add regular cards (limited display)
        if all_cards:
            display_cards = all_cards[:8]
            cards_text = "\n".join(display_cards)
            if len(all_cards) > 8:
                cards_text += f"\n...and {len(all_cards)-8} more cards!"
            
            embed.add_field(
                name="🎴 Cards Obtained",
                value=cards_text,
                inline=False
            )
        
        # Add bonus info
        if total_bonus_credits > 0:
            embed.add_field(
                name="💰 Bonus Credits",
                value=f"+{total_bonus_credits:,} coins!",
                inline=True
            )
        
        remaining_crates = event_crates.get(crate_name, 0)
        embed.add_field(
            name="📦 Remaining Crates",
            value=f"{remaining_crates} {crate_name}(s)",
            inline=True
        )
        
        embed.set_footer(text=f"Balance: {user_data['currency']:,} coins")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(OsuGachaEventCrates(bot))
