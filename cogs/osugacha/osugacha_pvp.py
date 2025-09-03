import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
import random
import aiohttp
import io
import difflib
from PIL import Image, ImageFilter
from utils.helpers import *
from utils.config import *

# Import the configuration and system
from .osugacha_config import *
from .osugacha_system import OsuGachaSystem

class PvPGamblingView(discord.ui.View):
    """Base PvP gambling view"""
    
    def __init__(self, challenger_id, challenged_id, bet_amount, game_type, pvp_cog):
        super().__init__(timeout=300)
        self.challenger_id = challenger_id
        self.challenged_id = challenged_id
        self.bet_amount = bet_amount
        self.game_type = game_type
        self.pvp_cog = pvp_cog
        self.challenged_accepted = False
        self.game_started = False
        
    @discord.ui.button(label="Accept Challenge", style=discord.ButtonStyle.green, emoji="⚔️")
    async def accept_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged_id:
            await interaction.response.send_message("This isn't your challenge!", ephemeral=True)
            return
            
        self.challenged_accepted = True
        button.disabled = True
        
        # Deduct bets from both players
        challenger_data = self.pvp_cog.get_user_gacha_data(self.challenger_id)
        challenged_data = self.pvp_cog.get_user_gacha_data(self.challenged_id)
        
        challenger_data["currency"] -= self.bet_amount
        challenged_data["currency"] -= self.bet_amount
        
        await self.pvp_cog.save_user_data()
        
        # Start the appropriate game
        if self.game_type == "pp_duel":
            await self._start_pp_duel(interaction)
        elif self.game_type == "rank_guesser":
            await self._start_rank_guesser(interaction)
        elif self.game_type == "bg_guesser":
            await self._start_bg_guesser(interaction)
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
    async def decline_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.challenged_id:
            await interaction.response.send_message("This isn't your challenge!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Challenge Declined",
            description=f"{interaction.user.mention} declined the challenge.",
            color=discord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

    async def _start_pp_duel(self, interaction):
        """Start PP Duel game"""
        view = PPDuelView(self.challenger_id, self.challenged_id, self.bet_amount, self.pvp_cog)
        await view.execute_duel(interaction)

    async def _start_rank_guesser(self, interaction):
        """Start Rank Guesser game"""
        # Get random player from leaderboard cache
        if not self.pvp_cog.gacha_system.leaderboard_cache:
            await self.pvp_cog.gacha_system.rebuild_leaderboard_cache()
        
        if not self.pvp_cog.gacha_system.leaderboard_cache:
            embed = discord.Embed(
                title="Error",
                description="Could not load player data. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        # Pick random player from ranks 1-10000
        target_player = random.choice(self.pvp_cog.gacha_system.leaderboard_cache)
        
        view = RankGuesserView(self.challenger_id, self.challenged_id, self.bet_amount, target_player, self.pvp_cog)
        embed = view.create_game_embed()
        
        await interaction.response.edit_message(embed=embed, view=view)

    async def _start_bg_guesser(self, interaction):
        """Start Background Guesser game"""
        await interaction.response.defer()
        
        # Check if we need to cache beatmaps
        needs_caching = (not self.pvp_cog.popular_beatmaps or 
                        time.time() - self.pvp_cog.beatmap_cache_time > self.pvp_cog.cache_duration)
        
        if needs_caching:
            # Show caching message
            embed = discord.Embed(
                title="Background Guesser - Loading",
                description="**Caching popular beatmaps from osu! API...**\n\n"
                        "This may take 10-30 seconds for the first game.\n"
                        "Future games will be instant!",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Please wait...",
                value="🔄 Fetching top 1000 most popular beatmaps",
                inline=False
            )
            await interaction.edit_original_response(embed=embed)
        
        # Get popular beatmaps
        beatmaps = await self.pvp_cog.get_popular_beatmaps()
        if not beatmaps:
            embed = discord.Embed(
                title="Error",
                description="Could not load beatmaps. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Pick random beatmap
        beatmap = random.choice(beatmaps)
        
        view = BackgroundGuesserView(self.challenger_id, self.challenged_id, self.bet_amount, beatmap, self.pvp_cog)
        await view.start_game(interaction)

class PPDuelView(discord.ui.View):
    """PP Duel implementation"""
    
    def __init__(self, challenger_id, challenged_id, bet_amount, pvp_cog):
        super().__init__(timeout=60)
        self.challenger_id = challenger_id
        self.challenged_id = challenged_id
        self.bet_amount = bet_amount
        self.pvp_cog = pvp_cog

    async def execute_duel(self, interaction):
        """Execute the PP duel"""
        challenger_data = self.pvp_cog.get_user_gacha_data(self.challenger_id)
        challenged_data = self.pvp_cog.get_user_gacha_data(self.challenged_id)
        
        # Check if both players have cards
        if not challenger_data.get("cards") or not challenged_data.get("cards"):
            # Refund bets
            challenger_data["currency"] += self.bet_amount
            challenged_data["currency"] += self.bet_amount
            
            embed = discord.Embed(
                title="PP Duel Cancelled",
                description="One player doesn't have any cards! Bets refunded.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            return
        
        # Get random cards
        challenger_cards = list(challenger_data["cards"].values())
        challenged_cards = list(challenged_data["cards"].values())
        
        challenger_card = random.choice(challenger_cards)
        challenged_card = random.choice(challenged_cards)
        
        # Calculate effective PP
        challenger_pp = self._calculate_effective_pp(challenger_card)
        challenged_pp = self._calculate_effective_pp(challenged_card)
        
        # Determine winner
        if challenger_pp > challenged_pp:
            winner_id = self.challenger_id
            winner_name = "Challenger"
            challenger_data["currency"] += self.bet_amount * 2
        elif challenged_pp > challenger_pp:
            winner_id = self.challenged_id
            winner_name = "Challenged"
            challenged_data["currency"] += self.bet_amount * 2
        else:
            # Tie - refund both
            challenger_data["currency"] += self.bet_amount
            challenged_data["currency"] += self.bet_amount
            winner_name = "Tie"
            winner_id = None
        
        # Update PvP stats
        self._update_pvp_stats(self.challenger_id, winner_id == self.challenger_id, self.bet_amount)
        self._update_pvp_stats(self.challenged_id, winner_id == self.challenged_id, self.bet_amount)
        
        # Create result embed
        embed = self._create_result_embed(challenger_card, challenged_card, challenger_pp, challenged_pp, winner_name)
        
        await self.pvp_cog.save_user_data()
        await interaction.response.edit_message(embed=embed, view=None)

    def _calculate_effective_pp(self, card_data):
        """Calculate effective PP with bonuses"""
        base_pp = card_data["player_data"]["pp"]
        
        # Star bonus: 10% per star above 1
        star_bonus = (card_data["stars"] - 1) * 0.1
        
        # Mutation bonus
        mutation_bonus = 0
        if card_data.get("mutation"):
            mutation_multiplier = self.pvp_cog.gacha_system.mutations[card_data["mutation"]]["multiplier"]
            mutation_bonus = (mutation_multiplier - 1) * 0.3
        
        effective_pp = base_pp * (1 + star_bonus + mutation_bonus)
        return round(effective_pp, 1)

    def _update_pvp_stats(self, user_id, won, bet_amount):
        """Update PvP statistics (stats only, no coin changes)"""
        user_data = self.pvp_cog.get_user_gacha_data(user_id)
        
        if "pvp_stats" not in user_data:
            user_data["pvp_stats"] = {
                "total_games": 0,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "coins_won": 0,
                "coins_lost": 0,
                "net_profit": 0,
                "biggest_win": 0,
                "biggest_loss": 0,
                "games_by_type": {}
            }
        
        stats = user_data["pvp_stats"]
        stats["total_games"] += 1
        
        # Track by game type
        if "pp_duel" not in stats["games_by_type"]:
            stats["games_by_type"]["pp_duel"] = {"played": 0, "won": 0}
        
        stats["games_by_type"]["pp_duel"]["played"] += 1
        
        if won:
            stats["wins"] += 1
            stats["games_by_type"]["pp_duel"]["won"] += 1
            # Track winnings for stats (winner gets 2x bet)
            winnings = bet_amount * 2
            stats["coins_won"] += winnings
            stats["net_profit"] += bet_amount  # Net profit is bet amount
            stats["biggest_win"] = max(stats["biggest_win"], bet_amount)
        elif won is False:  # Lost (not tie)
            stats["losses"] += 1
            # Track losses for stats only (don't modify actual coins)
            stats["coins_lost"] += bet_amount
            stats["net_profit"] -= bet_amount
            stats["biggest_loss"] = max(stats["biggest_loss"], bet_amount)
        else:  # Tie
            stats["ties"] += 1

    def _create_result_embed(self, challenger_card, challenged_card, challenger_pp, challenged_pp, winner_name):
        """Create result embed"""
        embed = discord.Embed(
            title="PP Duel Results!",
            color=discord.Color.gold() if winner_name != "Tie" else discord.Color.blue()
        )
        
        # Challenger card
        c_player = challenger_card["player_data"]
        c_mutation = f" - {self.pvp_cog.gacha_system.mutations[challenger_card['mutation']]['name'].upper()}" if challenger_card.get("mutation") else ""
        
        embed.add_field(
            name="Challenger Card",
            value=f"**{'⭐' * challenger_card['stars']} {c_player['username']}{c_mutation}**\n"
                  f"Rank #{c_player['rank']:,}\n"
                  f"Base PP: {c_player['pp']:,.1f}\n"
                  f"**Effective PP: {challenger_pp:,.1f}**",
            inline=True
        )
        
        # Challenged card
        ch_player = challenged_card["player_data"]
        ch_mutation = f" - {self.pvp_cog.gacha_system.mutations[challenged_card['mutation']]['name'].upper()}" if challenged_card.get("mutation") else ""
        
        embed.add_field(
            name="Challenged Card",
            value=f"**{'⭐' * challenged_card['stars']} {ch_player['username']}{ch_mutation}**\n"
                  f"Rank #{ch_player['rank']:,}\n"
                  f"Base PP: {ch_player['pp']:,.1f}\n"
                  f"**Effective PP: {challenged_pp:,.1f}**",
            inline=True
        )
        
        # Result
        if winner_name == "Tie":
            result_text = f"**It's a tie!** Both players get their {self.bet_amount:,} coins back!"
        else:
            pp_diff = abs(challenger_pp - challenged_pp)
            result_text = f"**{winner_name} wins!**\nBy {pp_diff:.1f} PP difference\nPrize: {self.bet_amount * 2:,} coins"
        
        embed.add_field(
            name="Result",
            value=result_text,
            inline=False
        )
        
        return embed

class RankGuesserView(discord.ui.View):
    """Rank Guesser implementation"""
    
    def __init__(self, challenger_id, challenged_id, bet_amount, target_player, pvp_cog):
        super().__init__(timeout=120)
        self.challenger_id = challenger_id
        self.challenged_id = challenged_id
        self.bet_amount = bet_amount
        self.target_player = target_player
        self.pvp_cog = pvp_cog
        
        self.challenger_guess = None
        self.challenged_guess = None
        self.challenger_submitted = False
        self.challenged_submitted = False

    @discord.ui.button(label="Submit Guess", style=discord.ButtonStyle.primary, emoji="🎯")
    async def submit_guess(self, interaction: discord.Interaction, button):
        if interaction.user.id not in [self.challenger_id, self.challenged_id]:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        
        modal = RankGuessModal(self, interaction.user.id)
        await interaction.response.send_modal(modal)

    def create_game_embed(self):
        """Create the game embed"""
        embed = discord.Embed(
            title="Rank Guesser Challenge!",
            description=f"Pot: {self.bet_amount * 2:,} coins\n\nGuess this player's **global rank**!",
            color=discord.Color.purple()
        )
        
        # Player stats (hide rank)
        player = self.target_player
        embed.add_field(
            name="Mystery Player Stats",
            value=f"**PP:** {player['pp']:,.0f}\n"
                  f"**Accuracy:** {player['accuracy']:.2f}%\n"
                  f"**Play Count:** {player['play_count']:,}\n"
                  f"**Country:** {player['country']}\n"
                  f"**Level:** {player['level']:.0f}",
            inline=False
        )
        
        embed.set_footer(text="Both players submit your rank guesses! (1-10000)")
        return embed

    async def check_winner(self, interaction):
        """Check if we have a winner and edit the original message"""
        if not (self.challenger_submitted and self.challenged_submitted):
            return
        
        actual_rank = self.target_player['rank']
        
        # Calculate distances
        challenger_distance = abs(self.challenger_guess - actual_rank)
        challenged_distance = abs(self.challenged_guess - actual_rank)
        
        # Determine winner
        challenger_data = self.pvp_cog.get_user_gacha_data(self.challenger_id)
        challenged_data = self.pvp_cog.get_user_gacha_data(self.challenged_id)
        
        if challenger_distance < challenged_distance:
            winner_id = self.challenger_id
            winner_name = "Challenger"
            challenger_data["currency"] += self.bet_amount * 2
        elif challenged_distance < challenger_distance:
            winner_id = self.challenged_id
            winner_name = "Challenged"
            challenged_data["currency"] += self.bet_amount * 2
        else:
            # Tie - refund both
            challenger_data["currency"] += self.bet_amount
            challenged_data["currency"] += self.bet_amount
            winner_name = "Tie"
            winner_id = None
        
        # Update PvP stats
        self._update_pvp_stats(self.challenger_id, winner_id == self.challenger_id)
        self._update_pvp_stats(self.challenged_id, winner_id == self.challenged_id)
        
        # Create result embed
        embed = self._create_result_embed(actual_rank, winner_name, challenger_distance, challenged_distance)
        
        await self.pvp_cog.save_user_data()
        
        # Edit the original message to show results (NOT ephemeral)
        try:
            # Try to edit through the interaction directly first
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception:
            # Fallback: try to get original response and edit it
            try:
                original_message = await interaction.original_response()
                await original_message.edit(embed=embed, view=None)
            except Exception:
                # Last resort: send new message
                try:
                    await interaction.channel.send(embed=embed)
                except Exception:
                    pass

    def _update_pvp_stats(self, user_id, won):
        """Update PvP stats for rank guesser (stats only, no coin changes)"""
        user_data = self.pvp_cog.get_user_gacha_data(user_id)
        
        if "pvp_stats" not in user_data:
            user_data["pvp_stats"] = {
                "total_games": 0, "wins": 0, "losses": 0, "ties": 0,
                "coins_won": 0, "coins_lost": 0, "net_profit": 0,
                "biggest_win": 0, "biggest_loss": 0, "games_by_type": {}
            }
        
        stats = user_data["pvp_stats"]
        stats["total_games"] += 1
        
        # Track by game type
        if "rank_guesser" not in stats["games_by_type"]:
            stats["games_by_type"]["rank_guesser"] = {"played": 0, "won": 0}
        
        stats["games_by_type"]["rank_guesser"]["played"] += 1
        
        if won:
            stats["wins"] += 1
            stats["games_by_type"]["rank_guesser"]["won"] += 1
            # Track winnings for stats (winner gets 2x bet)
            stats["coins_won"] += self.bet_amount * 2
            stats["net_profit"] += self.bet_amount
            stats["biggest_win"] = max(stats["biggest_win"], self.bet_amount)
        elif won is False:
            stats["losses"] += 1
            # Track losses for stats only (don't modify actual coins)
            stats["coins_lost"] += self.bet_amount
            stats["net_profit"] -= self.bet_amount
            stats["biggest_loss"] = max(stats["biggest_loss"], self.bet_amount)
        else:
            stats["ties"] += 1
    
    def _create_result_embed(self, actual_rank, winner_name, challenger_distance, challenged_distance):
        """Create result embed for rank guesser"""
        embed = discord.Embed(
            title="🎯 Rank Guesser Results!",
            color=discord.Color.gold() if winner_name != "Tie" else discord.Color.blue()
        )
        
        # Player info
        player = self.target_player
        embed.add_field(
            name="Mystery Player Revealed",
            value=f"**{player['username']}**\n"
                  f"**Actual Rank:** #{actual_rank:,}\n"
                  f"**PP:** {player['pp']:,.0f}\n"
                  f"**Accuracy:** {player['accuracy']:.2f}%\n"
                  f"**Country:** {player['country']}",
            inline=False
        )
        
        # Guesses
        challenger_user = self.pvp_cog.bot.get_user(self.challenger_id)
        challenged_user = self.pvp_cog.bot.get_user(self.challenged_id)
        
        embed.add_field(
            name="Challenger Guess",
            value=f"**{challenger_user.display_name if challenger_user else 'Challenger'}**\n"
                  f"Guess: #{self.challenger_guess:,}\n"
                  f"Distance: {challenger_distance:,} ranks",
            inline=True
        )
        
        embed.add_field(
            name="Challenged Guess", 
            value=f"**{challenged_user.display_name if challenged_user else 'Challenged'}**\n"
                  f"Guess: #{self.challenged_guess:,}\n"
                  f"Distance: {challenged_distance:,} ranks",
            inline=True
        )
        
        # Result
        if winner_name == "Tie":
            result_text = f"**It's a tie!** Both players were equally close!\nBoth get their {self.bet_amount:,} coins back."
        else:
            distance_diff = abs(challenger_distance - challenged_distance)
            result_text = f"**{winner_name} wins!**\nCloser by {distance_diff:,} ranks\n💰 Prize: {self.bet_amount * 2:,} coins"
        
        embed.add_field(
            name="Result",
            value=result_text,
            inline=False
        )
        
        return embed

class RankGuessModal(discord.ui.Modal):
    """Modal for rank guessing"""
    
    def __init__(self, view, user_id):
        super().__init__(title="Guess the Rank!")
        self.view = view
        self.user_id = user_id
        
        self.rank_input = discord.ui.TextInput(
            label="Your Rank Guess",
            placeholder="Enter rank (1-10000)",
            min_length=1,
            max_length=5
        )
        self.add_item(self.rank_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            guess = int(self.rank_input.value)
            if not (1 <= guess <= 10000):
                await interaction.response.send_message("Rank must be between 1-10000!", ephemeral=True)
                return
            
            # Store guess
            if self.user_id == self.view.challenger_id:
                self.view.challenger_guess = guess
                self.view.challenger_submitted = True
            else:
                self.view.challenged_guess = guess
                self.view.challenged_submitted = True
            
            # Check if both submitted
            if self.view.challenger_submitted and self.view.challenged_submitted:
                # Both players submitted - edit the original message with results
                await self.view.check_winner(interaction)
            else:
                # Only one player submitted - send ephemeral confirmation
                await interaction.response.send_message(f"Guess submitted: #{guess:,}", ephemeral=True)
                
        except ValueError:
            await interaction.response.send_message("Please enter a valid number!", ephemeral=True)

class BackgroundGuesserView(discord.ui.View):
    """Background Guesser with chat-based guessing"""
    
    def __init__(self, challenger_id, challenged_id, bet_amount, beatmap, pvp_cog):
        super().__init__(timeout=300)  # 5 minutes max
        self.challenger_id = challenger_id
        self.challenged_id = challenged_id
        self.bet_amount = bet_amount
        self.beatmap = beatmap
        self.pvp_cog = pvp_cog
        
        self.phase = 1  # 1=blurred, 2=clear, 3=new map blurred, etc.
        self.current_beatmap = beatmap
        self.game_ended = False
        self.channel = None  # Will store the channel where game started
        self.message_listener_task = None
        self.original_message = None
        self.phase_timer_task = None 
    
    # NO BUTTONS - Completely removed submit_guess button
    
    async def start_game(self, interaction):
        """Start the background guesser game"""
        self.channel = interaction.channel  # Store channel for message listening
        
        # Create blurred image
        blurred_image = await self.pvp_cog.create_blurred_background(self.beatmap['background_url'])
        
        embed = self._create_game_embed("🟫 Blurred Background - Phase 1")
        
        if blurred_image:
            file = discord.File(blurred_image, filename="blurred_bg.png")
            embed.set_image(url="attachment://blurred_bg.png")
            
            # Check if interaction was already responded to
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=None, attachments=[file])
            else:
                await interaction.response.edit_message(embed=embed, view=None, attachments=[file])
        else:
            embed.add_field(name="⚠️", value="Image failed to load", inline=False)
            
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=None)
            else:
                await interaction.response.edit_message(embed=embed, view=None)
        
        # Store original message reference
        try:
            self.original_message = await interaction.original_response()
        except:
            pass
        
        # Start message listener and phase progression
        self.message_listener_task = asyncio.create_task(self._listen_for_guesses())
        self.phase_timer_task = asyncio.create_task(self._start_phase_timer(interaction))  
        
    async def _listen_for_guesses(self):
        """Listen for chat messages from players"""
        def check(message):
            # Only accept messages from the two players in the same channel
            return (message.author.id in [self.challenger_id, self.challenged_id] and 
                    message.channel.id == self.channel.id and
                    not self.game_ended and
                    not message.author.bot and
                    len(message.content.strip()) > 0)
        
        try:
            while not self.game_ended:
                # Wait for a message from either player
                message = await self.pvp_cog.bot.wait_for('message', check=check, timeout=300)
                
                # Check if the guess is correct
                await self._check_guess(message.author.id, message.content, message)
                
                # Check if game ended
                if self.game_ended:
                    break
                    
        except asyncio.TimeoutError:
            if not self.game_ended:
                await self._end_game_timeout()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    
    async def _check_guess(self, guesser_id, guess, message):
        """Check if the guess is correct using very strict string matching"""
        if self.game_ended:
            return

        correct_title = self.current_beatmap['title'].lower()
        correct_artist = self.current_beatmap['artist'].lower()
        guess_lower = guess.lower().strip()
        
        # ✅ MUCH MORE STRICT: Reject very short guesses
        if len(guess_lower) < 3:  # ✅ INCREASED from 3 to 4 characters minimum
            return  # Don't accept guesses shorter than 4 characters
        
        # Remove common punctuation and extra spaces for better matching
        def clean_string(s):
            import re
            # Remove common punctuation and normalize spaces
            s = re.sub(r'[^\w\s]', ' ', s)  # Replace punctuation with spaces
            s = re.sub(r'\s+', ' ', s)      # Normalize multiple spaces
            return s.strip()
        
        clean_title = clean_string(correct_title)
        clean_artist = clean_string(correct_artist)
        clean_guess = clean_string(guess_lower)
        
        # ✅ MUCH MORE STRICT: Substring matching now very restrictive
        title_substring = False
        artist_substring = False
        
        if len(clean_guess) >= 6:  # ✅ INCREASED from 4 to 6 characters for substring
            # Check if guess is substantial portion of title/artist (at least 40%)
            title_substring = (clean_guess in clean_title and 
                            len(clean_guess) >= len(clean_title) * 0.4)  # ✅ INCREASED from 30% to 40%
            artist_substring = (clean_guess in clean_artist and 
                            len(clean_guess) >= len(clean_artist) * 0.4)  # ✅ INCREASED from 30% to 40%
        
        # Calculate similarity ratios (0.0 to 1.0)
        title_similarity = difflib.SequenceMatcher(None, clean_guess, clean_title).ratio()
        artist_similarity = difflib.SequenceMatcher(None, clean_guess, clean_artist).ratio()
        
        # ✅ MUCH MORE STRICT: Word matching with higher requirements
        title_words = clean_title.split()
        artist_words = clean_artist.split()
        guess_words = clean_guess.split()
        
        # Check if any word in the guess closely matches any word in title/artist
        word_match_threshold = 0.90  # ✅ INCREASED from 0.85 to 0.90 (much more strict)
        title_word_match = False
        artist_word_match = False
        
        for guess_word in guess_words:
            if len(guess_word) >= 5:  # ✅ INCREASED from 4 to 5 characters minimum
                for title_word in title_words:
                    if len(title_word) >= 5:  # ✅ Target word must also be 5+ chars
                        word_sim = difflib.SequenceMatcher(None, guess_word, title_word).ratio()
                        if word_sim >= word_match_threshold:
                            title_word_match = True
                            break
                
                for artist_word in artist_words:
                    if len(artist_word) >= 5:  # ✅ Target word must also be 5+ chars
                        word_sim = difflib.SequenceMatcher(None, guess_word, artist_word).ratio()
                        if word_sim >= word_match_threshold:
                            artist_word_match = True
                            break
        
        # ✅ MUCH MORE STRICT: Very high thresholds
        similarity_threshold = 0.90    # ✅ INCREASED from 0.85 to 0.90
        partial_threshold = 0.85       # ✅ INCREASED from 0.75 to 0.85
        
        # ✅ VERY STRICT: Much more restrictive acceptance criteria
        is_correct = (
            (title_substring and len(clean_guess) >= 7) or  # ✅ Substring must be 7+ chars (was 5)
            (artist_substring and len(clean_guess) >= 7) or  # ✅ Substring must be 7+ chars (was 5)
            title_similarity >= similarity_threshold or  # 90% similarity to title
            artist_similarity >= similarity_threshold or  # 90% similarity to artist
            (title_similarity >= partial_threshold and len(clean_guess) >= 8) or  # ✅ Partial match needs 8+ chars (was 6)
            (artist_similarity >= partial_threshold and len(clean_guess) >= 8) or  # ✅ Partial match needs 8+ chars (was 6)
            (title_word_match and len(clean_guess) >= 6) or  # ✅ Word match with minimum 6 chars (was 4)
            (artist_word_match and len(clean_guess) >= 6)    # ✅ Word match with minimum 6 chars (was 4)
        )
        
        # ✅ ADDITIONAL STRICT CHECK: Reject common short words
        common_short_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'man', 'way', 'too', 'any', 'she', 'oil', 'sit', 'set'}
        
        if clean_guess in common_short_words or any(word in common_short_words for word in guess_words):
            is_correct = False  # ✅ Reject common short words entirely
        
        # ✅ ADDITIONAL CHECK: Reject single-word guesses that are too short relative to title
        if len(guess_words) == 1 and len(clean_guess) < len(clean_title) * 0.3:
            is_correct = False  # ✅ Single word must be at least 30% of title length
        
        if is_correct:
            self.game_ended = True
            
            # Cancel phase timer
            if self.phase_timer_task:
                self.phase_timer_task.cancel()
            
            # Award winner
            winner_data = self.pvp_cog.get_user_gacha_data(guesser_id)
            winner_data["currency"] += self.bet_amount * 2
            
            # Update stats
            self._update_pvp_stats(self.challenger_id, guesser_id == self.challenger_id)
            self._update_pvp_stats(self.challenged_id, guesser_id == self.challenged_id)
            
            await self.pvp_cog.save_user_data()
            
            # Send result message
            try:
                await self._send_result_message(guesser_id, guess, message)
            except Exception:
                pass
            
            return
    
    async def _send_result_message(self, winner_id, winning_guess, message):
        """Delete original message and send new result message with background"""
        winner_name = "Challenger" if winner_id == self.challenger_id else "Challenged"
        winner_user = self.pvp_cog.bot.get_user(winner_id)
        
        # Create result embed
        embed = discord.Embed(
            title="Background Guesser Results!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="The Map Was",
            value=f"**{self.current_beatmap['title']}** by **{self.current_beatmap['artist']}**\n"
                f"Mapped by {self.current_beatmap['creator']}\n"
                f"{self.current_beatmap['difficulty_rating']}★",
            inline=False
        )
        
        embed.add_field(
            name="Winner",
            value=f"**{winner_user.display_name if winner_user else 'Unknown'}** guessed: `{winning_guess}`\n"
                f"Prize: {self.bet_amount * 2:,} coins\n"
                f"Phase: {self.phase}",
            inline=False
        )
        
        # Try to get the clear background image for the result
        image_success = False
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.current_beatmap['background_url']) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        # Process image
                        image = Image.open(io.BytesIO(image_data))
                        image = image.resize((400, 300))
                        
                        img_bytes = io.BytesIO()
                        image.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        
                        file = discord.File(img_bytes, filename="result_bg.png")
                        embed.set_image(url="attachment://result_bg.png")
                        image_success = True
                        
                        # Send result message with image
                        result_message = await self.channel.send(embed=embed, file=file)
                        
        except Exception:
            # Image failed, continue without it
            pass
        
        # Send result message without image if image failed
        if not image_success:
            try:
                result_message = await self.channel.send(embed=embed)
            except Exception:
                return
        
        # Try to delete the original message (after result is sent)
        try:
            if self.original_message:
                await asyncio.wait_for(self.original_message.delete(), timeout=3.0)
        except Exception:
            pass
    
    async def _end_game_timeout(self):
        """Handle game timeout"""
        self.game_ended = True
        
        # Refund both players
        challenger_data = self.pvp_cog.get_user_gacha_data(self.challenger_id)
        challenged_data = self.pvp_cog.get_user_gacha_data(self.challenged_id)
        
        challenger_data["currency"] += self.bet_amount
        challenged_data["currency"] += self.bet_amount
        
        await self.pvp_cog.save_user_data()
        
        embed = discord.Embed(
            title="Background Guesser - Timeout",
            description="Game timed out! Both players have been refunded.",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="The Map Was",
            value=f"**{self.current_beatmap['title']}** by **{self.current_beatmap['artist']}**\n"
                  f"Mapped by {self.current_beatmap['creator']}\n"
                  f"{self.current_beatmap['difficulty_rating']}★",
            inline=False
        )
        
        # Delete original and send timeout message
        try:
            if self.original_message:
                await self.original_message.delete()
        except:
            pass
        
        await self.channel.send(embed=embed)
    
    def _create_game_embed(self, phase_text):
        """Create game embed"""
        embed = discord.Embed(
            title="🎨 Background Guesser Challenge!",
            description=f"💰 Pot: {self.bet_amount * 2:,} coins\n\n{phase_text}\n\n**Type your guess in chat!** (song title or artist)",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="Current Map Info",
            value=f"{self.current_beatmap['difficulty_rating']}★\n"
                  f"{self.current_beatmap['playcount']:,} plays\n"
                  f"Mapped by {self.current_beatmap['creator']}",
            inline=True
        )
        
        embed.set_footer(text="Just type your guess in this channel! First correct guess wins!")
        return embed

    async def _start_phase_timer(self, interaction):
        """Handle phase progression"""
        try:
            await asyncio.sleep(10)  # Phase 1: 10 seconds blurred
            
            if not self.game_ended:
                await self._progress_to_clear(interaction)
                
                if not self.game_ended:
                    await asyncio.sleep(20)  # Phase 2: 20 seconds clear
            
            if not self.game_ended:
                await self._progress_to_new_map(interaction)
                
        except asyncio.CancelledError:
            return
        except Exception:
            pass

    async def _progress_to_clear(self, interaction):
        """Show clear background"""
        if self.game_ended:
            return
            
        self.phase = 2
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.current_beatmap['background_url']) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        if self.game_ended:
                            return
                        
                        # Resize for Discord
                        image = Image.open(io.BytesIO(image_data))
                        image = image.resize((400, 300))
                        
                        img_bytes = io.BytesIO()
                        image.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        
                        embed = self._create_game_embed("🖼️ Clear Background - Phase 2")
                        file = discord.File(img_bytes, filename="clear_bg.png")
                        embed.set_image(url="attachment://clear_bg.png")
                        
                        if self.game_ended:
                            return
                        
                        # Update the original message
                        if self.original_message:
                            try:
                                await self.original_message.edit(embed=embed, attachments=[file])
                            except Exception:
                                self.game_ended = True
                                
        except Exception:
            pass

    async def _progress_to_new_map(self, interaction):
        """Show new beatmap"""
        if self.game_ended:
            return
            
        self.phase = 3
        
        # Get new random beatmap
        beatmaps = await self.pvp_cog.get_popular_beatmaps()
        if beatmaps:
            available_maps = [b for b in beatmaps if b['id'] != self.current_beatmap['id']]
            if available_maps:
                self.current_beatmap = random.choice(available_maps)
        
        if self.game_ended:
            return
        
        # Show new blurred image
        blurred_image = await self.pvp_cog.create_blurred_background(self.current_beatmap['background_url'])
        
        embed = self._create_game_embed("🆕 New Map - Blurred - Phase 3")
        
        if blurred_image and not self.game_ended:
            file = discord.File(blurred_image, filename="new_blurred_bg.png")
            embed.set_image(url="attachment://new_blurred_bg.png")
            
            try:
                if self.original_message:
                    await self.original_message.edit(embed=embed, attachments=[file])
            except Exception:
                pass
        
        # Continue cycling if no winner
        if not self.game_ended:
            await asyncio.sleep(10)
            if not self.game_ended:
                await self._progress_to_clear(interaction)

    def _update_pvp_stats(self, user_id, won):
        """Update PvP stats (stats only, no coin changes)"""
        user_data = self.pvp_cog.get_user_gacha_data(user_id)
        
        if "pvp_stats" not in user_data:
            user_data["pvp_stats"] = {
                "total_games": 0, "wins": 0, "losses": 0, "ties": 0,
                "coins_won": 0, "coins_lost": 0, "net_profit": 0,
                "biggest_win": 0, "biggest_loss": 0, "games_by_type": {}
            }
        
        stats = user_data["pvp_stats"]
        stats["total_games"] += 1
        
        if "bg_guesser" not in stats["games_by_type"]:
            stats["games_by_type"]["bg_guesser"] = {"played": 0, "won": 0}
        
        stats["games_by_type"]["bg_guesser"]["played"] += 1
        
        if won:
            stats["wins"] += 1
            stats["games_by_type"]["bg_guesser"]["won"] += 1
            # Track winnings for stats (winner gets 2x bet)
            stats["coins_won"] += self.bet_amount * 2
            stats["net_profit"] += self.bet_amount
            stats["biggest_win"] = max(stats["biggest_win"], self.bet_amount)
        else:
            stats["losses"] += 1
            # Track losses for stats only (don't modify actual coins)
            stats["coins_lost"] += self.bet_amount
            stats["net_profit"] -= self.bet_amount
            stats["biggest_loss"] = max(stats["biggest_loss"], self.bet_amount)

    def _create_result_embed(self, winner_id, winning_guess):
        """Create result embed"""
        winner_name = "Challenger" if winner_id == self.challenger_id else "Challenged"
        
        embed = discord.Embed(
            title="🎨 Background Guesser Results!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="The Map Was",
            value=f"**{self.current_beatmap['title']}** by **{self.current_beatmap['artist']}**\n"
                  f"Mapped by {self.current_beatmap['creator']}\n"
                  f"{self.current_beatmap['difficulty_rating']}★",
            inline=False
        )
        
        embed.add_field(
            name="Winner",
            value=f"**{winner_name}** guessed: `{winning_guess}`\n"
                  f"Prize: {self.bet_amount * 2:,} coins\n"
                  f"Phase: {self.phase}",
            inline=False
        )
        
        return embed

