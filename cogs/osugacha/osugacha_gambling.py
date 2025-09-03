import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import time
import math
from utils.helpers import *
from utils.config import *

# Import all the configuration
from .osugacha_config import *
from .osugacha_system import OsuGachaSystem

SLOT_SYMBOLS = {
    "🟫": {"name": "Wood", "weight": 35, "payout": 0.5},
    "🥉": {"name": "Bronze", "weight": 25, "payout": 1.0},
    "🥈": {"name": "Silver", "weight": 20, "payout": 2.0},
    "🥇": {"name": "Gold", "weight": 15, "payout": 4.0},
    "💎": {"name": "Diamond", "weight": 4, "payout": 10.0},
    "⭐": {"name": "Star", "weight": 1, "payout": 50.0}
}

SLOT_COMBINATIONS = {
    ("⭐", "⭐", "⭐"): {"multiplier": 500, "name": "MEGA JACKPOT!", "crate_reward": "legendary"},
    ("💎", "💎", "💎"): {"multiplier": 100, "name": "Diamond Jackpot!", "crate_reward": "epic"},
    ("🥇", "🥇", "🥇"): {"multiplier": 25, "name": "Gold Triple!", "crate_reward": "rare"},
    ("🥈", "🥈", "🥈"): {"multiplier": 10, "name": "Silver Triple!", "crate_reward": "uncommon"},
    ("🥉", "🥉", "🥉"): {"multiplier": 5, "name": "Bronze Triple!", "crate_reward": "common"},
    ("🟫", "🟫", "🟫"): {"multiplier": 2, "name": "Wood Triple", "crate_reward": None},
    
    # Two of a kind
    ("⭐", "⭐"): {"multiplier": 10, "name": "Star Pair!"},
    ("💎", "💎"): {"multiplier": 5, "name": "Diamond Pair!"},
    ("🥇", "🥇"): {"multiplier": 3, "name": "Gold Pair!"},
    ("🥈", "🥈"): {"multiplier": 2, "name": "Silver Pair!"},
    ("🥉", "🥉"): {"multiplier": 1.5, "name": "Bronze Pair"},
}

SCRATCH_CARD_TYPES = {
    "bronze": {
        "name": "Bronze Scratcher", "cost": 5000, "emoji": "🥉",
        "prizes": {
            "coins_small": {"weight": 40, "min": 1000, "max": 5000},
            "coins_medium": {"weight": 20, "min": 5000, "max": 15000},
            "common_crate": {"weight": 15, "reward": "common"},
            "uncommon_crate": {"weight": 10, "reward": "uncommon"},
            "rare_crate": {"weight": 5, "reward": "rare"},
            "nothing": {"weight": 50}
        }
    },
    "silver": {
        "name": "Silver Scratcher", "cost": 10000, "emoji": "🥈",
        "prizes": {
            "coins_medium": {"weight": 30, "min": 8000, "max": 20000},
            "coins_large": {"weight": 10, "min": 20000, "max": 50000},
            "rare_crate": {"weight": 10, "reward": "rare"},
            "epic_crate": {"weight": 1, "reward": "epic"},
            "legendary_crate": {"weight": 0.1, "reward": "legendary"},
            "multiple_crates": {"weight": 10, "reward": "multi"},
            "nothing": {"weight": 50}
        }
    },
    "gold": {
        "name": "Gold Scratcher", "cost": 50000, "emoji": "🥇",
        "prizes": {
            "coins_large": {"weight": 30, "min": 25000, "max": 50000},     # Reduced max
            "coins_jackpot": {"weight": 8, "min": 60000, "max": 120000},   # Reduced weight & max
            "epic_crate": {"weight": 5, "reward": "epic"},                # Same
            "legendary_crate": {"weight": 1, "reward": "legendary"},      # Reduced weight
            "mega_pack": {"weight": 6, "reward": "mega"},                  # Reduced weight
            "mystery_card": {"weight": 10, "reward": "mystery"},            # Same
            "nothing": {"weight": 50}    
        }
    }
}

class SecureGamblingView(discord.ui.View):
    """Base view with user security checks for gambling operations"""
    
    def __init__(self, user_id, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command user can interact with buttons"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You cannot interact with this gambling game.", 
                ephemeral=True
            )
            return False
        return True
    
