import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
import random
import aiohttp
import io
import os
import json
import difflib
from PIL import Image, ImageFilter
from utils.helpers import *
from utils.config import *

# Import the configuration and system
from .osugacha_config import *
from .osugacha_system import OsuGachaSystem

class PartyBackgroundGuesserView(discord.ui.View):
    """Party Background Guesser - Free for all guessing"""
    
    def __init__(self, party_cog, maps_to_play=None):
        super().__init__(timeout=None)  # No timeout, game manages itself
        self.party_cog = party_cog
        self.maps_to_play = maps_to_play  # None = infinite
        self.maps_played = 0
        self.current_beatmap = None
        self.game_ended = False
        self.channel = None
        self.original_message = None
        self.phase_timer_task = None
        self.message_listener_task = None
        self.no_guess_timer_task = None  # NEW: Timer for no guesses
        self.participant_scores = {}  # {user_id: score}
        self.last_activity = time.time()
        self.phase = 1
        self.activity_timeout = 90  # 1 minute of no messages = game ends
        self.no_guess_timeout = 30  # NEW: 30 seconds with no guesses = skip map
        self.map_start_time = 0  # NEW: Track when current map started
        
    async def start_game(self, ctx):  # Changed from interaction to ctx
        """Start the party background guesser game"""
        self.channel = ctx.channel
        
        # Get first beatmap
        beatmaps = await self.party_cog.get_popular_beatmaps()
        if not beatmaps:
            error_msg = "Could not load beatmaps. Please try again later."
            if hasattr(ctx, 'response'):
                await ctx.response.send_message(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)
            return
            
        # Select first map using global cache
        available_maps = self.party_cog.get_available_beatmaps_global(beatmaps)
        if available_maps:
            self.current_beatmap = random.choice(available_maps)
        else:
            self.current_beatmap = random.choice(beatmaps)
        
        # Track this map in global cache
        self.party_cog.track_new_map_global(self.current_beatmap)
        
        # Create blurred image
        blurred_image = await self.party_cog.create_blurred_background(self.current_beatmap['background_url'])
        
        embed = self._create_game_embed()
        
        # Handle both interaction and context
        if blurred_image:
            file = discord.File(blurred_image, filename="blurred_bg.png")
            embed.set_image(url="attachment://blurred_bg.png")
            
            if hasattr(ctx, 'response'):
                # Slash command
                if ctx.response.is_done():
                    self.original_message = await ctx.edit_original_response(embed=embed, attachments=[file])
                else:
                    await ctx.response.send_message(embed=embed, file=file, view=None)
                    self.original_message = await ctx.original_response()
            else:
                # Prefix command - store the message we send
                self.original_message = await ctx.send(embed=embed, file=file, view=None)
        else:
            embed.add_field(name="Image failed to load", value="Playing without image", inline=False)
            
            if hasattr(ctx, 'response'):
                if ctx.response.is_done():
                    self.original_message = await ctx.edit_original_response(embed=embed)
                else:
                    await ctx.response.send_message(embed=embed, view=None)
                    self.original_message = await ctx.original_response()
            else:
                # Prefix command - store the message we send
                self.original_message = await ctx.send(embed=embed, view=None)
        
        # Start game systems
        self.message_listener_task = asyncio.create_task(self._listen_for_guesses())
        self.phase_timer_task = asyncio.create_task(self._start_phase_timer())
        
    def _create_game_embed(self):
        """Create game embed"""
        title = "Party Background Guesser!"
        if self.maps_to_play:
            description = f"Map {self.maps_played + 1}/{self.maps_to_play} - Phase {self.phase}"
        else:
            description = f"Map {self.maps_played + 1} - Phase {self.phase} (Infinite Mode)"
            
        description += f"\n\n**Type your guess in chat!** (song title or artist)"
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="Current Map Info",
            value=f"{self.current_beatmap['difficulty_rating']}★\n"
                  f"{self.current_beatmap['playcount']:,} plays\n"
                  f"Mapped by {self.current_beatmap['creator']}",
            inline=True
        )
        
        # Show current scores if any
        if self.participant_scores:
            sorted_scores = sorted(self.participant_scores.items(), key=lambda x: x[1], reverse=True)
            score_text = []
            for i, (user_id, score) in enumerate(sorted_scores[:5]):  # Top 5
                user = self.party_cog.bot.get_user(user_id)
                name = user.display_name if user else "Unknown"
                score_text.append(f"{i+1}. {name}: {score}")
            
            embed.add_field(
                name="Current Scores",
                value="\n".join(score_text) if score_text else "No scores yet",
                inline=True
            )
        
        if self.phase == 1:
            phase_text = "Blurred Background"
        elif self.phase == 2:
            phase_text = "Clear Background"
        else:
            phase_text = f"Phase {self.phase}"
            
        embed.set_footer(text=f"{phase_text} - Just type your guess!")
        return embed
    
    def _get_available_beatmaps(self, all_beatmaps):
        """Get beatmaps that haven't been used recently"""
        return self.party_cog.get_available_beatmaps_global(all_beatmaps)

    def _track_new_map(self, beatmap):
        """Track a newly selected map and manage recent maps list"""
        self.party_cog.track_new_map_global(beatmap)
        
    async def _listen_for_guesses(self):
        """Listen for chat messages from anyone"""
        def check(message):
            return (message.channel.id == self.channel.id and
                    not self.game_ended and
                    not message.author.bot and
                    len(message.content.strip()) > 0)
        
        try:
            while not self.game_ended:
                try:
                    # Wait for message with a timeout to check activity periodically
                    message = await asyncio.wait_for(
                        self.party_cog.bot.wait_for('message', check=check),
                        timeout=10.0  # Check every 10 seconds
                    )
                    
                    # Update activity time when we receive a message
                    self.last_activity = time.time()
                    
                    # Check if the guess is correct
                    await self._check_guess(message.author.id, message.content, message)
                        
                except asyncio.TimeoutError:
                    # No message received in 10 seconds, check if we should timeout the game
                    if time.time() - self.last_activity > self.activity_timeout:
                        await self._end_game_timeout()
                        break
                    # Otherwise continue waiting for messages
                    continue
                        
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _no_guess_timeout(self):
        """Handle timeout when no one guesses for 30 seconds"""
        try:
            await asyncio.sleep(self.no_guess_timeout)
            
            if not self.game_ended:
                print(f"⏰ No guess timeout triggered for map {self.maps_played + 1}")
                
                # Send timeout message
                try:
                    timeout_msg = f"⏰ **Time's up!** No one guessed correctly.\n" \
                                f"**Song:** {self.current_beatmap['title']}\n" \
                                f"**Artist:** {self.current_beatmap['artist']}"
                    
                    await self.channel.send(timeout_msg, delete_after=15)
                except:
                    pass
                
                # Small delay then move to next map
                await asyncio.sleep(2)
                
                # Increment maps_played BEFORE checking if game should end
                self.maps_played += 1
                print(f"📊 Maps played: {self.maps_played}/{self.maps_to_play if self.maps_to_play else 'infinite'}")
                
                # Check if game should end (only if we have a map limit)
                if self.maps_to_play and self.maps_played >= self.maps_to_play:
                    print("🏁 Game ending due to map limit reached")
                    await self._end_game_complete()
                else:
                    print("⏭️ Moving to next map...")
                    # Reset the timer task reference to None since this task is ending
                    self.no_guess_timer_task = None
                    # Continue to next map (will automatically avoid recent maps)
                    await self._next_map()
                    
        except asyncio.CancelledError:
            # print("❌ No guess timeout was cancelled (expected when someone guesses correctly)")
            return
        except Exception as e:
            print(f"❌ Error in no_guess_timeout: {e}")
            pass
            
    async def _check_guess(self, guesser_id, guess, message):
        """Check if the guess is correct using improved fuzzy matching"""
        if self.game_ended:
            return

        correct_title = self.current_beatmap['title']
        correct_artist = self.current_beatmap['artist']
        guess_clean = guess.strip()
        
        # Reject very short guesses
        if len(guess_clean) < 3:
            return
        
        def clean_title_for_matching(title):
            """Clean title by removing parentheses content, features, etc."""
            import re
            
            # Convert to lowercase for processing
            cleaned = title.lower()
            
            # Remove content in parentheses (TV Size), (Nightcore), etc.
            cleaned = re.sub(r'\([^)]*\)', '', cleaned)
            
            # Remove content in brackets [Remix], [Extended], etc.
            cleaned = re.sub(r'\[[^\]]*\]', '', cleaned)
            
            # Remove feature mentions and everything after them
            feature_patterns = [
                r'\bfeat\.?\s+.*$',
                r'\bft\.?\s+.*$', 
                r'\bfeaturing\s+.*$',
                r'\bwith\s+.*$',
            ]
            
            for pattern in feature_patterns:
                cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
            
            # Remove common punctuation and normalize spaces
            cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            
            return cleaned.strip()
        
        def clean_artist_for_matching(artist):
            """Clean artist name for matching and split featured artists"""
            import re
            
            cleaned = artist.lower()
            
            # Split by common feature separators and clean each part
            feature_separators = [
                r'\s+feat\.?\s+',
                r'\s+ft\.?\s+', 
                r'\s+featuring\s+',
                r'\s+with\s+',
                r'\s+&\s+',
                r'\s+and\s+',
                r'\s*,\s*'
            ]
            
            # Split the artist string by feature separators
            artists = [cleaned]
            for separator in feature_separators:
                new_artists = []
                for artist_part in artists:
                    new_artists.extend(re.split(separator, artist_part, flags=re.IGNORECASE))
                artists = new_artists
            
            # Clean each artist part
            cleaned_artists = []
            for artist_part in artists:
                # Remove common punctuation and normalize spaces
                clean_part = re.sub(r'[^\w\s]', ' ', artist_part)
                clean_part = re.sub(r'\s+', ' ', clean_part)
                clean_part = clean_part.strip()
                
                if len(clean_part) >= 2:  # Only keep parts with at least 2 characters
                    cleaned_artists.append(clean_part)
            
            return cleaned_artists
        
        def clean_guess_for_matching(guess):
            """Clean user guess for matching"""
            import re
            
            cleaned = guess.lower().strip()
            
            # Remove common punctuation and normalize spaces
            cleaned = re.sub(r'[^\w\s]', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            
            return cleaned.strip()
        
        # Clean all strings for comparison
        clean_title = clean_title_for_matching(correct_title)
        clean_artists = clean_artist_for_matching(correct_artist)  # Now returns a list
        clean_guess = clean_guess_for_matching(guess_clean)
        
        # Skip very short cleaned guesses or common words
        if len(clean_guess) < 3:
            return
        
        common_short_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'man', 'way', 'too', 'any', 'she', 'oil', 'sit', 'set', 'yes', 'not', 'can', 'got', 'let', 'put', 'end', 'why', 'how', 'old', 'see', 'him', 'two', 'how', 'its', 'our', 'out', 'day', 'use', 'her', 'may', 'say', 'she', 'him', 'each', 'which', 'their', 'said', 'will', 'what', 'about', 'they', 'would', 'there', 'could', 'other', 'where', 'when', 'been', 'more', 'very', 'like', 'just', 'into', 'over', 'think', 'also', 'back', 'after', 'first', 'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these', 'give', 'most', 'us'}
        
        if clean_guess in common_short_words:
            return
        
        # Use difflib for fuzzy matching (built-in Python library)
        import difflib
        
        # Calculate similarities for title
        title_similarity = difflib.SequenceMatcher(None, clean_guess, clean_title).ratio()
        
        # Calculate similarities for ALL artist parts (check against each featured artist)
        artist_similarities = []
        for clean_artist in clean_artists:
            similarity = difflib.SequenceMatcher(None, clean_guess, clean_artist).ratio()
            artist_similarities.append(similarity)
        
        # Get the best artist match
        best_artist_similarity = max(artist_similarities) if artist_similarities else 0
        
        # Check for substring matches (partial title matching)
        title_substring_match = False
        if len(clean_guess) >= 4:
            # Check if guess is a substantial part of the title
            if clean_guess in clean_title and len(clean_guess) >= len(clean_title) * 0.4:
                title_substring_match = True
            # Or if title words are found in guess
            title_words = clean_title.split()
            guess_words = clean_guess.split()
            if len(title_words) > 0:
                matched_words = sum(1 for word in title_words if len(word) >= 3 and any(difflib.SequenceMatcher(None, word, gw).ratio() >= 0.85 for gw in guess_words if len(gw) >= 3))
                if matched_words >= len(title_words) * 0.6:  # 60% of title words found
                    title_substring_match = True
        
        # Check for artist match first (now checking against ALL artist parts)
        artist_threshold = 0.80
        is_artist_match = best_artist_similarity >= artist_threshold
        
        # Also check for substring matches in any artist part
        artist_substring_match = False
        if len(clean_guess) >= 4:
            for clean_artist in clean_artists:
                if clean_guess in clean_artist and len(clean_guess) >= len(clean_artist) * 0.4:
                    artist_substring_match = True
                    break
        
        # Combined artist match check
        is_artist_match = is_artist_match or artist_substring_match
        
        # If it's clearly an artist match, give feedback
        if is_artist_match and not title_substring_match and title_similarity < 0.60:
            try:
                await message.add_reaction("🎤")  # Microphone for artist
                await message.reply(f"Great! That's the **artist name** 🎤\nNow, can you guess the **song title**?", delete_after=15)
            except:
                pass
            return
        
        # Check for title match - more lenient thresholds
        title_threshold = 0.75  # Lower threshold for better matching
        partial_threshold = 0.65  # For partial matches
        
        is_title_match = (
            title_similarity >= title_threshold or  # High similarity
            (title_similarity >= partial_threshold and len(clean_guess) >= 5) or  # Decent similarity with longer guess
            title_substring_match  # Substring match
        )
        
        # Additional check: if guess contains most important words from title
        if not is_title_match and len(clean_guess) >= 4:
            title_words = [w for w in clean_title.split() if len(w) >= 3]
            guess_words = [w for w in clean_guess.split() if len(w) >= 3]
            
            if title_words and guess_words:
                # Check if any significant title words are closely matched in the guess
                word_matches = 0
                for title_word in title_words:
                    for guess_word in guess_words:
                        if difflib.SequenceMatcher(None, title_word, guess_word).ratio() >= 0.80:
                            word_matches += 1
                            break
                
                # If we match most of the important words, consider it correct
                if word_matches >= max(1, len(title_words) * 0.6):
                    is_title_match = True
        
        if is_title_match:
            # Cancel no-guess timer since someone got it right
            if self.no_guess_timer_task:
                self.no_guess_timer_task.cancel()
            
            # Update score
            if guesser_id not in self.participant_scores:
                self.participant_scores[guesser_id] = 0
            self.participant_scores[guesser_id] += 1
            
            # Update user stats
            await self._update_party_stats(guesser_id, True)
            
            # React to correct message
            try:
                await message.add_reaction("✅")
            except:
                pass
            
            # Send confirmation message with correct answer
            try:
                guesser = self.party_cog.bot.get_user(guesser_id)
                guesser_name = guesser.display_name if guesser else "Someone"
                
                confirmation_msg = f"🎉 **{guesser_name}** was correct!\n" \
                                f"**Song:** {self.current_beatmap['title']}\n" \
                                f"**Artist:** {self.current_beatmap['artist']}"
                
                await self.channel.send(confirmation_msg, delete_after=20)
            except:
                pass
            
            # Small delay to let people see the confirmation
            await asyncio.sleep(2)

            self.maps_played += 1
            
            # Check if game should end
            if self.maps_to_play and self.maps_played >= self.maps_to_play:
                await self._end_game_complete()
            else:
                await self._next_map()     

    async def _update_party_stats(self, user_id, correct_guess):
        """Update party game statistics"""
        user_data = self.party_cog.get_user_gacha_data(user_id)
        
        if "party_stats" not in user_data:
            user_data["party_stats"] = {
                "bg_guesses_correct": 0,
                "bg_games_won": 0,
                "bg_games_played": 0
            }
        
        stats = user_data["party_stats"]
        
        if correct_guess:
            stats["bg_guesses_correct"] += 1
            
        await self.party_cog.save_user_data()
        

    async def _start_phase_timer(self):
        """Handle phase progression"""
        try:
            # Reset map start time and start no-guess timer
            self.map_start_time = time.time()
            if self.no_guess_timer_task:
                self.no_guess_timer_task.cancel()
            self.no_guess_timer_task = asyncio.create_task(self._no_guess_timeout())
            
            await asyncio.sleep(10)  # Phase 1: 10 seconds blurred
            
            if not self.game_ended:
                await self._progress_to_clear()
                
                # DON'T cancel the no_guess_timer here - let it continue running
                # The timer should run for the ENTIRE map duration (both phases)
                
        except asyncio.CancelledError:
            return
        except Exception:
            pass

    async def _stop_game_manual(self, ctx):
        """Handle manual game stop"""
        self.game_ended = True
        
        # Cancel all timers
        if self.phase_timer_task:
            self.phase_timer_task.cancel()
        if self.message_listener_task:
            self.message_listener_task.cancel()
        if self.no_guess_timer_task:  # NEW
            self.no_guess_timer_task.cancel()
        
        # Remove from active games
        if ctx.channel.id in self.party_cog.active_games:
            del self.party_cog.active_games[ctx.channel.id]
        
        # Update stats for participants
        for user_id in self.participant_scores:
            user_data = self.party_cog.get_user_gacha_data(user_id)
            if "party_stats" not in user_data:
                user_data["party_stats"] = {"bg_guesses_correct": 0, "bg_games_won": 0, "bg_games_played": 0}
            user_data["party_stats"]["bg_games_played"] += 1
        
        await self.party_cog.save_user_data()
        
        embed = discord.Embed(
            title="Party Background Guesser - Game Stopped",
            description="Game was manually stopped",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Final Song",
            value=f"**{self.current_beatmap['title']}** by **{self.current_beatmap['artist']}**\n"
                f"Mapped by {self.current_beatmap['creator']}",
            inline=False
        )
        
        if self.participant_scores:
            sorted_scores = sorted(self.participant_scores.items(), key=lambda x: x[1], reverse=True)
            score_text = []
            for i, (user_id, score) in enumerate(sorted_scores[:10]):
                user = self.party_cog.bot.get_user(user_id)
                name = user.display_name if user else "Unknown"
                score_text.append(f"{i+1}. {name}: {score}")
            
            embed.add_field(
                name="Final Scores",
                value="\n".join(score_text),
                inline=False
            )
        
        embed.add_field(
            name="Stats Updated",
            value=f"Total maps played: {self.maps_played}",
            inline=False
        )
        
        await ctx.send(embed=embed)

    async def _next_map(self):
        """Progress to next map - SEND NEW MESSAGE instead of editing"""
        if self.game_ended:
            return
            
        # Cancel timers (but NOT the message listener - we need it to keep running)
        if self.phase_timer_task:
            self.phase_timer_task.cancel()
        
        # DON'T cancel the no_guess_timer_task here since _no_guess_timeout called this function
        # The task that called this is already finishing, so cancelling it would cause the error
            
        # Get new beatmap (with filtering for recent maps)
        all_beatmaps = await self.party_cog.get_popular_beatmaps()
        if all_beatmaps:
            available_maps = self._get_available_beatmaps(all_beatmaps)
            if available_maps:
                self.current_beatmap = random.choice(available_maps)
                self._track_new_map(self.current_beatmap)  # Track this new map
        
        self.phase = 1
        
        # Show new blurred image
        blurred_image = await self.party_cog.create_blurred_background(self.current_beatmap['background_url'])
        embed = self._create_game_embed()
        
        if blurred_image and not self.game_ended:
            file = discord.File(blurred_image, filename="new_blurred_bg.png")
            embed.set_image(url="attachment://new_blurred_bg.png")
            
            try:
                self.original_message = await self.channel.send(embed=embed, file=file)
            except Exception:
                pass
        
        # Start new phase timer (which will create a new no_guess_timer)
        self.phase_timer_task = asyncio.create_task(self._start_phase_timer())
            
    async def _progress_to_clear(self):
        """Show clear background - SEND NEW MESSAGE instead of editing"""
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
                        
                        image = Image.open(io.BytesIO(image_data))
                        image = image.resize((400, 300))
                        
                        img_bytes = io.BytesIO()
                        image.save(img_bytes, format='PNG')
                        img_bytes.seek(0)
                        
                        embed = self._create_game_embed()
                        file = discord.File(img_bytes, filename="clear_bg.png")
                        embed.set_image(url="attachment://clear_bg.png")
                        
                        if self.game_ended:
                            return
                        
                        try:
                            # SEND NEW MESSAGE instead of editing
                            self.original_message = await self.channel.send(embed=embed, file=file)
                        except Exception:
                            pass
                                
        except Exception:
            pass
            
    async def _end_game_timeout(self):
        """Handle game timeout due to inactivity"""
        self.game_ended = True
        
        # Cancel all timers
        if self.phase_timer_task:
            self.phase_timer_task.cancel()
        if self.message_listener_task:
            self.message_listener_task.cancel()
        if self.no_guess_timer_task:  # NEW
            self.no_guess_timer_task.cancel()
        
        # Remove from active games
        if self.channel.id in self.party_cog.active_games:
            del self.party_cog.active_games[self.channel.id]
            
        # Update stats for participants
        for user_id in self.participant_scores:
            user_data = self.party_cog.get_user_gacha_data(user_id)
            if "party_stats" not in user_data:
                user_data["party_stats"] = {"bg_guesses_correct": 0, "bg_games_won": 0, "bg_games_played": 0}
            user_data["party_stats"]["bg_games_played"] += 1
        
        await self.party_cog.save_user_data()
        
        embed = discord.Embed(
            title="Party Background Guesser - Game Ended",
            description="Game ended due to inactivity (1 minute without guesses)",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Final Song",
            value=f"**{self.current_beatmap['title']}** by **{self.current_beatmap['artist']}**\n"
                  f"Mapped by {self.current_beatmap['creator']}",
            inline=False
        )
        
        if self.participant_scores:
            sorted_scores = sorted(self.participant_scores.items(), key=lambda x: x[1], reverse=True)
            score_text = []
            for i, (user_id, score) in enumerate(sorted_scores[:10]):
                user = self.party_cog.bot.get_user(user_id)
                name = user.display_name if user else "Unknown"
                score_text.append(f"{i+1}. {name}: {score}")
            
            embed.add_field(
                name="Final Scores",
                value="\n".join(score_text),
                inline=False
            )
        
        embed.add_field(
            name="Stats Updated",
            value=f"Total maps played: {self.maps_played}",
            inline=False
        )
        
        await self.channel.send(embed=embed)
        
    async def _end_game_complete(self):
        """Handle game completion"""
        self.game_ended = True
        
        if self.phase_timer_task:
            self.phase_timer_task.cancel()
        if self.message_listener_task:
            self.message_listener_task.cancel()
        if self.no_guess_timer_task: 
            self.no_guess_timer_task.cancel()
        
        # Remove from active games
        if self.channel.id in self.party_cog.active_games:
            del self.party_cog.active_games[self.channel.id]
            
        # Determine winner and update stats
        winner_id = None
        if self.participant_scores:
            sorted_scores = sorted(self.participant_scores.items(), key=lambda x: x[1], reverse=True)
            if sorted_scores and sorted_scores[0][1] > 0:
                winner_id = sorted_scores[0][0]
        
        # Update stats for all participants
        for user_id in self.participant_scores:
            user_data = self.party_cog.get_user_gacha_data(user_id)
            if "party_stats" not in user_data:
                user_data["party_stats"] = {"bg_guesses_correct": 0, "bg_games_won": 0, "bg_games_played": 0}
            
            user_data["party_stats"]["bg_games_played"] += 1
            if user_id == winner_id:
                user_data["party_stats"]["bg_games_won"] += 1
        
        await self.party_cog.save_user_data()
        
        embed = discord.Embed(
            title="Party Background Guesser - Game Complete!",
            description=f"Game completed after {self.maps_played} maps!",
            color=discord.Color.gold()
        )
        
        if self.participant_scores:
            sorted_scores = sorted(self.participant_scores.items(), key=lambda x: x[1], reverse=True)
            
            if winner_id:
                winner = self.party_cog.bot.get_user(winner_id)
                winner_name = winner.display_name if winner else "Unknown"
                embed.add_field(
                    name="Winner",
                    value=f"**{winner_name}** with {sorted_scores[0][1]} correct guesses!",
                    inline=False
                )
            
            score_text = []
            for i, (user_id, score) in enumerate(sorted_scores[:10]):
                user = self.party_cog.bot.get_user(user_id)
                name = user.display_name if user else "Unknown"
                score_text.append(f"{i+1}. {name}: {score}")
            
            embed.add_field(
                name="Final Scores",
                value="\n".join(score_text),
                inline=False
            )
        
        await self.channel.send(embed=embed)