class BeatmapGuessModal(discord.ui.Modal):
    """Modal for beatmap guessing"""
    
    def __init__(self, view, user_id):
        super().__init__(title="Guess the Song!")
        self.view = view
        self.user_id = user_id
        
        self.guess_input = discord.ui.TextInput(
            label="Your Guess",
            placeholder="Enter song title or artist...",
            min_length=1,
            max_length=100
        )
        self.add_item(self.guess_input)

    async def on_submit(self, interaction: discord.Interaction):
        guess = self.guess_input.value.strip()
        
        # Send ephemeral confirmation first
        await interaction.response.send_message(f"Guess submitted: `{guess}`", ephemeral=True)
        
        # Check winner - this will update the original message if someone wins
        await self.view.check_winner(self.user_id, guess, interaction)

class OsuPvPCog(commands.Cog, name="Osu PvP Games"):
    """PvP gambling games cog"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Use shared gacha system
        if hasattr(bot, 'gacha_system'):
            self.gacha_system = bot.gacha_system
        else:
            from .osugacha_system import OsuGachaSystem
            self.gacha_system = OsuGachaSystem()
            bot.gacha_system = self.gacha_system
        
        # Beatmap cache
        self.popular_beatmaps = []
        self.beatmap_cache_time = 0
        self.cache_duration = 86400  # 1 hour

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
                "pvp_stats": {
                    "total_games": 0,
                    "wins": 0,
                    "losses": 0,
                    "ties": 0,
                    "coins_won": 0,
                    "coins_lost": 0,
                    "net_profit": 0,
                    "biggest_win": 0,
                    "biggest_loss": 0,
                    "games_by_type": {}
                }
            }
            save_json(FILE_PATHS["gacha_data"], self.bot.osu_gacha_data)
        return self.bot.osu_gacha_data[user_id_str]

    async def save_user_data(self):
        """Save user data"""
        save_json(FILE_PATHS["gacha_data"], self.bot.osu_gacha_data)

    async def get_popular_beatmaps(self):
        """Get popular beatmaps from osu! API"""
        if (self.popular_beatmaps and 
            time.time() - self.beatmap_cache_time < self.cache_duration):
            return self.popular_beatmaps
        
        try:
            token = await self.gacha_system.get_access_token()
            if not token:
                return []
            
            headers = {'Authorization': f'Bearer {token}'}
            beatmaps = []
            
            print("Caching popular beatmaps for Background Guesser...")
            
            async with aiohttp.ClientSession() as session:
                url = 'https://osu.ppy.sh/api/v2/beatmapsets/search'
                params = {
                    'q': '',
                    's': 'ranked',
                    'sort': 'plays_desc',
                    'limit': 50
                }
                
                # Get 1000 popular beatmaps
                for page in range(20):
                    params['offset'] = page * 50
                    
                    # Progress logging every 5 pages
                    if page % 5 == 0 and page > 0:
                        print(f"📊 Beatmap cache progress: {page * 50}/1000 beatmaps...")
                    
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            for beatmapset in data.get('beatmapsets', []):
                                if beatmapset.get('beatmaps'):
                                    main_diff = max(beatmapset['beatmaps'], 
                                                key=lambda x: x.get('playcount', 0))
                                    
                                    beatmap = {
                                        'id': main_diff['id'],
                                        'beatmapset_id': beatmapset['id'],
                                        'title': beatmapset['title'],
                                        'artist': beatmapset['artist'],
                                        'creator': beatmapset['creator'],
                                        'difficulty_rating': round(main_diff.get('difficulty_rating', 0), 2),
                                        'playcount': main_diff.get('playcount', 0),
                                        'background_url': f"https://assets.ppy.sh/beatmaps/{beatmapset['id']}/covers/raw.jpg"
                                    }
                                    beatmaps.append(beatmap)
                        
                        await asyncio.sleep(0.1)
            
            self.popular_beatmaps = beatmaps
            self.beatmap_cache_time = time.time()
            print(f"✅ Cached {len(beatmaps)} popular beatmaps for Background Guesser")
            
            return beatmaps
            
        except Exception as e:
            print(f"❌ Failed to fetch beatmaps: {e}")
            return []

    async def create_blurred_background(self, background_url):
        """Create blurred background image"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(background_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        image = Image.open(io.BytesIO(image_data))
                        image = image.resize((400, 300))
                        blurred = image.filter(ImageFilter.GaussianBlur(radius=8))
                        
                        img_bytes = io.BytesIO()
                        blurred.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        
                        return img_bytes
        except Exception as e:
            print(f"❌ Failed to create blurred background: {e}")
            return None

    # SLASH COMMANDS
    @app_commands.command(name="osupvp", description="Challenge another player to PvP games")
    @app_commands.describe(
        opponent="The player to challenge",
        game_type="Type of PvP game",
        bet_amount="Amount of coins to bet"
    )
    @app_commands.choices(game_type=[
        app_commands.Choice(name="PP Duel - Compare card PP values", value="pp_duel"),
        app_commands.Choice(name="Rank Guesser - Guess player's rank from stats", value="rank_guesser"),
        app_commands.Choice(name="Background Guesser - Guess song from backgrounds", value="bg_guesser"),
    ])
    async def osu_pvp_slash(self, interaction: discord.Interaction, opponent: discord.Member, 
                           game_type: str, bet_amount: int):
        await self._pvp_command(interaction, opponent, game_type, bet_amount)

    @app_commands.command(name="osupvpstats", description="View your PvP statistics")
    async def osu_pvp_stats_slash(self, interaction: discord.Interaction):
        await self._pvp_stats_command(interaction)

    # PREFIX COMMANDS
    @commands.command(name="osupvp", aliases=["opvp", "pvp"])
    async def osu_pvp_prefix(self, ctx: commands.Context, opponent: discord.Member = None, 
                            game_type: str = None, bet_amount: int = None):
        if not opponent or not game_type or not bet_amount:
            embed = discord.Embed(
                title="⚔️ PvP Games",
                description="Challenge other players to exciting PvP games!",
                color=discord.Color.purple()
            )
            
            embed.add_field(
                name="Available Games",
                value="**PP Duel** - `pp`, `duel`, `pp_duel`\n"
                    "**Rank Guesser** - `rank`, `guess`, `rank_guesser`\n"
                    "**Background Guesser** - `bg`, `background`, `bg_guesser`",
                inline=False
            )
            
            embed.add_field(
                name="Usage Examples",
                value="`!opvp @player pp 1000`\n"
                    "`!opvp @player rank 5000`\n"
                    "`!opvp @player bg 2000`\n\n"
                    "`!opvp @player duel 1500`\n"
                    "`!opvp @player guess 3000`\n"
                    "`!opvp @player background 1000`",
                inline=False
            )
            
            embed.add_field(
                name="Game Descriptions",
                value="**PP Duel:** Random cards compete - highest effective PP wins!\n"
                    "**Rank Guesser:** Guess mystery player's rank from stats\n"
                    "**Background Guesser:** First to guess song from background wins!",
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
        
        await self._pvp_command(ctx, opponent, game_type, bet_amount)

    @commands.command(name="osupvpstats", aliases=["opvpstats", "pvpstats"])
    async def osu_pvp_stats_prefix(self, ctx: commands.Context):
        await self._pvp_stats_command(ctx)

    # SHARED IMPLEMENTATIONS
    async def _pvp_command(self, ctx, opponent, game_type, bet_amount):
        """Handle PvP challenge"""
        challenger_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        
        # Validation
        if opponent.id == challenger_id:
            await self._send_error(ctx, "You can't challenge yourself!")
            return
        
        if opponent.bot:
            await self._send_error(ctx, "You can't challenge bots!")
            return
        
        if bet_amount <= 0:
            await self._send_error(ctx, "Bet amount must be positive!")
            return
        
        # Check if both players have enough coins
        challenger_data = self.get_user_gacha_data(challenger_id)
        challenged_data = self.get_user_gacha_data(opponent.id)
        
        if challenger_data["currency"] < bet_amount:
            await self._send_error(ctx, f"You only have {challenger_data['currency']:,} coins!")
            return
        
        if challenged_data["currency"] < bet_amount:
            await self._send_error(ctx, f"{opponent.mention} only has {challenged_data['currency']:,} coins!")
            return
        
        # ✅ ADD GAME TYPE ALIASES
        game_aliases = {
            # PP Duel aliases
            "pp": "pp_duel",
            "pp_duel": "pp_duel",
            "ppduel": "pp_duel",
            "duel": "pp_duel",
            
            # Rank Guesser aliases
            "rank": "rank_guesser",
            "rank_guesser": "rank_guesser",
            "rankguesser": "rank_guesser",
            "guess": "rank_guesser",
            "guesser": "rank_guesser",
            
            # Background Guesser aliases
            "bg": "bg_guesser",
            "bg_guesser": "bg_guesser",
            "bgguesser": "bg_guesser",
            "background": "bg_guesser",
            "bgguess": "bg_guesser",
            "beatmap": "bg_guesser"
        }
        
        # Normalize game type (case insensitive)
        game_type_lower = game_type.lower()
        if game_type_lower in game_aliases:
            game_type = game_aliases[game_type_lower]
        else:
            valid_aliases = list(set(game_aliases.keys()))
            await self._send_error(ctx, f"Invalid game type! Available: {', '.join(sorted(valid_aliases))}")
            return
        
        # Create challenge embed
        game_names = {
            "pp_duel": "PP Duel",
            "rank_guesser": "Rank Guesser", 
            "bg_guesser": "Background Guesser"
        }
        
        challenger_name = ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name
        
        embed = discord.Embed(
            title=f"PvP Challenge: {game_names[game_type]}",
            description=f"{challenger_name} challenges {opponent.mention}!\n"
                    f"**Bet:** {bet_amount:,} coins each\n"
                    f"**Game:** {game_names[game_type]}",
            color=discord.Color.orange()
        )
        
        # Add game description
        descriptions = {
            "pp_duel": "Random cards from each collection compete - highest effective PP wins!",
            "rank_guesser": "Guess a mystery player's rank from their stats - closest guess wins!",
            "bg_guesser": "Guess the song from beatmap backgrounds - first correct guess wins!"
        }
        
        embed.add_field(
            name="How to Play",
            value=descriptions[game_type],
            inline=False
        )
        
        embed.set_footer(text=f"{opponent.display_name}, you have 5 minutes to accept!")
        
        # Create view
        view = PvPGamblingView(challenger_id, opponent.id, bet_amount, game_type, self)
        
        if hasattr(ctx, 'response'):
            await ctx.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def _pvp_stats_command(self, ctx):
        """Show PvP statistics"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        pvp_stats = user_data.get("pvp_stats", {})
        
        if not pvp_stats.get("total_games", 0):
            embed = discord.Embed(
                title="PvP Statistics",
                description="You haven't played any PvP games yet!\nUse `/osupvp` to challenge someone!",
                color=discord.Color.blue()
            )
            await self._send_response(ctx, embed)
            return
        
        # Calculate win rate
        total_games = pvp_stats["total_games"]
        wins = pvp_stats["wins"]
        win_rate = (wins / total_games * 100) if total_games > 0 else 0
        
        # Calculate profit
        net_profit = pvp_stats["net_profit"]
        profit_color = discord.Color.green() if net_profit >= 0 else discord.Color.red()
        profit_symbol = "+" if net_profit >= 0 else ""
        
        embed = discord.Embed(
            title="Your PvP Statistics",
            description=f"**Total Games:** {total_games:,}\n**Win Rate:** {win_rate:.1f}%",
            color=profit_color
        )
        
        embed.add_field(
            name="Game Record",
            value=f"**Wins:** {pvp_stats['wins']:,}\n"
                  f"**Losses:** {pvp_stats['losses']:,}\n"
                  f"**Ties:** {pvp_stats['ties']:,}",
            inline=True
        )
        
        embed.add_field(
            name="Financial Summary",
            value=f"**Coins Won:** {pvp_stats['coins_won']:,}\n"
                  f"**Coins Lost:** {pvp_stats['coins_lost']:,}\n"
                  f"**Net Profit:** {profit_symbol}{net_profit:,}",
            inline=True
        )
        
        embed.add_field(
            name="Records",
            value=f"**Biggest Win:** {pvp_stats['biggest_win']:,}\n"
                  f"**Biggest Loss:** {pvp_stats['biggest_loss']:,}",
            inline=True
        )
        
        # Game breakdown
        games_by_type = pvp_stats.get("games_by_type", {})
        if games_by_type:
            game_stats = []
            for game, data in games_by_type.items():
                if data.get("played", 0) > 0:
                    game_win_rate = (data.get("won", 0) / data["played"] * 100)
                    game_name = game.replace("_", " ").title()
                    game_stats.append(f"**{game_name}:** {data['played']} played, {game_win_rate:.1f}% win rate")
            
            if game_stats:
                embed.add_field(
                    name="Game Breakdown",
                    value="\n".join(game_stats),
                    inline=False
                )
        
        await self._send_response(ctx, embed)

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
    await bot.add_cog(OsuPvPCog(bot))