class SlotMachineView(SecureGamblingView):
    """Persistent slot machine game view"""
    
    def __init__(self, user_data, bot, user_id, cog):
        super().__init__(user_id, timeout=600)  # 10 minute timeout
        self.user_data = user_data
        self.bot = bot
        self.cog = cog
        self.spinning = False
        
        # Current game state
        self.current_bet = 1000  # Default bet
        self.total_spins = 0
        self.session_profit = 0
        self.last_result = None
        
        # Bet amount options
        self.bet_options = [100, 500, 1000, 2500, 5000, 10000, 25000, 50000]
        self.current_bet_index = 2  # Start at 1000
        
        self._setup_buttons()
    
    def _setup_buttons(self):
        """Setup all buttons for the slot machine"""
        self.clear_items()
        
        # Row 1: Bet amount controls
        self.add_item(discord.ui.Button(
            label="- Bet",
            style=discord.ButtonStyle.secondary,
            custom_id="bet_down",
            row=0
        ))
        
        self.add_item(discord.ui.Button(
            label=f"💰 {self.current_bet:,}",
            style=discord.ButtonStyle.primary,
            custom_id="bet_display",
            disabled=True,
            row=0
        ))
        
        self.add_item(discord.ui.Button(
            label="+ Bet",
            style=discord.ButtonStyle.secondary,
            custom_id="bet_up",
            row=0
        ))
        
        # Row 2: Main action button
        self.add_item(discord.ui.Button(
            label="🎰 SPIN" if not self.spinning else "🎰 SPINNING...",
            style=discord.ButtonStyle.success if not self.spinning else discord.ButtonStyle.danger,
            custom_id="spin",
            disabled=self.spinning,
            row=1
        ))
        
        # Row 3: Utility buttons
        self.add_item(discord.ui.Button(
            label="📊 Stats",
            style=discord.ButtonStyle.secondary,
            custom_id="stats",
            row=2
        ))
        
        self.add_item(discord.ui.Button(
            label="❌ Quit",
            style=discord.ButtonStyle.danger,
            custom_id="quit",
            row=2
        ))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Security check and button handling"""
        if not await super().interaction_check(interaction):
            return False
        
        custom_id = interaction.data.get("custom_id")
        
        if custom_id == "bet_down":
            await self._handle_bet_change(interaction, -1)
        elif custom_id == "bet_up":
            await self._handle_bet_change(interaction, 1)
        elif custom_id == "spin":
            await self._handle_spin(interaction)
        elif custom_id == "stats":
            await self._show_session_stats(interaction)
        elif custom_id == "quit":
            await self._handle_quit(interaction)
        
        return True
    
    async def _handle_bet_change(self, interaction, direction):
        """Handle bet amount changes"""
        if self.spinning:
            await interaction.response.send_message("Can't change bet while spinning!", ephemeral=True)
            return
        
        # Update bet index
        new_index = self.current_bet_index + direction
        if 0 <= new_index < len(self.bet_options):
            self.current_bet_index = new_index
            self.current_bet = self.bet_options[self.current_bet_index]
            
            # Check if user can afford new bet
            if self.user_data["currency"] < self.current_bet:
                # Find highest affordable bet
                affordable_bets = [bet for bet in self.bet_options if bet <= self.user_data["currency"]]
                if affordable_bets:
                    self.current_bet = max(affordable_bets)
                    self.current_bet_index = self.bet_options.index(self.current_bet)
                else:
                    await interaction.response.send_message("You can't afford any bet amount!", ephemeral=True)
                    return
            
            self._setup_buttons()
            embed = self._create_main_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Can't change bet further in that direction!", ephemeral=True)
    
    async def _handle_spin(self, interaction):
        """Handle spin button press"""
        # Check if user can afford the bet
        if self.user_data["currency"] < self.current_bet:
            await interaction.response.send_message(
                f"You need {self.current_bet:,} coins but only have {self.user_data['currency']:,}!",
                ephemeral=True
            )
            return
        
        # Deduct bet
        self.user_data["currency"] -= self.current_bet
        self.spinning = True
        self._setup_buttons()
        
        # Update embed to show spinning state
        embed = self._create_spinning_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Animate the spin
        await self._animate_spin(interaction)
    
    async def _animate_spin(self, interaction):
        """Animate slot machine spinning"""
        symbols = list(SLOT_SYMBOLS.keys())
        final_result = self._generate_result()
        
        # Animation frames - shorter for continuous play
        animation_steps = [
            {"delay": 0.5, "status": "**SPINNING...**", "random": True},
            {"delay": 0.7, "status": "**SLOWING DOWN...**", "random": True},
            {"delay": 0.9, "status": "**RESULT!**", "random": False}
        ]
        
        for i, step in enumerate(animation_steps):
            if step["random"]:
                reels = [random.choice(symbols) for _ in range(3)]
            else:
                reels = final_result
            
            embed = self._create_spinning_embed(reels[0], reels[1], reels[2], step["status"])
            
            if i < len(animation_steps) - 1:
                await asyncio.sleep(step["delay"])
                await interaction.edit_original_response(embed=embed, view=self)
        
        # Process result and update
        await self._process_result(interaction, final_result[0], final_result[1], final_result[2])
    
    def _generate_result(self):
        """Generate weighted random slot result"""
        def get_symbol():
            total_weight = sum(symbol["weight"] for symbol in SLOT_SYMBOLS.values())
            rand = random.randint(1, total_weight)
            current = 0
            
            for symbol, data in SLOT_SYMBOLS.items():
                current += data["weight"]
                if rand <= current:
                    return symbol
            return "🟫"
        
        return get_symbol(), get_symbol(), get_symbol()
    
    async def _process_result(self, interaction, reel1, reel2, reel3):
        """Process slot result and update the persistent interface"""
        reels = [reel1, reel2, reel3]
        winnings = 0
        crate_reward = None
        combo_name = "No Match"
        
        # Check three of a kind
        if reel1 == reel2 == reel3:
            combo_key = (reel1, reel2, reel3)
            if combo_key in SLOT_COMBINATIONS:
                combo = SLOT_COMBINATIONS[combo_key]
                winnings = int(self.current_bet * combo["multiplier"])
                combo_name = combo["name"]
                crate_reward = combo.get("crate_reward")
        
        # Check two of a kind
        elif reel1 == reel2 or reel1 == reel3 or reel2 == reel3:
            if reel1 == reel2:
                pair_symbol = reel1
            elif reel1 == reel3:
                pair_symbol = reel1
            else:
                pair_symbol = reel2
            
            combo_key = (pair_symbol, pair_symbol)
            if combo_key in SLOT_COMBINATIONS:
                combo = SLOT_COMBINATIONS[combo_key]
                winnings = int(self.current_bet * combo["multiplier"])
                combo_name = combo["name"]
        
        # Update session stats
        self.total_spins += 1
        profit = winnings - self.current_bet
        self.session_profit += profit
        
        # Award winnings
        if winnings > 0:
            self.user_data["currency"] += winnings
        
        # Award bonus crate
        if crate_reward:
            if "crates" not in self.user_data:
                self.user_data["crates"] = {}
            self.user_data["crates"][crate_reward] = self.user_data["crates"].get(crate_reward, 0) + 1
        
        # Store last result for display
        self.last_result = {
            "reels": reels,
            "combo_name": combo_name,
            "winnings": winnings,
            "profit": profit,
            "crate_reward": crate_reward
        }
        
        # Update gambling stats
        won = winnings > self.current_bet
        self.cog._update_gambling_stats(self.user_data, "slots", won, self.current_bet, winnings)
        
        # Save data
        await self.cog.save_user_data()
        
        # Re-enable spinning and update display
        self.spinning = False
        self._setup_buttons()
        embed = self._create_main_embed()
        await interaction.edit_original_response(embed=embed, view=self)
    
    async def _show_session_stats(self, interaction):
        """Show session statistics"""
        embed = discord.Embed(
            title="Session Statistics",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Session Summary",
            value=f"**Total Spins:** {self.total_spins}\n"
                  f"**Session Profit:** {self.session_profit:+,} coins\n"
                  f"**Current Balance:** {self.user_data['currency']:,} coins",
            inline=False
        )
        
        if self.last_result:
            embed.add_field(
                name="Last Result",
                value=f"{' '.join(self.last_result['reels'])}\n"
                      f"**{self.last_result['combo_name']}**\n"
                      f"Profit: {self.last_result['profit']:+,} coins",
                inline=True
            )
        
        embed.add_field(
            name="Quick Stats",
            value=f"**Win Rate:** {(len([r for r in [self.last_result] if r and r['profit'] > 0]) / max(1, self.total_spins) * 100):.1f}%" if self.total_spins > 0 else "No spins yet",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _handle_quit(self, interaction):
        """Handle quit button"""
        embed = discord.Embed(
            title="Slot Machine Session Ended",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Final Session Stats",
            value=f"**Total Spins:** {self.total_spins}\n"
                  f"**Session Profit:** {self.session_profit:+,} coins\n"
                  f"**Final Balance:** {self.user_data['currency']:,} coins",
            inline=False
        )
        
        if self.session_profit > 0:
            embed.add_field(name="Result", value="🎉 **Profitable Session!**", inline=True)
        elif self.session_profit < 0:
            embed.add_field(name="Result", value="💸 **Lost Some Coins**", inline=True)
        else:
            embed.add_field(name="Result", value="📊 **Broke Even**", inline=True)
        
        embed.set_footer(text="Thanks for playing! Use /osugamble slots to play again.")
        await interaction.response.edit_message(embed=embed, view=None)
    
    def _create_main_embed(self):
        """Create the main slot machine interface embed"""
        embed = discord.Embed(
            title="Slot Machine",
            description="Set your bet and spin away! Results update in real-time.",
            color=discord.Color.gold()
        )
        
        # Show current reels or last result
        if self.last_result:
            reels_display = " │ ".join(self.last_result["reels"])
            embed.add_field(
                name="Last Spin Result",
                value=f"╭─────────────╮\n"
                      f"│  {reels_display}  │\n"
                      f"╰─────────────╯\n"
                      f"**{self.last_result['combo_name']}**",
                inline=False
            )
            
            # Show last result details
            result_color = "🟢" if self.last_result["profit"] > 0 else "🔴" if self.last_result["profit"] < 0 else "🟡"
            embed.add_field(
                name="Last Result",
                value=f"{result_color} **Profit:** {self.last_result['profit']:+,} coins\n"
                      f"💰 **Winnings:** {self.last_result['winnings']:,} coins",
                inline=True
            )
            
            if self.last_result.get("crate_reward"):
                crate_info = self.cog.gacha_system.crate_config[self.last_result["crate_reward"]]
                embed.add_field(
                    name="Bonus Prize!",
                    value=f"🎁 **{crate_info['name']} {crate_info['emoji']}**",
                    inline=True
                )
        else:
            embed.add_field(
                name="Ready to Spin!",
                value="╭─────────────╮\n"
                      "│  ?  │  ?  │  ?  │\n"
                      "╰─────────────╯\n"
                      "Press SPIN to start!",
                inline=False
            )
        
        # Current bet and balance info
        embed.add_field(
            name="💰 Current Bet",
            value=f"**{self.current_bet:,} coins**\n"
                  f"Balance: {self.user_data['currency']:,} coins",
            inline=True
        )
        
        # Session stats
        embed.add_field(
            name="📊 Session Stats",
            value=f"**Spins:** {self.total_spins}\n"
                  f"**Profit:** {self.session_profit:+,} coins",
            inline=True
        )
        
        # Payout info
        embed.add_field(
            name="🎯 Key Payouts",
            value="⭐⭐⭐ = 500x + Legendary\n"
                  "💎💎💎 = 100x + Epic\n"
                  "🥇🥇🥇 = 25x + Rare\n"
                  "Any Pair = 1.5x - 10x",
            inline=True
        )
        
        return embed
    
    def _create_spinning_embed(self, reel1="?", reel2="?", reel3="?", status="**SPINNING...**"):
        """Create embed during spinning animation - SAME SIZE as main embed"""
        embed = discord.Embed(
            title="Slot Machine",
            description="Set your bet and spin away! Results update in real-time.",
            color=discord.Color.orange()  # Different color to show spinning state
        )
        
        # Show spinning reels in SAME format as main embed
        embed.add_field(
            name=status,  # Use status instead of "Last Spin Result"
            value=f"╭─────────────╮\n"
                f"│  {reel1}  │  {reel2}  │  {reel3}  │\n"
                f"╰─────────────╯\n"
                f"**Spinning...**",  # Replace combo name with spinning text
            inline=False
        )
        
        # Keep SAME result section but with spinning text
        embed.add_field(
            name="Current Spin",  # Replace "Last Result"
            value="🎰 **Spinning:** In progress...\n"
                "💰 **Bet:** " + f"{self.current_bet:,} coins",
            inline=True
        )
        
        # Keep SAME bet info
        embed.add_field(
            name="💰 Current Bet",
            value=f"**{self.current_bet:,} coins**\n"
                f"Balance: {self.user_data['currency']:,} coins",
            inline=True
        )
        
        # Keep SAME session stats
        embed.add_field(
            name="📊 Session Stats",
            value=f"**Spins:** {self.total_spins}\n"
                f"**Profit:** {self.session_profit:+,} coins",
            inline=True
        )
        
        # Keep SAME payout info - this maintains embed height
        embed.add_field(
            name="🎯 Key Payouts",
            value="⭐⭐⭐ = 500x + Legendary\n"
                "💎💎💎 = 100x + Epic\n"
                "🥇🥇🥇 = 25x + Rare\n"
                "Any Pair = 1.5x - 10x",
            inline=True
        )
        
        return embed
    
class ScratchCardView(SecureGamblingView):
    """Scratch card game view"""
    
    def __init__(self, user_data, card_type, bot, user_id, cog):
        super().__init__(user_id)
        self.user_data = user_data
        self.card_type = card_type
        self.card_info = SCRATCH_CARD_TYPES[card_type]
        self.bot = bot
        self.cog = cog
        self.scratched_spots = set()
        self.prize = self._generate_prize()
        self.revealed = False
        
        # Create 3x3 grid of scratch spots
        for row in range(3):
            for col in range(3):
                spot_id = row * 3 + col
                button = discord.ui.Button(
                    label="❓",
                    style=discord.ButtonStyle.secondary,
                    row=row,
                    custom_id=f"scratch_{spot_id}"
                )
                button.callback = self.create_scratch_callback(spot_id)
                self.add_item(button)
    
    def _generate_prize(self):
        """Generate random prize"""
        prizes = self.card_info["prizes"]
        total_weight = sum(prize["weight"] for prize in prizes.values())
        rand = random.randint(1, total_weight)
        current = 0
        
        for prize_key, prize_data in prizes.items():
            current += prize_data["weight"]
            if rand <= current:
                return prize_key, prize_data
        
        return "nothing", prizes["nothing"]
    
    def create_scratch_callback(self, spot_id):
        async def callback(interaction: discord.Interaction):
            await self._scratch_spot(interaction, spot_id)
        return callback
    
    async def _scratch_spot(self, interaction, spot_id):
        """Scratch a spot"""
        if spot_id in self.scratched_spots:
            await interaction.response.send_message("Already scratched!", ephemeral=True)
            return
        
        self.scratched_spots.add(spot_id)
        button = self.children[spot_id]
        
        if len(self.scratched_spots) >= 5:
            # Reveal prize
            self.revealed = True
            prize_key, prize_data = self.prize
            
            if prize_key != "nothing":
                button.label = "🏆"
                button.style = discord.ButtonStyle.success
            else:
                button.label = "🍅"
                button.style = discord.ButtonStyle.danger
            
            # Disable all buttons
            for child in self.children:
                child.disabled = True
            
            await self._award_prize(interaction)
        else:
            # Show scratch symbol
            rand = random.random()
            if rand < 0.1:
                button.label = "💀"  # 10% chance
            elif rand < 0.2:
                button.label = "😭"  # 10% chance
            elif rand < 0.3:
                button.label = "😂"  # 10% chance
            elif rand < 0.4:
                button.label = "🥀"  # 10% chance
            elif rand < 0.5:
                button.label = "💔"  # 10% chance
            else:
                button.label = "❌"  # 50% chance
            button.disabled = True
        
        embed = self._create_card_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    def _create_card_embed(self):
        """Create scratch card embed"""
        embed = discord.Embed(
            title=f"{self.card_info['emoji']} {self.card_info['name']}",
            description="Scratch 5 spots to reveal your prize!\n"
                       f"**Scratched:** {len(self.scratched_spots)}/5" if not self.revealed else "🎉 **PRIZE REVEALED!** 🎉",
            color=discord.Color.gold() if self.revealed else discord.Color.blue()
        )
        
        if self.revealed:
            prize_key, prize_data = self.prize
            if prize_key == "nothing":
                embed.add_field(
                    name="😔 No Prize",
                    value="Better luck next time!",
                    inline=False
                )
            else:
                prize_text = self._format_prize_text(prize_key, prize_data)
                embed.add_field(
                    name="You Won!",
                    value=prize_text,
                    inline=False
                )
        
        return embed
    
    async def _generate_mystery_card(self):
        """Generate a mystery card with balanced rarity distribution"""
        try:
            # FIX: Use existing crate system instead of non-existent generate_card method
            # Gold crates have a good balanced distribution for mystery cards
            card_data = await self.cog.gacha_system.open_crate("rare")
            
            if not card_data:
                return None
            
            # Add special "mystery" indicator to card data
            card_data["source"] = "mystery_scratch"
            card_data["mystery_card"] = True
            
            return card_data
            
        except Exception as e:
            print(f"Error generating mystery card: {e}")
            return None
    
    def _format_prize_text(self, prize_key, prize_data):
        """Format prize text"""
        if "coins" in prize_key:
            amount = random.randint(prize_data["min"], prize_data["max"])
            return f"💰 **{amount:,} coins!**"
        elif prize_key.endswith("_crate"):
            crate_type = prize_data["reward"]
            crate_info = self.cog.gacha_system.crate_config[crate_type]
            return f"📦 **{crate_info['name']} {crate_info['emoji']}!**"
        elif prize_key == "multiple_crates":
            return f"🎁 **3 Random Crates!**"
        elif prize_key == "mega_pack":
            return f"🎁 **5 Random Crates!**"
        elif prize_key == "mystery_card":
            # Check if we have mystery card details to show
            if hasattr(self, 'mystery_card_details') and self.mystery_card_details:
                mystery_card = self.mystery_card_details
                player = mystery_card["player_data"]
                stars_display = "⭐" * mystery_card["stars"]
                mutation_text = ""
                if mystery_card.get("mutation"):
                    mutation_name = self.cog.gacha_system.mutations[mystery_card["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"
                
                return (f"**{stars_display} {player['username']}{mutation_text}**\n"
                    f"**Rank:** #{player['rank']:,}\n"
                    f"**PP:** {player['pp']:,}\n"
                    f"**Value:** {mystery_card['price']:,} coins\n"
                    f"**Country:** {player['country']}")
            else:
                return f"🎴 **Mystery Player Card!**"
        else:
            return "🎉 **Prize!**"
    
    async def _award_prize(self, interaction):
        """Award the prize"""
        prize_key, prize_data = self.prize
        
        if prize_key == "nothing":
            return
        
        # Award based on prize type
        if "coins" in prize_key:
            amount = random.randint(prize_data["min"], prize_data["max"])
            self.user_data["currency"] += amount
        
        elif prize_key.endswith("_crate"):
            crate_type = prize_data["reward"]
            if "crates" not in self.user_data:
                self.user_data["crates"] = {}
            self.user_data["crates"][crate_type] = self.user_data["crates"].get(crate_type, 0) + 1
        
        elif prize_key == "multiple_crates":
            crate_types = ["common", "uncommon", "rare"]
            for _ in range(3):
                crate_type = random.choice(crate_types)
                if "crates" not in self.user_data:
                    self.user_data["crates"] = {}
                self.user_data["crates"][crate_type] = self.user_data["crates"].get(crate_type, 0) + 1
        
        elif prize_key == "mega_pack":
            crate_types = ["uncommon", "rare", "epic", "legendary"]
            weights = [50, 40, 5, 1]
            for _ in range(5):
                crate_type = random.choices(crate_types, weights=weights)[0]
                if "crates" not in self.user_data:
                    self.user_data["crates"] = {}
                self.user_data["crates"][crate_type] = self.user_data["crates"].get(crate_type, 0) + 1

        # ADD MYSTERY CARD IMPLEMENTATION
        elif prize_key == "mystery_card":
            # Generate a mystery card similar to opening a crate
            mystery_card = await self._generate_mystery_card()
            if mystery_card:
                if "cards" not in self.user_data:
                    self.user_data["cards"] = {}
                
                # Add the card to user's collection
                card_id = mystery_card["card_id"]
                self.user_data["cards"][card_id] = mystery_card
                
                # Update the prize text in _format_prize_text instead of editing here
                self.mystery_card_details = mystery_card  # Store for display
        
        await self.cog.save_user_data()

class DiceTowerView(SecureGamblingView):
    """Dice tower climbing game"""
    
    def __init__(self, user_data, bet_value, is_card_bet, card_data, bot, user_id, cog, card_id=None):
        super().__init__(user_id)
        self.user_data = user_data
        self.bet_value = bet_value
        self.is_card_bet = is_card_bet
        self.card_data = card_data
        self.card_id = card_id
        self.bot = bot
        self.cog = cog
        self.current_floor = 1
        self.total_winnings = 0
        self.game_over = False
        
        # Floor multipliers and risks
        self.floors = {
            1: {"multiplier": 0.3, "risk": 0.1, "name": "Ground Floor"},
            2: {"multiplier": 0.6, "risk": 0.15, "name": "Second Floor"},
            3: {"multiplier": 0.9, "risk": 0.2, "name": "Third Floor"},
            4: {"multiplier": 1.2, "risk": 0.25, "name": "Fourth Floor"},
            5: {"multiplier": 1.5, "risk": 0.3, "name": "Fifth Floor"},
            6: {"multiplier": 2.5, "risk": 0.35, "name": "Sixth Floor"},
            7: {"multiplier": 4.0, "risk": 0.4, "name": "Seventh Floor"},
            8: {"multiplier": 6.0, "risk": 0.45, "name": "Eighth Floor"},
            9: {"multiplier": 10.0, "risk": 0.5, "name": "Ninth Floor"},
            10: {"multiplier": 20.0, "risk": 0.6, "name": "TOP FLOOR - PENTHOUSE!"}
        }
        
        # Add game buttons
        self.add_item(discord.ui.Button(
            label="🎲 Climb Higher",
            style=discord.ButtonStyle.primary,
            custom_id="climb"
        ))
        
        self.add_item(discord.ui.Button(
            label="💰 Cash Out",
            style=discord.ButtonStyle.success,
            custom_id="cashout"
        ))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Security check and button handling"""
        if not await super().interaction_check(interaction):
            return False
        
        if self.game_over:
            await interaction.response.send_message("Game is over!", ephemeral=True)
            return False
        
        custom_id = interaction.data.get("custom_id")
        
        if custom_id == "climb":
            await self._attempt_climb(interaction)
        elif custom_id == "cashout":
            await self._cash_out(interaction)
        
        return True
    
    async def _attempt_climb(self, interaction):
        """Attempt to climb higher"""
        if self.current_floor >= 10:
            await interaction.response.send_message("Already at top floor!", ephemeral=True)
            return
        
        next_floor = self.current_floor + 1
        floor_info = self.floors[next_floor]
        
        # Roll for success
        roll = random.random()
        risk = floor_info["risk"]
        
        if roll <= risk:
            # Failed - lose everything
            await self._tower_collapse(interaction)
        else:
            # Success - climb higher
            self.current_floor = next_floor
            self.total_winnings = int(self.bet_value * floor_info["multiplier"])
            
            if self.current_floor >= 10:
                # Reached penthouse
                await self._reach_penthouse(interaction)
            else:
                # Continue climbing
                embed = self._create_tower_embed()
                embed.add_field(
                    name="✅ Successful Climb!",
                    value=f"Climbed to **{floor_info['name']}**!\n"
                          f"💰 **Current Winnings:** {self.total_winnings:,} coins",
                    inline=False
                )
                await interaction.response.edit_message(embed=embed, view=self)
    
    async def _tower_collapse(self, interaction):
        """Handle tower collapse"""
        self.game_over = True
        self.total_winnings = 0
        
        embed = self._create_tower_embed()
        embed.add_field(
            name="💥 TOWER COLLAPSE!",
            value="The dice tower collapsed! You lost everything!",
            inline=False
        )
        embed.color = discord.Color.red()
        
        # Handle losses
        if not self.is_card_bet:
            embed.add_field(
                name="Total Loss",
                value=f"💸 **{self.bet_value:,} coins lost**",
                inline=True
            )
        else:
            # Remove card
            if self.card_id and self.card_id in self.user_data["cards"]:
                del self.user_data["cards"][self.card_id]
            
            player = self.card_data["player_data"]
            embed.add_field(
                name="Card Lost!",
                value=f"Your **{player['username']}** card is gone!",
                inline=True
            )
        
        # Update stats
        bet_value = self.bet_value if not self.is_card_bet else self.card_data['price']
        self.cog._update_gambling_stats(self.user_data, "tower", False, bet_value, 0)
        
        await self.cog.save_user_data()
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _reach_penthouse(self, interaction):
        """Handle reaching penthouse"""
        await self._award_winnings(interaction, "🏆 PENTHOUSE REACHED!")
    
    async def _cash_out(self, interaction):
        """Cash out current winnings"""
        if self.current_floor == 1:
            await interaction.response.send_message("Need to climb at least one floor to cash out!", ephemeral=True)
            return
        
        await self._award_winnings(interaction, "💰 Cashed Out!")
    
    async def _award_winnings(self, interaction, title):
        """Award final winnings"""
        self.game_over = True
        
        embed = self._create_tower_embed()
        embed.add_field(
            name=title,
            value=f"Successfully cashed out from **{self.floors[self.current_floor]['name']}**!",
            inline=False
        )
        embed.color = discord.Color.green()
        
        if not self.is_card_bet:
            # Coin betting - award winnings
            self.user_data["currency"] += self.total_winnings
            profit = self.total_winnings - self.bet_value
            
            embed.add_field(
                name="Final Results",
                value=f"**Winnings:** {self.total_winnings:,} coins\n"
                      f"**Profit:** {profit:,} coins\n"
                      f"**New Balance:** {self.user_data['currency']:,} coins",
                inline=False
            )
        else:
            # Card betting - keep card and award coins
            coins_awarded = self.total_winnings
            self.user_data["currency"] += coins_awarded
            
            player = self.card_data["player_data"]
            embed.add_field(
                name="Card Saved + Coins Won!",
                value=f"You keep your **{player['username']}** card!\n"
                      f"**Coins Won:** {coins_awarded:,}\n"
                      f"**New Balance:** {self.user_data['currency']:,} coins",
                inline=False
            )
        
        # Update stats
        bet_value = self.bet_value if not self.is_card_bet else self.card_data['price']
        self.cog._update_gambling_stats(self.user_data, "tower", True, bet_value, self.total_winnings)
        
        await self.cog.save_user_data()
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    def _create_tower_embed(self):
        """Create tower display embed"""
        embed = discord.Embed(
            title="🏗️ Dice Tower",
            description=f"**Current Floor:** {self.current_floor}/10\n"
                       f"**{self.floors[self.current_floor]['name']}**\n\n"
                       f"💰 **Current Winnings:** {self.total_winnings:,} coins",
            color=discord.Color.blue()
        )
        
        if self.is_card_bet:
            player = self.card_data["player_data"]
            embed.add_field(
                name="Card at Risk",
                value=f"**{player['username']}**\n"
                      f"Value: {self.card_data['price']:,} coins",
                inline=True
            )
        else:
            embed.add_field(
                name="Original Bet",
                value=f"{self.bet_value:,} coins",
                inline=True
            )
        
        # Show next floor info if not at top
        if self.current_floor < 10 and not self.game_over:
            next_floor = self.current_floor + 1
            next_info = self.floors[next_floor]
            potential_winnings = int(self.bet_value * next_info["multiplier"])
            
            embed.add_field(
                name="🎯 Next Floor",
                value=f"**{next_info['name']}**\n"
                      f"🎰 Potential: {potential_winnings:,} coins\n"
                      f"💀 Risk: {next_info['risk'] * 100:.0f}%",
                inline=True
            )
        
        return embed