class OsuPartyGamesCog(commands.Cog, name="Osu Party Games"):
    """Party games for multiple players"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Use shared gacha system
        if hasattr(bot, 'gacha_system'):
            self.gacha_system = bot.gacha_system
        else:
            from .osugacha_system import OsuGachaSystem
            self.gacha_system = OsuGachaSystem()
            bot.gacha_system = self.gacha_system
        
        # Beatmap cache (shared with PvP cog if it exists)
        self.popular_beatmaps = []
        self.beatmap_cache_time = 0
        self.cache_duration = 2592000  # 24 hours
        self.cache_file = 'data/party_beatmaps_cache.json' 
        
        # Global recent maps cache (persistent across games)
        self.global_recent_maps = []
        self.max_global_recent_maps = 50  # Track last 50 maps globally
        self.recent_maps_file = 'data/party_recent_maps.json'
        
        # Load cache from file on startup
        self._load_beatmap_cache()
        self._load_recent_maps_cache()

        # Active games
        self.active_games = {}  # {channel_id: game_view}

    def _load_recent_maps_cache(self):
        """Load recent maps cache from file"""
        try:
            if os.path.exists(self.recent_maps_file):
                with open(self.recent_maps_file, 'r') as f:
                    cache_data = json.load(f)
                    self.global_recent_maps = cache_data.get('recent_maps', [])
                    print(f"✅ Loaded {len(self.global_recent_maps)} recent maps from cache")
        except Exception as e:
            print(f"⚠️ Failed to load recent maps cache: {e}")
            self.global_recent_maps = []

    def _save_recent_maps_cache(self):
        """Save recent maps cache to file"""
        try:
            cache_data = {
                'recent_maps': self.global_recent_maps,
                'timestamp': time.time()
            }
            
            os.makedirs('data', exist_ok=True)
            with open(self.recent_maps_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            print(f"⚠️ Failed to save recent maps cache: {e}")

    def get_available_beatmaps_global(self, all_beatmaps):
        """Get beatmaps that haven't been used recently (global cache)"""
        if not all_beatmaps:
            return []
        
        # Filter out recently used maps from global cache
        available_maps = [
            beatmap for beatmap in all_beatmaps 
            if beatmap['id'] not in self.global_recent_maps
        ]
        
        # If we've exhausted most maps, reset to keep only last 50
        if len(available_maps) < len(all_beatmaps) * 0.1:  # Less than 10% available
            print("⚠️ Most maps have been used recently, resetting global recent maps cache")
            self.global_recent_maps = self.global_recent_maps[-50:]  # Keep only last 50
            self._save_recent_maps_cache()
            available_maps = [
                beatmap for beatmap in all_beatmaps 
                if beatmap['id'] not in self.global_recent_maps
            ]
        
        return available_maps

    def track_new_map_global(self, beatmap):
        """Track a newly selected map in global cache"""
        self.global_recent_maps.append(beatmap['id'])
        
        # Keep only the last N maps
        if len(self.global_recent_maps) > self.max_global_recent_maps:
            self.global_recent_maps = self.global_recent_maps[-self.max_global_recent_maps:]
        
        # Save to file
        self._save_recent_maps_cache()

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
        """Save user data"""
        save_json(FILE_PATHS["gacha_data"], self.bot.osu_gacha_data)

    def _load_beatmap_cache(self):
        """Load beatmap cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    
                # Check if cache is still valid
                cache_age = time.time() - cache_data.get('timestamp', 0)
                if cache_age < self.cache_duration:
                    self.popular_beatmaps = cache_data.get('beatmaps', [])
                    self.beatmap_cache_time = cache_data.get('timestamp', 0)
                    print(f"✅ Loaded {len(self.popular_beatmaps)} beatmaps from party cache file")
                else:
                    print("⚠️ Party beatmap cache expired, will rebuild on first use")
        except Exception as e:
            print(f"⚠️ Failed to load party beatmap cache: {e}")

    def _save_beatmap_cache(self):
        """Save beatmap cache to file"""
        try:
            cache_data = {
                'beatmaps': self.popular_beatmaps,
                'timestamp': self.beatmap_cache_time
            }
            
            os.makedirs('data', exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
            print("💾 Saved party beatmap cache to disk")
        except Exception as e:
            print(f"⚠️ Failed to save party beatmap cache: {e}")

    async def get_popular_beatmaps(self):
        """Get popular beatmaps from osu! API - 5000 UNIQUE MAPSETS using subcategories"""
        if (self.popular_beatmaps and 
            time.time() - self.beatmap_cache_time < self.cache_duration):
            return self.popular_beatmaps
        
        try:
            token = await self.gacha_system.get_access_token()
            if not token:
                return []
            
            headers = {'Authorization': f'Bearer {token}'}
            beatmaps = []
            seen_beatmapsets = set()  # Track unique beatmapset IDs globally
            
            print("🎵 Caching unique popular beatmaps using subcategories...")
            
            # Create comprehensive search configurations with subcategories
            search_configs = [
                # Year-based searches (most diversity)
                {'sort': 'plays_desc', 'q': '2024', 's': 'ranked', 'pages': 25},
                {'sort': 'plays_desc', 'q': '2023', 's': 'ranked', 'pages': 25},
                {'sort': 'plays_desc', 'q': '2022', 's': 'ranked', 'pages': 25},
                {'sort': 'plays_desc', 'q': '2021', 's': 'ranked', 'pages': 25},
                {'sort': 'plays_desc', 'q': '2020', 's': 'ranked', 'pages': 25},
                {'sort': 'plays_desc', 'q': '2019', 's': 'ranked', 'pages': 25},
                {'sort': 'plays_desc', 'q': '2018', 's': 'ranked', 'pages': 25},
                {'sort': 'plays_desc', 'q': '2017', 's': 'ranked', 'pages': 20},
                {'sort': 'plays_desc', 'q': '2016', 's': 'ranked', 'pages': 20},
                {'sort': 'plays_desc', 'q': '2015', 's': 'ranked', 'pages': 15},
                
                # Status-based searches
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'pages': 20},
                {'sort': 'plays_desc', 'q': '', 's': 'approved', 'pages': 15},
                {'sort': 'plays_desc', 'q': '', 's': 'loved', 'pages': 30},
                
                # Genre + year combinations
                {'sort': 'plays_desc', 'q': 'anime 2023', 's': 'ranked', 'pages': 20},
                {'sort': 'plays_desc', 'q': 'anime 2022', 's': 'ranked', 'pages': 20},
                {'sort': 'plays_desc', 'q': 'anime 2021', 's': 'ranked', 'pages': 15},
                {'sort': 'plays_desc', 'q': 'rock 2023', 's': 'ranked', 'pages': 15},
                {'sort': 'plays_desc', 'q': 'rock 2022', 's': 'ranked', 'pages': 15},
                {'sort': 'plays_desc', 'q': 'electronic 2023', 's': 'ranked', 'pages': 15},
                {'sort': 'plays_desc', 'q': 'electronic 2022', 's': 'ranked', 'pages': 15},
                {'sort': 'plays_desc', 'q': 'pop 2023', 's': 'ranked', 'pages': 15},
                {'sort': 'plays_desc', 'q': 'pop 2022', 's': 'ranked', 'pages': 15},
                
                # Language-based searches
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'l': '2', 'pages': 20},  # English
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'l': '3', 'pages': 20},  # Japanese
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'l': '4', 'pages': 15},  # Chinese
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'l': '6', 'pages': 15},  # Korean
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'l': '8', 'pages': 10},  # German
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'l': '10', 'pages': 10}, # Spanish
                
                # Genre-based searches
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'g': '1', 'pages': 20},  # Unspecified
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'g': '2', 'pages': 15},  # Video Game
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'g': '3', 'pages': 20},  # Anime
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'g': '4', 'pages': 15},  # Rock
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'g': '5', 'pages': 15},  # Pop
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'g': '6', 'pages': 10},  # Other
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'g': '7', 'pages': 10},  # Novelty
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'g': '9', 'pages': 15},  # Hip Hop
                {'sort': 'plays_desc', 'q': '', 's': 'ranked', 'g': '10', 'pages': 15}, # Electronic
                
                # Different sort methods with subcategories
                {'sort': 'rating_desc', 'q': '2023', 's': 'ranked', 'pages': 20},
                {'sort': 'rating_desc', 'q': '2022', 's': 'ranked', 'pages': 20},
                {'sort': 'rating_desc', 'q': '', 's': 'loved', 'pages': 25},
                {'sort': 'favourites_desc', 'q': '2023', 's': 'ranked', 'pages': 20},
                {'sort': 'favourites_desc', 'q': '2022', 's': 'ranked', 'pages': 20},
                {'sort': 'relevance_desc', 'q': 'anime', 's': 'ranked', 'pages': 20},
                {'sort': 'relevance_desc', 'q': 'electronic', 's': 'ranked', 'pages': 15},
                
                # Difficulty-based searches
                {'sort': 'plays_desc', 'q': 'stars>6', 's': 'ranked', 'pages': 15},
                {'sort': 'plays_desc', 'q': 'stars>5 stars<6', 's': 'ranked', 'pages': 20},
                {'sort': 'plays_desc', 'q': 'stars>4 stars<5', 's': 'ranked', 'pages': 20},
                {'sort': 'plays_desc', 'q': 'stars>3 stars<4', 's': 'ranked', 'pages': 20},
                {'sort': 'plays_desc', 'q': 'stars<3', 's': 'ranked', 'pages': 15},
                
                # Combination searches for maximum diversity
                {'sort': 'plays_desc', 'q': 'anime 2023', 's': 'loved', 'pages': 15},
                {'sort': 'plays_desc', 'q': 'rock 2022', 's': 'loved', 'pages': 15},
                {'sort': 'rating_desc', 'q': 'electronic', 's': 'approved', 'pages': 10},
                {'sort': 'favourites_desc', 'q': 'pop', 's': 'approved', 'pages': 10},
            ]
            
            async with aiohttp.ClientSession() as session:
                url = 'https://osu.ppy.sh/api/v2/beatmapsets/search'
                
                for i, config in enumerate(search_configs):
                    if len(beatmaps) >= 5000:
                        break
                    
                    search_desc = f"{config['sort']} q='{config['q']}' s={config['s']}"
                    if 'g' in config:
                        search_desc += f" genre={config['g']}"
                    if 'l' in config:
                        search_desc += f" lang={config['l']}"
                        
                    print(f"🔄 [{i+1}/{len(search_configs)}] Fetching: {search_desc}")
                    
                    params = {
                        'q': config['q'],
                        's': config['s'],
                        'sort': config['sort'],
                        'limit': 50
                    }
                    
                    # Add optional parameters
                    if 'g' in config:
                        params['g'] = config['g']
                    if 'l' in config:
                        params['l'] = config['l']
                    
                    maps_from_this_search = 0
                    page = 0
                    consecutive_empty_pages = 0
                    
                    while page < config['pages'] and len(beatmaps) < 5000:
                        params['offset'] = page * 50
                        
                        try:
                            async with session.get(url, headers=headers, params=params) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    
                                    if not data.get('beatmapsets'):
                                        consecutive_empty_pages += 1
                                        if consecutive_empty_pages >= 3:  # Stop after 3 empty pages
                                            break
                                        page += 1
                                        continue
                                    
                                    consecutive_empty_pages = 0
                                    page_found_new = False
                                    
                                    for beatmapset in data.get('beatmapsets', []):
                                        if beatmapset.get('beatmaps'):
                                            beatmapset_id = beatmapset['id']
                                            
                                            # Skip if we've already seen this beatmapset
                                            if beatmapset_id in seen_beatmapsets:
                                                continue
                                            
                                            seen_beatmapsets.add(beatmapset_id)
                                            page_found_new = True
                                            maps_from_this_search += 1
                                            
                                            # Get the hardest difficulty (highest star rating)
                                            hardest_diff = max(beatmapset['beatmaps'], 
                                                            key=lambda x: x.get('difficulty_rating', 0))
                                            
                                            # Skip maps with less than 1 million plays
                                            playcount = hardest_diff.get('playcount', 0)
                                            if playcount < 1000000:
                                                continue
                                            
                                            beatmap = {
                                                'id': hardest_diff['id'],
                                                'beatmapset_id': beatmapset_id,
                                                'title': beatmapset['title'],
                                                'artist': beatmapset['artist'],
                                                'creator': beatmapset['creator'],
                                                'difficulty_rating': round(hardest_diff.get('difficulty_rating', 0), 2),
                                                'playcount': hardest_diff.get('playcount', 0),
                                                'background_url': f"https://assets.ppy.sh/beatmaps/{beatmapset_id}/covers/raw.jpg"
                                            }
                                            beatmaps.append(beatmap)
                                            
                                            # Stop if we've reached our target
                                            if len(beatmaps) >= 5000:
                                                break
                                    
                                    # If we didn't find any new maps on this page, skip ahead
                                    if not page_found_new:
                                        page += 5  # Skip ahead more aggressively
                                    else:
                                        page += 1
                                
                                elif response.status == 429:  # Rate limited
                                    print("⚠️ Rate limited, waiting 5 seconds...")
                                    await asyncio.sleep(5)
                                    continue
                                else:
                                    print(f"❌ API error: {response.status}")
                                    break
                                    
                        except Exception as e:
                            print(f"⚠️ Error in search {i+1}: {e}")
                            break
                        
                        await asyncio.sleep(0.1)  # Small delay between requests
                    
                    print(f"✅ Found {maps_from_this_search} unique maps from this search (total: {len(beatmaps)})")
                    
                    # Progress update every 10 searches
                    if (i + 1) % 10 == 0:
                        print(f"🎯 Progress: {len(beatmaps)}/5000 unique beatmapsets cached")
            
            self.popular_beatmaps = beatmaps
            self.beatmap_cache_time = time.time()
            self._save_beatmap_cache()
            
            print(f"✅ Final result: Cached {len(beatmaps)} unique mapsets for party games using subcategories")
            
            return beatmaps
            
        except Exception as e:
            print(f"❌ Failed to fetch party beatmaps: {e}")
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
            print(f"Failed to create blurred background: {e}")
            return None

    # SLASH COMMANDS
    @app_commands.command(name="osuparty", description="Start party background guesser game")
    @app_commands.describe(maps="Number of maps to play (leave empty for infinite)")
    async def osu_party_slash(self, interaction: discord.Interaction, maps: int = None):
        await self._party_command(interaction, "bg", maps)

    @app_commands.command(name="opartystats", description="View your party game statistics")
    @app_commands.describe(user="User to check stats for (optional)")
    async def osu_party_stats_slash(self, interaction: discord.Interaction, user: discord.Member = None):
        await self._party_stats_command(interaction, user)

    @app_commands.command(name="opartyleaderboard", description="View party game leaderboards")
    @app_commands.describe(stat_type="Type of leaderboard to show")
    @app_commands.choices(stat_type=[
        app_commands.Choice(name="Background Guesses (Total Correct)", value="bg_guesses"),
        app_commands.Choice(name="Game Wins", value="wins"),
    ])
    async def osu_party_leaderboard_slash(self, interaction: discord.Interaction, stat_type: str = "bg_guesses"):
        await self._party_leaderboard_command(interaction, stat_type)

    # PREFIX COMMANDS
    @commands.command(name="osuparty", aliases=["op", "party"])
    async def osu_party_prefix(self, ctx: commands.Context, game_type: str = "bg", maps_or_action = None):
        # Handle stop commands
        if game_type.lower() in ["stop", "s"] or (isinstance(maps_or_action, str) and maps_or_action.lower() in ["stop", "s"]):
            await self._party_command(ctx, "bg", "stop")
            return
        
        if game_type.lower() not in ["bg", "background"]:
            from utils.helpers import show_command_usage
            await show_command_usage(
                ctx, "osuparty",
                description="Start a party background guesser game! 🎵",
                usage_examples=[
                    f"{COMMAND_PREFIX}op bg",
                    f"{COMMAND_PREFIX}party bg 10",
                    f"{COMMAND_PREFIX}op bg stop"
                ],
                subcommands={
                    "bg/background": "Background guesser game",
                    "stop/s": "Stop current game"
                },
                notes=[
                    "Type song titles or artists in chat to guess",
                    "+1 point per correct guess",
                    "Game auto-ends after 1 minute of no activity",
                    "Use numbers to limit maps (e.g., 'bg 10')"
                ]
            )
            return
        
        # Convert maps_or_action to int if it's a number
        maps = None
        if maps_or_action is not None:
            try:
                maps = int(maps_or_action)
            except ValueError:
                if maps_or_action.lower() in ["stop", "s"]:
                    await self._party_command(ctx, game_type, "stop")
                    return
                else:
                    await self._send_error(ctx, f"Invalid parameter: {maps_or_action}. Use a number or 'stop'.")
                    return
        
        await self._party_command(ctx, game_type, maps)

    @commands.command(name="opartystats", aliases=["opstats"])
    async def osu_party_stats_prefix(self, ctx: commands.Context, user: discord.Member = None):
        await self._party_stats_command(ctx, user)

    @commands.command(name="opartyleaderboard", aliases=["opleaderboard", "oplb"])
    async def osu_party_leaderboard_prefix(self, ctx: commands.Context, stat_type: str = "bg_guesses"):
        await self._party_leaderboard_command(ctx, stat_type)

    # SHARED IMPLEMENTATIONS
    async def _party_command(self, ctx, game_type, maps):
        """Handle party game command"""
        channel_id = ctx.channel.id

            # Handle stop command
        if isinstance(maps, str) and maps.lower() in ["stop", "s"]:
            if channel_id not in self.active_games:
                await self._send_error(ctx, "No party game is running in this channel!")
                return
        
            # Check if user has permission to stop (optional: only allow game starter or admins)
            game_view = self.active_games[channel_id]
            await game_view._stop_game_manual(ctx)
            return
        
        # Check if game already running in this channel
        if channel_id in self.active_games:
            await self._send_error(ctx, "A party game is already running in this channel!")
            return
        
        if maps is not None and maps <= 0:
            await self._send_error(ctx, "Number of maps must be positive!")
            return
        
        if maps is not None and maps > 100:
            await self._send_error(ctx, "Maximum 100 maps per game!")
            return
        
        # Determine if this is a slash command (interaction) or prefix command
        is_interaction = hasattr(ctx, 'response')
        
        # Defer response for slash commands only
        if is_interaction and not ctx.response.is_done():
            await ctx.response.defer()
        
        # Check if we need to cache beatmaps
        needs_caching = (not self.popular_beatmaps or 
                        time.time() - self.beatmap_cache_time > self.cache_duration)
        
        if needs_caching:
            # Show caching message
            embed = discord.Embed(
                title="Party Background Guesser - Loading",
                description="Caching popular beatmaps from osu! API...\n\n"
                        "This may take 10-30 seconds for the first game.\n"
                        "Future games will be instant!",
                color=discord.Color.blue()
            )
            
            if is_interaction:
                await ctx.edit_original_response(embed=embed)
            else:
                # For prefix commands, send a regular message
                loading_msg = await ctx.send(embed=embed)
        
        # Get popular beatmaps
        beatmaps = await self.get_popular_beatmaps()
        if not beatmaps:
            embed = discord.Embed(
                title="Error",
                description="Could not load beatmaps. Please try again later.",
                color=discord.Color.red()
            )
            
            if is_interaction:
                await ctx.edit_original_response(embed=embed)
            else:
                if 'loading_msg' in locals():
                    await loading_msg.edit(embed=embed)
                else:
                    await ctx.send(embed=embed)
            return
        
        # Create and start game
        view = PartyBackgroundGuesserView(self, maps)
        self.active_games[channel_id] = view
        
        try:
            await view.start_game(ctx)
        except Exception as e:
            if channel_id in self.active_games:
                del self.active_games[channel_id]
            raise e

    async def _party_stats_command(self, ctx, target_user):
        """Show party game statistics"""
        if target_user is None:
            user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
            display_name = ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name
            is_self = True
        else:
            user_id = target_user.id
            display_name = target_user.display_name
            is_self = (target_user.id == (ctx.author.id if hasattr(ctx, 'author') else ctx.user.id))

        user_data = self.get_user_gacha_data(user_id)
        party_stats = user_data.get("party_stats", {})
        
        bg_guesses = party_stats.get("bg_guesses_correct", 0)
        bg_wins = party_stats.get("bg_games_won", 0)
        bg_games = party_stats.get("bg_games_played", 0)
        
        if bg_games == 0:
            pronoun = "You haven't" if is_self else f"{display_name} hasn't"
            embed = discord.Embed(
                title=f"{'Your' if is_self else f'{display_name}\'s'} Party Game Statistics",
                description=f"{pronoun} played any party games yet!\nUse `/osuparty` to start a game!",
                color=discord.Color.blue()
            )
            await self._send_response(ctx, embed)
            return
        
        win_rate = (bg_wins / bg_games * 100) if bg_games > 0 else 0
        avg_guesses = (bg_guesses / bg_games) if bg_games > 0 else 0
        
        embed = discord.Embed(
            title=f"{'Your' if is_self else f'{display_name}\'s'} Party Game Statistics",
            description=f"**Games Played:** {bg_games:,}\n**Games Won:** {bg_wins:,}\n**Win Rate:** {win_rate:.1f}%",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="Background Guesser Stats",
            value=f"**Total Correct Guesses:** {bg_guesses:,}\n"
                  f"**Average Guesses per Game:** {avg_guesses:.1f}",
            inline=False
        )
        
        if is_self:
            embed.set_footer(text="Keep playing to improve your stats!")
        else:
            embed.set_footer(text=f"Party game statistics for {display_name}")
        
        await self._send_response(ctx, embed)

    async def _party_leaderboard_command(self, ctx, stat_type):
        """Show party game leaderboards"""
        all_users = []
        
        for user_id_str, user_data in self.bot.osu_gacha_data.items():
            party_stats = user_data.get("party_stats", {})
            
            if stat_type == "bg_guesses":
                value = party_stats.get("bg_guesses_correct", 0)
            elif stat_type == "wins":
                value = party_stats.get("bg_games_won", 0)
            else:
                value = 0
            
            if value > 0:
                all_users.append((int(user_id_str), value))
        
        if not all_users:
            embed = discord.Embed(
                title="Party Game Leaderboard",
                description="No party game stats recorded yet!\nUse `/osuparty` to start playing!",
                color=discord.Color.blue()
            )
            await self._send_response(ctx, embed)
            return
        
        # Sort by value (descending)
        all_users.sort(key=lambda x: x[1], reverse=True)
        
        # Create leaderboard embed
        if stat_type == "bg_guesses":
            title = "Background Guesses Leaderboard"
            value_name = "Correct Guesses"
        elif stat_type == "wins":
            title = "Party Game Wins Leaderboard"
            value_name = "Games Won"
        else:
            title = "Party Game Leaderboard"
            value_name = "Score"
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.gold()
        )
        
        leaderboard_text = []
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_rank = None
        
        for i, (uid, value) in enumerate(all_users[:10]):  # Top 10
            user = self.bot.get_user(uid)
            name = user.display_name if user else "Unknown"
            
            # Add rank emoji for top 3
            if i == 0:
                rank_emoji = "🥇"
            elif i == 1:
                rank_emoji = "🥈"
            elif i == 2:
                rank_emoji = "🥉"
            else:
                rank_emoji = f"{i+1}."
            
            leaderboard_text.append(f"{rank_emoji} **{name}** - {value:,}")
            
            if uid == user_id:
                user_rank = i + 1
        
        embed.description = "\n".join(leaderboard_text)
        
        # Show user's rank if not in top 10
        if user_rank is None:
            for i, (uid, value) in enumerate(all_users):
                if uid == user_id:
                    user_rank = i + 1
                    user_value = value
                    embed.set_footer(text=f"Your rank: #{user_rank:,} with {user_value:,} {value_name.lower()}")
                    break
        elif user_rank <= 10:
            embed.set_footer(text=f"You're rank #{user_rank}!")
        
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
            if ctx.response.is_done():
                await ctx.edit_original_response(embed=embed)
            else:
                await ctx.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(OsuPartyGamesCog(bot))