class BlackjackView(SecureGamblingView):
    """Secure blackjack game view"""
    
    def __init__(self, user_data, bet_value, is_card_bet, card_data, bot, user_id, cog, card_id=None):
        super().__init__(user_id)
        self.user_data = user_data
        self.bet_value = bet_value
        self.is_card_bet = is_card_bet
        self.card_data = card_data
        self.card_id = card_id
        
        self.bot = bot
        self.cog = cog
        
        # Game state
        self.deck = self._create_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.game_over = False
        self.player_score = 0
        self.dealer_score = 0
        
        # Deal initial cards
        self._deal_initial_cards()
        
        # Add game buttons
        self.add_item(discord.ui.Button(
            label="Hit", 
            style=discord.ButtonStyle.primary,
            custom_id="hit"
        ))
        
        self.add_item(discord.ui.Button(
            label="Stand", 
            style=discord.ButtonStyle.secondary,
            custom_id="stand"
        ))
        
        if len(self.player_hand) == 2 and self._can_double_down():
            self.add_item(discord.ui.Button(
                label="Double Down", 
                style=discord.ButtonStyle.danger,
                custom_id="double"
            ))
    
    def _create_deck(self):
        """Create a standard 52-card deck"""
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        deck = []
        
        for suit in suits:
            for rank in ranks:
                value = 11 if rank == 'A' else min(10, int(rank) if rank.isdigit() else 10)
                deck.append({'rank': rank, 'suit': suit, 'value': value})
        
        random.shuffle(deck)
        return deck
    
    def _deal_card(self):
        """Deal one card from deck"""
        if not self.deck:
            self.deck = self._create_deck()
        return self.deck.pop()
    
    def _deal_initial_cards(self):
        """Deal initial 2 cards to player and dealer"""
        self.player_hand = [self._deal_card(), self._deal_card()]
        self.dealer_hand = [self._deal_card(), self._deal_card()]
        self._update_scores()
    
    def _calculate_hand_value(self, hand):
        """Calculate the value of a hand, handling aces properly"""
        total = 0
        aces = 0
        
        for card in hand:
            if card['rank'] == 'A':
                aces += 1
                total += 11
            else:
                total += card['value']
        
        # Adjust for aces
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        
        return total
    
    def _update_scores(self):
        """Update player and dealer scores"""
        self.player_score = self._calculate_hand_value(self.player_hand)
        self.dealer_score = self._calculate_hand_value(self.dealer_hand)
    
    def _can_double_down(self):
        """Check if player can double down"""
        return len(self.player_hand) == 2 and not self.is_card_bet
    
    def _format_hand(self, hand, hide_dealer_card=False):
        """Format hand display"""
        if hide_dealer_card and len(hand) > 1:
            # Hide dealer's second card
            cards = [f"{hand[0]['rank']}{hand[0]['suit']}", "🂠"]
            return " ".join(cards)
        else:
            cards = [f"{card['rank']}{card['suit']}" for card in hand]
            return " ".join(cards)
    
    def _is_blackjack(self, hand):
        """Check if hand is blackjack (21 with 2 cards)"""
        return len(hand) == 2 and self._calculate_hand_value(hand) == 21
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Security check and button handling"""
        if not await super().interaction_check(interaction):
            return False
        
        if self.game_over:
            await interaction.response.send_message("This game is already finished!", ephemeral=True)
            return False
        
        custom_id = interaction.data.get("custom_id")
        
        if custom_id == "hit":
            await self._handle_hit(interaction)
        elif custom_id == "stand":
            await self._handle_stand(interaction)
        elif custom_id == "double":
            await self._handle_double_down(interaction)
        
        return True
    
    async def _handle_hit(self, interaction):
        """Handle hit button"""
        # Deal card to player
        self.player_hand.append(self._deal_card())
        self._update_scores()
        
        # Check if player busted
        if self.player_score > 21:
            await self._end_game(interaction, "bust")
        elif self.player_score == 21:
            # Player hit 21 - instant win!
            await self._end_game(interaction, "player_21")
        else:
            # Remove double down button if it exists
            new_items = []
            for item in self.children:
                if item.custom_id != "double":
                    new_items.append(item)
            self.clear_items()
            for item in new_items:
                self.add_item(item)
            
            embed = self._create_game_embed(True)  # Still hide dealer card
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def _handle_stand(self, interaction):
        """Handle stand button"""
        await self._play_dealer_turn(interaction)
    
    async def _handle_double_down(self, interaction):
        """Handle double down button"""
        # Check if player has enough currency to double
        if not self.is_card_bet:
            if self.user_data["currency"] < self.bet_value:
                await interaction.response.send_message(
                    "You don't have enough coins to double down!", 
                    ephemeral=True
                )
                return
            
            # Double the bet
            self.user_data["currency"] -= self.bet_value
            self.bet_value *= 2
        
        # Deal one card and end turn
        self.player_hand.append(self._deal_card())
        self._update_scores()
        
        if self.player_score > 21:
            await self._end_game(interaction, "bust")
        elif self.player_score == 21:
            # Player hit 21 with double down - instant win!
            await self._end_game(interaction, "player_21")
        else:
            await self._play_dealer_turn(interaction)
    
    async def _play_dealer_turn(self, interaction):
        """Play dealer's turn automatically"""
        # Dealer hits on 16 and below, stands on 17 and above
        while self.dealer_score < 17:
            self.dealer_hand.append(self._deal_card())
            self._update_scores()
        
        # Determine winner
        if self.dealer_score > 21:
            result = "dealer_bust"
        elif self.dealer_score > self.player_score:
            result = "dealer_win"
        elif self.player_score > self.dealer_score:
            result = "player_win"
        else:
            result = "tie"
        
        # Check for blackjacks
        player_blackjack = self._is_blackjack(self.player_hand)
        dealer_blackjack = self._is_blackjack(self.dealer_hand)
        
        if player_blackjack and dealer_blackjack:
            result = "tie"
        elif player_blackjack:
            result = "blackjack"
        elif dealer_blackjack:
            result = "dealer_blackjack"
        
        await self._end_game(interaction, result)
    
    async def _end_game(self, interaction, result):
        """End the game and handle payouts"""
        self.game_over = True
        self.clear_items()
        
        # Calculate winnings
        winnings = 0
        result_text = ""
        result_color = discord.Color.red()
        
        if result == "bust":
            result_text = "**BUST!** You went over 21!"
            result_color = discord.Color.red()
        elif result == "dealer_bust":
            result_text = "**DEALER BUST!** You win!"
            winnings = self.bet_value * 2
            result_color = discord.Color.green()
        elif result == "blackjack":
            result_text = "**BLACKJACK!** Natural 21!"
            winnings = int(self.bet_value * 2.5)  # 3:2 payout
            result_color = discord.Color.gold()
        elif result == "player_21":
            result_text = "**21!** Perfect score wins!"
            winnings = int(self.bet_value * 2.5)
            result_color = discord.Color.green()
        elif result == "dealer_blackjack":
            result_text = "**DEALER BLACKJACK!** You lose!"
            result_color = discord.Color.red()
        elif result == "player_win":
            result_text = "**YOU WIN!** Your hand beats the dealer!"
            winnings = self.bet_value * 2
            result_color = discord.Color.green()
        elif result == "dealer_win":
            result_text = "**DEALER WINS!** Dealer's hand beats yours!"
            result_color = discord.Color.red()
        elif result == "tie":
            result_text = "**PUSH!** It's a tie!"
            winnings = self.bet_value  # Return bet
            result_color = discord.Color.blue()
        
        # Handle payouts
        if not self.is_card_bet:
            # Coin bet
            self.user_data["currency"] += winnings
            profit = winnings - self.bet_value
            
            embed = discord.Embed(
                title="Blackjack Result",
                description=result_text,
                color=result_color
            )
            
            embed.add_field(
                name="Final Hands",
                value=f"**Your Hand:** {self._format_hand(self.player_hand)} = {self.player_score}\n"
                      f"**Dealer Hand:** {self._format_hand(self.dealer_hand)} = {self.dealer_score}",
                inline=False
            )
            
            embed.add_field(
                name="Betting Results",
                value=f"**Bet:** {self.bet_value:,} coins\n"
                      f"**Winnings:** {winnings:,} coins\n"
                      f"**Profit:** {profit:,} coins\n"
                      f"**New Balance:** {self.user_data['currency']:,} coins",
                inline=False
            )
        else:
            # Card bet
            embed = discord.Embed(
                title="Blackjack Result",
                description=result_text,
                color=result_color
            )
            
            embed.add_field(
                name="Final Hands",
                value=f"**Your Hand:** {self._format_hand(self.player_hand)} = {self.player_score}\n"
                    f"**Dealer Hand:** {self._format_hand(self.dealer_hand)} = {self.dealer_score}",
                inline=False
            )
            
            if winnings > 0:
                # Player won - keep the card AND award coins equal to card value
                player = self.card_data["player_data"]
                mutation_text = ""
                if self.card_data["mutation"]:
                    mutation_name = self.cog.gacha_system.mutations[self.card_data["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"
                
                # Award coins equal to card value
                card_value = self.card_data['price']
                self.user_data["currency"] += card_value
                
                embed.add_field(
                    name="Card Saved + Coins Won!",
                    value=f"You keep your **{'⭐' * self.card_data['stars']} {player['username']}{mutation_text}** card!\n"
                        f"**Card Value:** {card_value:,} coins\n"
                        f"**Coins Awarded:** {card_value:,} coins\n"
                        f"**New Balance:** {self.user_data['currency']:,} coins",
                    inline=False
                )
            else:
                # Player lost - remove the card from collection using stored card_id
                player = self.card_data["player_data"]
                mutation_text = ""
                if self.card_data["mutation"]:
                    mutation_name = self.cog.gacha_system.mutations[self.card_data["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"
                
                # Remove the specific card using the stored card_id
                if self.card_id and self.card_id in self.user_data["cards"]:
                    del self.user_data["cards"][self.card_id]
                
                embed.add_field(
                    name="Card Lost!",
                    value=f"Your **{'⭐' * self.card_data['stars']} {player['username']}{mutation_text}** card is gone!\n"
                        f"Lost Value: {self.card_data['price']:,} coins",
                    inline=False
                )

        won = winnings > self.bet_value if not self.is_card_bet else winnings > 0
        bet_value = self.bet_value if not self.is_card_bet else self.card_data['price']
        self.cog._update_gambling_stats(self.user_data, "blackjack", won, bet_value, winnings)
        
        # Save user data
        await self.cog.save_user_data()
        
        embed.set_footer(text="Thanks for playing! Use /osugamble to play again.")
        await interaction.response.edit_message(embed=embed, view=self)
    
    def _create_game_embed(self, hide_dealer_card=True):
        """Create game state embed"""
        embed = discord.Embed(
            title="Blackjack Game",
            description="Get as close to 21 as possible without going over!",
            color=discord.Color.blue()
        )
        
        # Show hands
        dealer_score_text = "?" if hide_dealer_card else str(self.dealer_score)
        
        embed.add_field(
            name=f"Dealer Hand ({dealer_score_text})",
            value=self._format_hand(self.dealer_hand, hide_dealer_card),
            inline=False
        )
        
        embed.add_field(
            name=f"Your Hand ({self.player_score})",
            value=self._format_hand(self.player_hand),
            inline=False
        )
        
        # Show bet info
        if self.is_card_bet:
            player = self.card_data["player_data"]
            mutation_text = ""
            if self.card_data["mutation"]:
                mutation_name = self.cog.gacha_system.mutations[self.card_data["mutation"]]["name"]
                mutation_text = f" - {mutation_name.upper()}"
            
            embed.add_field(
                name="Card at Risk",
                value=f"**{'⭐' * self.card_data['stars']} {player['username']}{mutation_text}**\n"
                      f"Value: {self.card_data['price']:,} coins",
                inline=True
            )
        else:
            embed.add_field(
                name="Bet Amount",
                value=f"{self.bet_value:,} coins",
                inline=True
            )
        
        embed.add_field(
            name="Game Rules",
            value="• Hit: Take another card\n• Stand: Keep current hand\n• Double: Double bet, take 1 card\n• Dealer hits on 16, stands on 17+",
            inline=True
        )
        
        return embed

class CoinFlipView(SecureGamblingView):
    """Secure coin flip game view"""
    
    def __init__(self, user_data, bet_value, is_card_bet, card_data, bot, user_id, cog, card_id=None): # Added card_id
        super().__init__(user_id)
        self.user_data = user_data
        self.bet_value = bet_value # This is the stake (coin amount or card price)
        self.is_card_bet = is_card_bet
        self.card_data = card_data
        self.card_id = card_id # Store the card_id for removal on loss
        self.bot = bot
        self.cog = cog
        
        # Add choice buttons
        self.add_item(discord.ui.Button(
            label="Heads", 
            style=discord.ButtonStyle.primary,
            custom_id="heads"
        ))
        
        self.add_item(discord.ui.Button(
            label="Tails", 
            style=discord.ButtonStyle.secondary,
            custom_id="tails"
        ))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Security check and button handling"""
        if not await super().interaction_check(interaction):
            return False
        
        custom_id = interaction.data.get("custom_id")
        
        if custom_id in ["heads", "tails"]:
            await self._execute_coin_flip(interaction, custom_id)
        
        return True
    
    async def _execute_coin_flip(self, interaction, choice):
        """Execute the coin flip game"""
        try:
            result = random.choice(["heads", "tails"])
            won = (choice == result)
            
            embed = discord.Embed(
                title="Coin Flip Result",
                color=discord.Color.green() if won else discord.Color.red()
            )
            embed.add_field(
                name="The Flip",
                value=f"**Your Choice:** {choice.title()}\n"
                      f"**Result:** {result.title()}\n"
                      f"**Outcome:** {'YOU WIN!' if won else 'YOU LOSE!'}",
                inline=False
            )
            
            net_profit_for_display = 0
            gross_payout_for_stats = 0

            if not self.is_card_bet: # Coin betting
                if won:
                    gross_payout_value = self.bet_value * 2 # e.g., bet 100, payout 200
                    self.user_data["currency"] += gross_payout_value # Add gross payout to (balance - original bet)
                    net_profit_for_display = self.bet_value # Net gain is original bet
                    gross_payout_for_stats = gross_payout_value
                else:
                    # Currency already reduced by self.bet_value in _gamble_command
                    net_profit_for_display = -self.bet_value
                    gross_payout_for_stats = 0 # No payout
                
                embed.add_field(
                    name="Betting Results",
                    value=f"**Bet:** {self.bet_value:,} coins\n"
                          f"**Winnings:** {gross_payout_for_stats:,} coins\n" # Show gross payout
                          f"**Profit:** {net_profit_for_display:,} coins\n"
                          f"**New Balance:** {self.user_data['currency']:,} coins",
                    inline=False
                )
            else: # Card betting
                player = self.card_data["player_data"]
                mutation_text = ""
                if self.card_data["mutation"]:
                    mutation_name = self.cog.gacha_system.mutations[self.card_data["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"
                
                if won:
                    coins_awarded = self.card_data['price']
                    self.user_data["currency"] += coins_awarded
                    gross_payout_for_stats = coins_awarded # Coins won
                    # Card is kept (not removed initially, and not removed here)
                    embed.add_field(
                        name="Card Saved + Coins Won!",
                        value=f"You keep your **{'⭐' * self.card_data['stars']} {player['username']}{mutation_text}** card!\n"
                              f"**Card Value:** {self.card_data['price']:,} coins\n"
                              f"**Coins Awarded:** {coins_awarded:,} coins\n"
                              f"**New Balance:** {self.user_data['currency']:,} coins",
                        inline=False
                    )
                else:
                    gross_payout_for_stats = 0
                    if self.card_id and self.card_id in self.user_data["cards"]:
                        del self.user_data["cards"][self.card_id]
                    
                    embed.add_field(
                        name="Card Lost!",
                        value=f"Your **{'⭐' * self.card_data['stars']} {player['username']}{mutation_text}** card is gone!\n"
                              f"Lost Value: {self.card_data['price']:,} coins",
                        inline=False
                    )
            
            embed.add_field(
                name="Game Info",
                value=f"**Odds:** 50/50 (50%)\n**Coin Payout:** 2x bet\n**Card Mode:** Win card + value, or lose card",
                inline=False
            )

            stake_for_stats = self.bet_value # This is the original bet (coins or card price)
            self.cog._update_gambling_stats(self.user_data, "coinflip", won, stake_for_stats, gross_payout_for_stats)
            
            await self.cog.save_user_data()
            embed.set_footer(text="Thanks for playing! Use /osugamble to play again.")
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            print(f"Error in coin flip game: {e}")
            await self._handle_game_error(interaction, "Failed to complete coin flip game")
    
    async def _handle_game_error(self, interaction, reason="An error occurred"):
        """Handle unexpected errors during gambling"""
        embed = discord.Embed(
            title="Game Error",
            description=f"{reason}. Please try again.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class DiceView(SecureGamblingView):
    """Secure dice game view"""
    
    def __init__(self, user_data, bet_value, is_card_bet, card_data, bot, user_id, cog, card_id=None):  # Added card_id parameter
        super().__init__(user_id)
        self.user_data = user_data
        self.bet_value = bet_value
        self.is_card_bet = is_card_bet
        self.card_data = card_data
        self.card_id = card_id  # Store the card_id for removal on loss
        self.bot = bot
        self.cog = cog
        
        # Add dice buttons (1-6)
        for i in range(1, 7):
            self.add_item(discord.ui.Button(
                label=str(i),
                style=discord.ButtonStyle.primary,
                custom_id=f"dice_{i}"
            ))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Security check and button handling"""
        if not await super().interaction_check(interaction):
            return False
        
        custom_id = interaction.data.get("custom_id")
        
        if custom_id.startswith("dice_"):
            choice = int(custom_id.split("_")[1])
            await self._execute_dice_roll(interaction, choice)
        
        return True
    
    async def _execute_dice_roll(self, interaction, choice):
        """Execute the dice roll game"""
        try:
            # Roll the dice
            result = random.randint(1, 6)
            won = (choice == result)
            
            # Create result embed
            embed = discord.Embed(
                title="Dice Roll Result",
                color=discord.Color.green() if won else discord.Color.red()
            )
            
            embed.add_field(
                name="The Roll",
                value=f"**Your Guess:** {choice}\n"
                      f"**Result:** {result}\n"
                      f"**Outcome:** {'PERFECT GUESS!' if won else 'WRONG GUESS!'}",
                inline=False
            )
            
            # Handle rewards/losses (6x multiplier for exact guess)
            if not self.is_card_bet:
                # Coin betting
                if won:
                    winnings = self.bet_value * 6  # 6x payout for 1/6 chance
                    self.user_data["currency"] += winnings
                    profit = self.bet_value * 5
                else:
                    winnings = 0
                    profit = -self.bet_value
                
                embed.add_field(
                    name="Betting Results",
                    value=f"**Bet:** {self.bet_value:,} coins\n"
                          f"**Winnings:** {winnings:,} coins\n"
                          f"**Profit:** {profit:,} coins\n"
                          f"**New Balance:** {self.user_data['currency']:,} coins",
                    inline=False
                )
            else:
                # Card betting
                player = self.card_data["player_data"]
                mutation_text = ""
                if self.card_data["mutation"]:
                    mutation_name = self.cog.gacha_system.mutations[self.card_data["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"

                if won:
                    # ✅ FIX: Award 6x card value AND keep card (like coin betting gets 6x bet)
                    card_value = self.card_data['price']
                    payout = card_value * 5  # ✅ CHANGED: 5x multiplier for dice win
                    self.user_data["currency"] += payout
                    
                    embed.add_field(
                        name="Card Saved + MASSIVE Coins Won!",
                        value=f"You keep your **{'⭐' * self.card_data['stars']} {player['username']}{mutation_text}** card!\n"
                            f"**Card Value:** {card_value:,} coins\n"
                            f"**5x Profit:** {payout:,} coins\n"  # ✅ CHANGED: Show 5x profit
                            f"**New Balance:** {self.user_data['currency']:,} coins",
                        inline=False
                    )
                else:
                    # Remove card from collection when you lose using stored card_id
                    if self.card_id and self.card_id in self.user_data["cards"]:
                        del self.user_data["cards"][self.card_id]
                    
                    embed.add_field(
                        name="Card Lost!",
                        value=f"Your **{'⭐' * self.card_data['stars']} {player['username']}{mutation_text}** card is gone!\n"
                            f"Lost Value: {self.card_data['price']:,} coins",
                        inline=False
                    )
                
                # Add odds info
                embed.add_field(
                    name="Game Info",
                    value=f"**Odds:** 1 in 6 (16.67%)\n**Coin Payout:** 6x bet\n**Card Mode:** Win or lose card",
                    inline=False
                )

            # Track gambling stats
            bet_value = self.bet_value if not self.is_card_bet else self.card_data['price'] 
            win_amount = self.bet_value * 6 if not self.is_card_bet else self.card_data['price'] * 6
            self.cog._update_gambling_stats(self.user_data, "dice", won, bet_value, win_amount if won else 0)
            
            # Save data and update message
            await self.cog.save_user_data()
            embed.set_footer(text="Thanks for playing! Use /osugamble to play again.")
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            print(f"Error in dice game: {e}")
            await self._handle_game_error(interaction, "Failed to complete dice game")
    
    async def _handle_game_error(self, interaction, reason="An error occurred"):
        """Handle unexpected errors during gambling"""
        embed = discord.Embed(
            title="Game Error",
            description=f"{reason}. Please try again.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class OsuGachaGamblingCog(commands.Cog, name="Osu Gacha Gambling"):
    """Gambling games system cog"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Don't create new system - use the shared one
        if hasattr(bot, 'gacha_system'):
            self.gacha_system = bot.gacha_system
        else:
            # Fallback if system not loaded yet
            self.gacha_system = OsuGachaSystem()
            bot.gacha_system = self.gacha_system

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

    async def save_user_data(self):
        """Save user data to file"""
        save_json(FILE_PATHS["gacha_data"], self.bot.osu_gacha_data)

    # SLASH COMMANDS - Update choices to include new games
    @app_commands.command(name="osugamble", description="Gamble with coins or cards")
    @app_commands.describe(
        game_type="Type of gambling game to play",
        card_search="Player name to search for card betting (leave empty for coin betting)",
        amount="Amount to bet - coins if no card_search, number of cards if card_search provided"
    )
    @app_commands.choices(game_type=[
        app_commands.Choice(name="Blackjack (bj) - Beat the dealer (Best odds)", value="blackjack"),
        app_commands.Choice(name="Coin Flip (cf) - 50/50 chance", value="coinflip"),
        app_commands.Choice(name="Dice Roll (d) - Guess the number (6x payout)", value="dice"),
        app_commands.Choice(name="Slot Machine (slots) - Match symbols (Big jackpots)", value="slots"),
        app_commands.Choice(name="Dice Tower (tower) - Risk/reward climbing (Up to 20x)", value="tower")
    ])
    async def osu_gamble_slash(self, interaction: discord.Interaction, game_type: str, card_search: str = None, amount: int = 1):
        await self._gamble_command(interaction, game_type, card_search, amount)

    @app_commands.command(name="osuscratch", description="Buy and play scratch cards")
    @app_commands.describe(card_type="Type of scratch card to buy")
    @app_commands.choices(card_type=[
        app_commands.Choice(name="Bronze Scratcher (2,500 coins)", value="bronze"),
        app_commands.Choice(name="Silver Scratcher (10,000 coins)", value="silver"),
        app_commands.Choice(name="Gold Scratcher (25,000 coins)", value="gold")
    ])
    async def osu_scratch_slash(self, interaction: discord.Interaction, card_type: str = "bronze"):
        await self._scratch_command(interaction, card_type, interaction)

    @app_commands.command(name="osugamblestats", description="View gambling statistics")
    @app_commands.describe(user="User to check stats for (optional)")
    async def osu_gamble_stats_slash(self, interaction: discord.Interaction, user: discord.Member = None):
        await self._gamble_stats_command(interaction, user)

    # PREFIX COMMANDS
    @commands.command(name="osugamble", aliases=["ogamble", "gamble", "og"])  
    async def osu_gamble_prefix(self, ctx: commands.Context, game_type: str = None, card_search: str = None, amount: int = 1):
        if not game_type:
            embed = discord.Embed(
                title="Gambling Games",
                description="Test your luck with these exciting games!",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="Available Games",
                value="• `blackjack`, `bj` - Beat the dealer\n"
                      "• `coinflip`, `cf`, `coin` - Heads or tails\n"
                      "• `dice`, `d` - Guess the dice roll\n"
                      "• `slots`, `slot` - Match symbols for jackpots\n"
                      "• `tower`, `climb` - Risk/reward climbing game",
                inline=False
            )

            embed.add_field(
                name="Special Games",
                value="• `/osuscratch` - Buy scratch cards with instant prizes",
                inline=False
            )
            
            embed.add_field(
                name="Betting Options",
                value="• **Cards**: `!og bj mrekk` (bets 1 card)\n• **Cards**: `!og bj mrekk 2` (bets 2 cards)\n• **Coins**: `!og bj 1000` (bets 1000 coins)\n• **Coins w/ Shorthand**: `!og bj 10k` (bets 10,000 coins)",
                inline=False
            )
            
            embed.add_field(
                name="Quick Examples",
                value="`!og bj mrekk` - Blackjack with 1 mrekk card\n`!og cf whitecat 3` - Coinflip with 3 whitecat cards\n`!og d 1000` - Dice with 1000 coins\n`!og cf 5k` - Coinflip with 5,000 coins\n`!og bj 2.5m` - Blackjack with 2,500,000 coins",
                inline=False
            )
            
            embed.add_field(
                name="Shorthand Numbers",
                value="• `k` = thousand (1k = 1,000)\n• `m` = million (1m = 1,000,000)\n• `b` = billion (1b = 1,000,000,000)",
                inline=False
            )
            
            embed.set_footer(text="Aliases: !og = !osugamble | New: slots, tower, scratch cards!")
            await ctx.send(embed=embed)
            return
        
        await self._gamble_command(ctx, game_type, card_search, amount)

    @commands.command(name="osuscratch", aliases=["oscratch", "scratch"])
    async def osu_scratch_prefix(self, ctx: commands.Context, card_type: str = None):
        if card_type is None:
            # Show scratch card information instead of auto-buying bronze
            embed = discord.Embed(
                title="🎫 Scratch Cards",
                description="Instant-win scratch cards with various prizes!",
                color=discord.Color.gold()
            )
            
            # Show all available card types
            for card_key, card_info in SCRATCH_CARD_TYPES.items():
                prizes_text = []
                for prize_key, prize_data in card_info["prizes"].items():
                    if prize_key == "nothing":
                        continue
                    elif "coins" in prize_key:
                        prizes_text.append(f"💰 {prize_data['min']:,}-{prize_data['max']:,} coins")
                    elif prize_key.endswith("_crate"):
                        crate_name = self.gacha_system.crate_config[prize_data["reward"]]["name"]
                        prizes_text.append(f"📦 {crate_name}")
                    elif prize_key == "multiple_crates":
                        prizes_text.append("🎁 3 Random Crates")
                    elif prize_key == "mega_pack":
                        prizes_text.append("🎁 5 Random Crates")
                    elif prize_key == "mystery_card":
                        prizes_text.append("🎴 Mystery Card")
                
                embed.add_field(
                    name=f"{card_info['emoji']} {card_info['name']} - {card_info['cost']:,} coins",
                    value="\n".join(prizes_text[:5]) + ("\n..." if len(prizes_text) > 5 else ""),
                    inline=True
                )
            
            embed.add_field(
                name="How to Play",
                value="• **Purchase** a scratch card with `/osuscratch [type]`\n"
                    "• **Scratch 5 spots** to reveal your prize\n"
                    "• Higher tier cards = better prizes!",
                inline=False
            )
            
            embed.add_field(
                name="Commands",
                value="`/osuscratch bronze` - Buy Bronze Scratcher\n"
                    "`/osuscratch silver` - Buy Silver Scratcher\n"
                    "`/osuscratch gold` - Buy Gold Scratcher",
                inline=False
            )
            
            embed.set_footer(text="Choose your card type to purchase and play!")
            await ctx.send(embed=embed)
            return
        
        await self._scratch_command(ctx, card_type)

    @commands.command(name="osugamblestats", aliases=["ogamblestats", "ogstats"])
    async def osu_gamble_stats_prefix(self, ctx: commands.Context, user: discord.Member = None):
        await self._gamble_stats_command(ctx, user)

    # SHARED COMMAND IMPLEMENTATION
    async def _gamble_command(self, ctx, game_type: str, cmd_card_search: str = None, cmd_amount: int = 1):
        """Handle gambling command with improved parameter parsing and betting logic"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)

        game_aliases = {
            "blackjack": "blackjack", "bj": "blackjack", "black": "blackjack", "21": "blackjack",
            "coinflip": "coinflip", "cf": "coinflip", "coin": "coinflip", "flip": "coinflip",
            "dice": "dice", "d": "dice", "roll": "dice",
            "slots": "slots", "slot": "slots", "spin": "slots",
            "tower": "tower", "climb": "tower", "dicetower": "tower"
        }
        
        game_type_lower = game_type.lower()
        if game_type_lower in game_aliases:
            game_type = game_aliases[game_type_lower]
        else:
            embed = discord.Embed(
                title="Invalid Game Type",
                description=f"Unknown game: `{game_type}`. Valid games are Blackjack, Coinflip, Dice, Slots, Tower.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Available Games & Aliases",
                value="**Blackjack:** `blackjack`, `bj`, `black`, `21`\n"
                      "**Coinflip:** `coinflip`, `cf`, `coin`, `flip`\n"
                      "**Dice:** `dice`, `d`, `roll`\n"
                      "**Slots:** `slots`, `slot`, `spin`\n"
                      "**Tower:** `tower`, `climb`, `dicetower`",
                inline=False
            )
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return
        
        # SPECIAL HANDLING FOR SLOTS - No betting logic needed, persistent interface
        if game_type == "slots":
            view = SlotMachineView(user_data, self.bot, user_id, self)
            embed = view._create_main_embed()
            
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(embed=embed, view=view)
            else:
                await ctx.send(embed=embed, view=view)
            return

        is_card_bet = False
        actual_bet_stake = 0
        card_data_for_view = None
        card_id_for_view = None

        if cmd_card_search is not None:
            # First try to parse as a number with shorthand (10k, 5m, etc.)
            parsed_amount = parse_number_shorthand(cmd_card_search)
            
            if parsed_amount is not None:
                # cmd_card_search is a number (with possible shorthand), so it's a coin bet
                if parsed_amount <= 0:
                    embed = discord.Embed(title="Invalid Bet", description="Coin bet amount must be positive.", color=discord.Color.red())
                    if hasattr(ctx, 'response'): await ctx.response.send_message(embed=embed, ephemeral=True)
                    else: await ctx.send(embed=embed)
                    return
                is_card_bet = False
                actual_bet_stake = parsed_amount
                # cmd_amount is ignored if cmd_card_search is a number (coin bet)
            else:
                # cmd_card_search is not a number, so it's a card name
                is_card_bet = True
                card_name_to_find = cmd_card_search
                # num_cards_to_bet = cmd_amount # Current logic only supports betting 1 card instance

                cards = user_data.get("cards", {})
                matching_cards_found = []
                search_lower = card_name_to_find.lower()
                for c_id, c_data in cards.items():
                    if search_lower in c_data["player_data"]["username"].lower():
                        matching_cards_found.append((c_id, c_data))
                
                if not matching_cards_found:
                    embed = discord.Embed(title="Card Not Found", description=f"You don't have any cards matching: `{card_name_to_find}`", color=discord.Color.red())
                    if hasattr(ctx, 'response'): await ctx.response.send_message(embed=embed, ephemeral=True)
                    else: await ctx.send(embed=embed)
                    return

                # If multiple cards match, use the first one found.
                card_id_for_view, card_data_for_view = matching_cards_found[0]
                actual_bet_stake = card_data_for_view["price"]
        else:
            # cmd_card_search is None, so this is a coin bet using cmd_amount
            # Support shorthand in cmd_amount as well (though it's an int parameter)
            parsed_amount = parse_number_shorthand(str(cmd_amount))
            
            if parsed_amount is None or parsed_amount <= 0:
                embed = discord.Embed(title="Invalid Bet", description="Coin bet amount must be positive.", color=discord.Color.red())
                if hasattr(ctx, 'response'): await ctx.response.send_message(embed=embed, ephemeral=True)
                else: await ctx.send(embed=embed)
                return
            
            is_card_bet = False
            actual_bet_stake = parsed_amount

        # Pre-game validation and actions
        if is_card_bet:
            if not card_data_for_view: # Should have been caught earlier, but as a safeguard
                embed = discord.Embed(title="Error", description="Selected card data is missing for the bet.", color=discord.Color.red())
                if hasattr(ctx, 'response'): await ctx.response.send_message(embed=embed, ephemeral=True)
                else: await ctx.send(embed=embed)
                return
            # Card is NOT removed from user_data here. Game view handles it on loss.
        else: # Coin bet
            if user_data["currency"] < actual_bet_stake:
                embed = discord.Embed(title="Insufficient Funds", description=f"You need {actual_bet_stake:,} coins but only have {user_data['currency']:,}.", color=discord.Color.red())
                if hasattr(ctx, 'response'): await ctx.response.send_message(embed=embed, ephemeral=True)
                else: await ctx.send(embed=embed)
                return
            user_data["currency"] -= actual_bet_stake # Deduct coins for coin bet upfront

        # Create game view
        view = None
        embed_to_send = None

        if game_type == "blackjack":
            view = BlackjackView(user_data, actual_bet_stake, is_card_bet, card_data_for_view, self.bot, user_id, self, card_id_for_view)
            embed_to_send = view._create_game_embed()
        elif game_type == "coinflip":
            view = CoinFlipView(user_data, actual_bet_stake, is_card_bet, card_data_for_view, self.bot, user_id, self, card_id_for_view)
            embed_to_send = self._create_coinflip_embed(actual_bet_stake, is_card_bet, card_data_for_view)
        elif game_type == "dice":
            view = DiceView(user_data, actual_bet_stake, is_card_bet, card_data_for_view, self.bot, user_id, self, card_id_for_view)
            embed_to_send = self._create_dice_embed(actual_bet_stake, is_card_bet, card_data_for_view)
        elif game_type == "tower":
            view = DiceTowerView(user_data, actual_bet_stake, is_card_bet, card_data_for_view, self.bot, user_id, self, card_id_for_view)
            embed_to_send = self._create_tower_embed_initial(actual_bet_stake, is_card_bet, card_data_for_view)
        
        if view and embed_to_send:
            # Save user data (currency deduction for coin bets is done)
            await self.save_user_data()
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(embed=embed_to_send, view=view)
            else:
                await ctx.send(embed=embed_to_send, view=view)
        else:
            # Fallback if view/embed wasn't created for some reason
            embed = discord.Embed(title="Game Error", description="Could not start the game. Please try again.", color=discord.Color.red())
            if hasattr(ctx, 'response'): await ctx.response.send_message(embed=embed, ephemeral=True)
            else: await ctx.send(embed=embed)

    async def _scratch_command(self, ctx, card_type, interaction=None):
        """Scratch card command implementation"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Validate card type
        if card_type not in SCRATCH_CARD_TYPES:
            embed = discord.Embed(
                title="Invalid Card Type",
                description="Available types: `bronze`, `silver`, `gold`",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        card_info = SCRATCH_CARD_TYPES[card_type]
        cost = card_info["cost"]
        
        # Check if user can afford it
        if user_data["currency"] < cost:
            embed = discord.Embed(
                title="Insufficient Coins",
                description=f"You need {cost:,} coins but only have {user_data['currency']:,}!",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Deduct cost
        user_data["currency"] -= cost
        await self.save_user_data()
        
        # Create scratch card view
        view = ScratchCardView(user_data, card_type, self.bot, user_id, self)
        embed = view._create_card_embed()
        
        embed.add_field(
            name="💰 Purchase",
            value=f"Bought for {cost:,} coins\n**New Balance:** {user_data['currency']:,} coins",
            inline=False
        )
        
        if interaction:
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def _gamble_stats_command(self, ctx, target_user: discord.Member = None):
        """Show user's gambling statistics"""
        # Determine which user's stats to show
        if target_user is None:
            # Show command user's own stats
            user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
            display_name = ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name
            is_self = True
        else:
            # Show target user's stats
            user_id = target_user.id
            display_name = target_user.display_name
            is_self = (target_user.id == (ctx.author.id if hasattr(ctx, 'author') else ctx.user.id))

        user_data = self.get_user_gacha_data(user_id)
        
        # Check for gambling_stats or total_games
        gambling_stats = user_data.get("gambling_stats", {})
        total_games = gambling_stats.get("total_games", 0)
        
        if total_games == 0:
            pronoun = "You haven't" if is_self else f"{display_name} hasn't"
            embed = discord.Embed(
                title=f"{'Your' if is_self else f'{display_name}\'s'} Gambling Statistics",
                description=f"{pronoun} gambled yet! Use `/osugamble` to start.",
                color=discord.Color.blue()
            )
            
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        # Calculate win rate
        wins = gambling_stats.get("wins", 0)
        win_rate = (wins / total_games * 100) if total_games > 0 else 0
        
        # Calculate profit/loss
        net_profit = gambling_stats.get("net_profit", 0)
        profit_color = discord.Color.green() if net_profit >= 0 else discord.Color.red()
        profit_symbol = "+" if net_profit >= 0 else ""
        
        embed = discord.Embed(
            title=f"{'Your' if is_self else f'{display_name}\'s'} Gambling Statistics",
            description=f"**Total Games:** {total_games:,}\n**Win Rate:** {win_rate:.1f}%",
            color=profit_color
        )
        
        embed.add_field(
            name="Financial Summary",
            value=f"**Coins Wagered:** {gambling_stats.get('coins_wagered', 0):,}\n"
                f"**Coins Won:** {gambling_stats.get('coins_won', 0):,}\n"
                f"**Coins Lost:** {gambling_stats.get('coins_lost', 0):,}\n"
                f"**Net Profit:** {profit_symbol}{net_profit:,}",
            inline=True
        )
        
        embed.add_field(
            name="Records",
            value=f"**Biggest Win:** {gambling_stats.get('biggest_win', 0):,}\n"
                f"**Biggest Loss:** {gambling_stats.get('biggest_loss', 0):,}\n"
                f"**Total Wins:** {wins:,}\n"
                f"**Total Losses:** {gambling_stats.get('losses', 0):,}",
            inline=True
        )
        
        # Game-specific stats
        games_played = gambling_stats.get("games_played", {})
        game_stats = []
        for game, data in games_played.items():
            if data.get("played", 0) > 0:
                game_win_rate = (data.get("won", 0) / data["played"] * 100)
                game_stats.append(f"**{game.title()}:** {data['played']} played, {game_win_rate:.1f}% win rate")
        
        if game_stats:
            embed.add_field(
                name="Game Breakdown",
                value="\n".join(game_stats),
                inline=False
            )
        
        # Add gambling advice (only for own stats)
        if is_self:
            if net_profit < -1000:
                embed.set_footer(text="Consider taking a break! Remember: the house always has an edge.")
            elif net_profit > 1000:
                embed.set_footer(text="You're on a hot streak! But remember: luck can change quickly.")
            else:
                embed.set_footer(text="Gamble responsibly! Only bet what you can afford to lose.")
        else:
            embed.set_footer(text=f"Gambling statistics for {display_name}")
        
        if hasattr(ctx, 'response'):
            await ctx.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)

    def _update_gambling_stats(self, user_data, game_type, won, bet_amount, winnings):
        """Update gambling statistics for the user"""
        if "gambling_stats" not in user_data:
            user_data["gambling_stats"] = {
                "total_games": 0,
                "wins": 0,
                "losses": 0,
                "net_profit": 0,
                "biggest_win": 0,
                "biggest_loss": 0,
                "total_bets": 0,
                "total_wins": 0,
                "total_losses": 0,
                "coins_wagered": 0,
                "coins_won": 0,
                "coins_lost": 0,
                "games_played": {
                    "blackjack": {"played": 0, "won": 0},
                    "coinflip": {"played": 0, "won": 0},
                    "dice": {"played": 0, "won": 0},
                    "slots": {"played": 0, "won": 0},  # ADD NEW GAMES
                    "tower": {"played": 0, "won": 0}   # ADD NEW GAMES
                }
            }
        
        stats = user_data["gambling_stats"]
        
        # Update general stats
        stats["total_games"] += 1
        stats["total_bets"] += 1
        
        if won:
            stats["wins"] += 1
            stats["total_wins"] += 1
            stats["coins_won"] += winnings
            stats["net_profit"] += (winnings - bet_amount)
            stats["biggest_win"] = max(stats["biggest_win"], winnings - bet_amount)
        else:
            stats["losses"] += 1
            stats["total_losses"] += 1
            stats["coins_lost"] += bet_amount
            stats["net_profit"] -= bet_amount
            stats["biggest_loss"] = max(stats["biggest_loss"], bet_amount)
        
        # Update bet amount
        stats["coins_wagered"] += bet_amount
        
        # Update game-specific stats
        if game_type in stats["games_played"]:
            stats["games_played"][game_type]["played"] += 1
            if won:
                stats["games_played"][game_type]["won"] += 1

    def _create_coinflip_embed(self, bet_amount, is_card_bet, card_data):
        """Create coin flip game embed"""
        embed = discord.Embed(
            title="Coin Flip",
            description="Choose heads or tails! 50% chance to win.",
            color=discord.Color.blue()
        )
        
        if is_card_bet:
            player = card_data["player_data"]
            mutation_text = ""
            if card_data["mutation"]:
                mutation_name = self.gacha_system.mutations[card_data["mutation"]]["name"]
                mutation_text = f" - {mutation_name.upper()}"
            
            embed.add_field(
                name="Card at Risk",
                value=f"**{'⭐' * card_data['stars']} {player['username']}{mutation_text}**\n"
                      f"Value: {card_data['price']:,} coins",
                inline=True
            )
        else:
            embed.add_field(
                name="Bet Amount",
                value=f"{bet_amount:,} coins",
                inline=True
            )
        
        embed.add_field(
            name="Game Rules",
            value="• Choose heads or tails\n• 50% chance to win\n• Coin mode: 2x payout\n• Card mode: Keep or lose card",
            inline=True
        )
        
        return embed

    def _create_dice_embed(self, bet_amount, is_card_bet, card_data):
        """Create dice game embed"""
        embed = discord.Embed(
            title="Dice Roll",
            description="Guess the exact number! 1 in 6 chance to win.",
            color=discord.Color.blue()
        )
        
        if is_card_bet:
            player = card_data["player_data"]
            mutation_text = ""
            if card_data["mutation"]:
                mutation_name = self.gacha_system.mutations[card_data["mutation"]]["name"]
                mutation_text = f" - {mutation_name.upper()}"
            
            embed.add_field(
                name="Card at Risk",
                value=f"**{'⭐' * card_data['stars']} {player['username']}{mutation_text}**\n"
                      f"Value: {card_data['price']:,} coins",
                inline=True
            )
        else:
            embed.add_field(
                name="Bet Amount",
                value=f"{bet_amount:,} coins",
                inline=True
            )
        
        embed.add_field(
            name="Game Rules",
            value="• Guess the exact number (1-6)\n• 16.67% chance to win\n• Coin mode: 6x payout\n• Card mode: Keep or lose card",
            inline=True
        )
        
        return embed
    
    def _create_tower_embed_initial(self, bet_amount, is_card_bet, card_data):
        """Create initial tower game embed"""
        embed = discord.Embed(
            title="🏗️ Dice Tower",
            description="Climb the tower floor by floor! Higher floors = bigger rewards but more risk!",
            color=discord.Color.blue()
        )
        
        if is_card_bet:
            player = card_data["player_data"]
            mutation_text = ""
            if card_data["mutation"]:
                mutation_name = self.gacha_system.mutations[card_data["mutation"]]["name"]
                mutation_text = f" - {mutation_name.upper()}"
            
            embed.add_field(
                name="Card at Risk",
                value=f"**{'⭐' * card_data['stars']} {player['username']}{mutation_text}**\n"
                      f"Value: {card_data['price']:,} coins",
                inline=True
            )
        else:
            embed.add_field(
                name="Starting Bet",
                value=f"{bet_amount:,} coins",
                inline=True
            )
        
        embed.add_field(
            name="How to Play",
            value="• **Climb Higher** - Risk everything to go up\n"
                  "• **Cash Out** - Take current winnings\n"
                  "• Each floor = higher risk & reward\n"
                  "• Penthouse = 20x multiplier!",
            inline=True
        )
        
        return embed

async def setup(bot):
    await bot.add_cog(OsuGachaGamblingCog(bot))