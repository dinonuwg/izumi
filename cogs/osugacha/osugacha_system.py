import discord
from discord.ext import commands
import aiohttp
import asyncio
import random
import math
import time
import json
from datetime import datetime, timezone, timedelta
from utils.helpers import *
from utils.config import *
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from io import BytesIO
import os #os

# Import all the configuration
from .osugacha_config import *

class OsuGachaSystem:
    """Core gacha system with all game logic and functionality"""
    
    def __init__(self, bot=None):
        self.bot = bot

        # API credentials from config
        self.client_id = API_CONFIG["client_id"]
        self.client_secret = API_CONFIG["client_secret"]
        
        self.access_token = None
        self.token_expires_at = 0
        
        # Enhanced caching for 10k players
        self.leaderboard_cache = []
        self.leaderboard_cache_time = 0
        self.leaderboard_cache_duration = GAME_CONFIG["cache_duration"]
        self.player_cache = {}
        self.player_cache_duration = GAME_CONFIG["cache_duration"]

        self.cache_file = FILE_PATHS["cache_file"]
        self._load_cache_from_disk()
        self._cache_building = False
        
        # Load configurations from config file
        self.mutations = MUTATIONS
        self.flashback_cards = FLASHBACK_CARDS
        self.store_config = STORE_CONFIG
        self.daily_config = DAILY_CONFIG
        self.store_descriptions = STORE_DESCRIPTIONS
        self.crate_config = CRATE_CONFIG
        self.rarity_config = RARITY_CONFIG
        self.achievement_definitions = ACHIEVEMENT_DEFINITIONS

            # ADD: Image optimization
        self._font_cache = {}
        self._background_cache = {}
        self._profile_cache = {}

        # Cooldown system
        self.user_cooldowns = {}
        self.crate_cooldown = GAME_CONFIG["crate_cooldown"]

            # ADD: Race condition protection
        self._cache_lock = asyncio.Lock()
        self._achievement_lock = asyncio.Lock()
        self._cooldown_lock = asyncio.Lock()

    def _load_cache_from_disk(self):
        """Load leaderboard cache from disk"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    
                # Check if cache is still valid
                cache_age = time.time() - cache_data.get('timestamp', 0)
                if cache_age < self.leaderboard_cache_duration:
                    self.leaderboard_cache = cache_data.get('players', [])
                    self.leaderboard_cache_time = cache_data.get('timestamp', 0)
                    print(f"✅ Loaded {len(self.leaderboard_cache)} players from cache file")
                else:
                    print("⚠️ Cache file expired, will rebuild on first use")
        except Exception as e:
            print(f"⚠️ Failed to load cache from disk: {e}")

    def _save_cache_to_disk(self):
        """Save leaderboard cache to disk"""
        try:
            cache_data = {
                'players': self.leaderboard_cache,
                'timestamp': self.leaderboard_cache_time
            }
            
            os.makedirs('data', exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
            print("💾 Saved leaderboard cache to disk")
        except Exception as e:
            print(f"⚠️ Failed to save cache to disk: {e}")

    async def get_access_token(self):
        """Get access token from osu! API v2"""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        async with aiohttp.ClientSession() as session:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials',
                'scope': 'public'
            }
            
            async with session.post('https://osu.ppy.sh/oauth/token', data=data) as response:
                if response.status != 200:
                    raise Exception(f"Token request failed: {response.status}")
                
                token_data = await response.json()
                self.access_token = token_data['access_token']
                self.token_expires_at = time.time() + token_data['expires_in'] - API_CONFIG["token_buffer_seconds"]
                return self.access_token

    async def get_access_token_with_retry(self, retries=3):
        """Get access token with retry logic"""
        for attempt in range(retries):
            try:
                return await self.get_access_token()
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                await asyncio.sleep(API_CONFIG["retry_delays"][attempt])
        return None

    async def build_leaderboard_cache(self):
        """Build aggressive cache of top 10k players with race condition protection"""
        async with self._cache_lock:
            if self.leaderboard_cache and (time.time() - self.leaderboard_cache_time) < self.leaderboard_cache_duration:
                return self.leaderboard_cache
            
            token = await self.get_access_token_with_retry()
            if not token:
                raise Exception("API not responding, try again later")
                
            leaderboard = []
            
            print(f"🔄 Building cache for {API_CONFIG['max_pages']} pages (up to ~{API_CONFIG['max_pages'] * 50} players)")
            
            try:
                headers = {'Authorization': f'Bearer {token}'}
                
                for page in range(1, API_CONFIG["max_pages"] + 1):
                    # Log progress every 100 pages DURING the actual requests
                    if page % 10 == 0:
                        print(f"📊 Progress: {page}/{API_CONFIG['max_pages']} pages ({len(leaderboard)} players cached so far)")
                    
                    url = f'https://osu.ppy.sh/api/v2/rankings/osu/performance'
                    params = {'page': page}
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, params=params) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                for user_data in data.get('ranking', []):
                                    user_info = user_data.get('user', {})
                                    
                                    player = {
                                        "user_id": str(user_info.get('id', 0)),
                                        "username": user_info.get('username', 'Unknown'),
                                        "rank": user_data.get('global_rank', 0),
                                        "pp": round(float(user_data.get('pp', 0)), 2),
                                        "accuracy": round(float(user_data.get('hit_accuracy', 0)), 2),
                                        "play_count": int(user_data.get('play_count', 0)),
                                        "country": user_info.get('country_code', 'XX'),
                                        "level": round(float(user_data.get('level', {}).get('current', 0)), 2),
                                        "profile_picture": user_info.get('avatar_url', f"https://a.ppy.sh/{user_info.get('id', 0)}")
                                    }
                                    leaderboard.append(player)
                            else:
                                print(f"❌ API error on page {page}: Status {response.status}")
                                if response.status == 429:  # Rate limited
                                    print("⚠️ Rate limited, waiting 5 seconds...")
                                    await asyncio.sleep(5)
                                    continue
                                else:
                                    raise Exception(f"API error: {response.status}")
                    
                    await asyncio.sleep(API_CONFIG["request_delay"])
                    
            except Exception as e:
                print(f"❌ Cache build failed: {e}")
                raise Exception("API not responding, try again later")
            
            print(f"✅ Cache build complete! Cached {len(leaderboard)} players")
            
            self.leaderboard_cache = leaderboard
            self.leaderboard_cache_time = time.time()
            self._save_cache_to_disk()
            return leaderboard

    async def build_leaderboard_cache_with_retry(self, retries=3, ctx=None):
        """Build leaderboard cache with retry logic and user notification"""
        
        # Check if cache is already being built
        if self._cache_building:
            print("🔄 Cache already building, waiting...")
            # Wait for the current build to complete
            while self._cache_building:
                await asyncio.sleep(0.5)
            
            # Return the freshly built cache
            if self.leaderboard_cache and len(self.leaderboard_cache) >= 500:
                return self.leaderboard_cache
        
        # Check if cache is still valid after waiting
        if self.leaderboard_cache and (time.time() - self.leaderboard_cache_time) < self.leaderboard_cache_duration:
            return self.leaderboard_cache
        
        # Set building flag
        self._cache_building = True
        
        try:
            # Send caching message if ctx is provided
            cache_message = None
            if ctx:
                embed = discord.Embed(
                    title="🔄 Refreshing Player Statistics",
                    description="**Please wait 1-2 minutes while we refresh our player database...**\n\n"
                            "This happens when:\n"
                            "• The cache is outdated\n"
                            "• New players need to be loaded\n"
                            "• The bot just started\n\n"
                            "**Don't worry - your crates will open once this is done!**",
                    color=discord.Color.blue()
                )
                embed.set_footer(text="This only happens occasionally and helps ensure accurate player data")
                
                try:
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed)
                        cache_message = "edited"
                    elif hasattr(ctx, 'response') and not ctx.response.is_done():
                        await ctx.response.send_message(embed=embed)
                        cache_message = "sent"
                    else:
                        cache_message = await ctx.send(embed=embed)
                except:
                    pass  # Don't fail if message sending fails
            
            for attempt in range(retries):
                try:
                    print(f"🔄 Building leaderboard cache (attempt {attempt + 1}/{retries})")
                    
                    # Call the existing build_leaderboard_cache method
                    leaderboard = await self.build_leaderboard_cache()
                    
                    if leaderboard and len(leaderboard) >= 500:
                        print(f"✅ Successfully cached {len(leaderboard)} players")
                        
                        # Update the message to show completion (only once)
                        if ctx and cache_message:
                            success_embed = discord.Embed(
                                title="✅ Player Statistics Updated",
                                description="**Cache refresh complete!** Proceeding with your command...",
                                color=discord.Color.green()
                            )
                            
                            try:
                                if cache_message == "edited":
                                    await ctx.edit_original_response(embed=success_embed)
                                elif cache_message == "sent":
                                    await ctx.edit_original_response(embed=success_embed)
                                elif hasattr(cache_message, 'edit'):
                                    await cache_message.edit(embed=success_embed)
                                
                                # Small delay to let users see the completion message
                                await asyncio.sleep(1)
                            except:
                                pass
                        
                        return leaderboard
                        
                except Exception as e:
                    print(f"❌ Cache attempt {attempt + 1} failed: {e}")
                    if attempt < retries - 1:
                        print(f"⏳ Retrying in 2 seconds...")
                        await asyncio.sleep(2)
                    else:
                        print(f"💀 All cache attempts failed")
                        
                        # Update message to show failure
                        if ctx and cache_message:
                            error_embed = discord.Embed(
                                title="⚠️ Cache Refresh Failed",
                                description="**Unable to refresh player data, but we'll try to continue...**\n\n"
                                        "Using existing cached data or fallback players.",
                                color=discord.Color.orange()
                            )
                            
                            try:
                                if cache_message == "edited":
                                    await ctx.edit_original_response(embed=error_embed)
                                elif cache_message == "sent":
                                    await ctx.edit_original_response(embed=error_embed)
                                elif hasattr(cache_message, 'edit'):
                                    await cache_message.edit(embed=error_embed)
                            except:
                                pass
            
            return None
        
        finally:
            # Always reset the building flag
            self._cache_building = False
        
    async def _ensure_cache_is_valid(self):
        """Automatically rebuild cache if it's outdated (silent background rebuild)"""
        try:
            # Check if cache is expired
            cache_age = time.time() - self.leaderboard_cache_time
            
            # If cache is outdated and not currently rebuilding
            if cache_age >= self.leaderboard_cache_duration and not self._cache_building:
                print(f"🔄 Cache expired ({cache_age/3600:.1f}h old), rebuilding automatically...")
                
                # Set flag to prevent concurrent rebuilds
                self._cache_building = True
                
                try:
                    # Silent rebuild without user messages
                    leaderboard = await self.build_leaderboard_cache()
                    
                    if leaderboard and len(leaderboard) > 0:
                        self.leaderboard_cache = leaderboard
                        self.leaderboard_cache_time = time.time()
                        self._save_cache_to_disk()
                        print(f"✅ Auto-rebuild complete! Cached {len(leaderboard)} players")
                    else:
                        print("⚠️ Auto-rebuild failed - no data received")
                        
                except Exception as e:
                    print(f"❌ Auto-rebuild error: {e}")
                    
                finally:
                    self._cache_building = False
                    
        except Exception as e:
            print(f"Error in cache validation: {e}")
        
        finally:
            # Always reset the building flag
            self._cache_building = False

    async def get_player_by_rank_with_retry(self, rank, retries=3):
        """Get player by rank with retry logic"""
        for attempt in range(retries):
            try:
                return await self.get_player_by_rank(rank)
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                await asyncio.sleep(API_CONFIG["retry_delays"][attempt])
        return None

    async def get_player_by_rank(self, rank, ctx=None):
        """Get player by specific rank from cache or API - OPTIMIZED"""
        # Ensure cache is valid (auto-rebuild if needed)
        await self._ensure_cache_is_valid()
        
        # Try optimized cache lookup first
        player = self.get_player_from_cache_optimized(rank=rank)
        if player:
            return player
        
        # If still not in cache and user is waiting, show rebuild message
        if not self.leaderboard_cache or len(self.leaderboard_cache) < 500:
            if ctx:
                # Only show message to users who are actively waiting
                await self.build_leaderboard_cache_with_retry(retries=3, ctx=ctx)
            else:
                # Silent rebuild if no user context
                await self.build_leaderboard_cache_with_retry(retries=3, ctx=None)
        
        # Try optimized lookup again
        player = self.get_player_from_cache_optimized(rank=rank)
        if player:
            return player
        
        return None
    
    async def get_valid_player_for_crate(self, crate_type, max_attempts=10, ctx=None):
        """Get a valid player for a crate, re-rolling if necessary"""
        
        # Rest of your existing logic...
        crate_info = self.crate_config.get(crate_type)
        if not crate_info:
            raise Exception(f"Invalid crate type: {crate_type}")
        
        for attempt in range(max_attempts):
            try:
                # Select rank range based on weights
                selected_range = random.choices(
                    crate_info["rank_ranges"],
                    weights=[r["weight"] for r in crate_info["rank_ranges"]]
                )[0]
                
                # Get player from range
                player = await self.get_random_player_from_range(
                    selected_range["min"], 
                    selected_range["max"]
                )
                
                if player:
                    return player
                    
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                continue
        
        print(f"❌ Failed to find valid player after {max_attempts} attempts, using cache fallback")
        
        try:
            leaderboard = await self.build_leaderboard_cache_with_retry()
            if leaderboard:
                fallback_player = random.choice(leaderboard)
                print(f"🔄 Using fallback player: {fallback_player['username']} (Rank #{fallback_player['rank']})")
                return fallback_player
        except Exception as e:
            print(f"❌ Cache fallback also failed: {e}")
        
        # Ultimate fallback - create a fake player (should rarely happen)
        fake_rank = random.randint(5000, 9999)
        return {
            'user_id': f'fake_{fake_rank}',
            'username': f'Player{fake_rank}',
            'rank': fake_rank,
            'pp': random.randint(8000, 12000),
            'accuracy': round(random.uniform(95.0, 99.0), 2),
            'play_count': random.randint(10000, 50000),
            'country': 'XX',
            'level': round(random.uniform(80.0, 105.0), 2),
            'profile_picture': f'https://a.ppy.sh/{fake_rank}'
        }

    async def get_random_player_from_range(self, min_rank, max_rank):
        """Get random player from rank range"""
        # Ensure cache is valid (auto-rebuild if needed)
        await self._ensure_cache_is_valid()
        
        # If still no cache, rebuild with retry (silent)
        if not self.leaderboard_cache:
            await self.build_leaderboard_cache_with_retry()
        
        # Filter players in range
        valid_players = [
            player for player in self.leaderboard_cache
            if min_rank <= player['rank'] <= max_rank
        ]
        
        if valid_players:
            return random.choice(valid_players)
        
        return None
    
    def _build_rank_lookup(self):
        """Build rank lookup index for faster searches"""
        if not hasattr(self, '_rank_lookup') or not self._rank_lookup:
            self._rank_lookup = {player['rank']: player for player in self.leaderboard_cache}
            self._username_lookup = {player['username'].lower(): player for player in self.leaderboard_cache}
        return self._rank_lookup, self._username_lookup
    
    def get_player_from_cache_optimized(self, rank=None, username=None):
        """Get player from cache with optimized lookup"""
        rank_lookup, username_lookup = self._build_rank_lookup()
        
        if rank is not None:
            return rank_lookup.get(rank)
        elif username is not None:
            return username_lookup.get(username.lower())
        
        return None

    async def open_crate(self, crate_type, user_id=None, guild_id=None):
        """Open a crate and return player data with mutation and event bonuses"""
        if crate_type not in self.crate_config:
            raise ValueError(f"Invalid crate type: {crate_type}")
        
        # Check for event bonuses if user_id and guild_id provided
        event_bonuses = None
        if user_id and guild_id:
            event_bonuses = self.check_event_bonuses(user_id, guild_id, crate_type)
        
        crate_data = self.crate_config[crate_type]
        rank_ranges = crate_data["rank_ranges"]
        
        # Create weighted list of rank ranges
        weighted_ranges = []
        for range_data in rank_ranges:
            weight = int(range_data["weight"] * 100)  # Convert to integer weight
            weighted_ranges.extend([range_data] * weight)
        
        if not weighted_ranges:
            raise Exception("No valid rank ranges found")
        
        # Select random range
        selected_range = random.choice(weighted_ranges)
        
        # Get random player from that range
        attempts = 0
        max_attempts = GAME_CONFIG["max_rank_attempts"]
        
        while attempts < max_attempts:
            try:
                # Roll for mutation first (before getting player)
                mutation = self.roll_mutation(crate_type)
                
                # Check if flashback card should be generated
                flashback_data, final_mutation, forced_stars, flashback_year = self.generate_flashback_card(mutation)
                
                if flashback_data:
                    # Use flashback player data - REPLACE the random player
                    player = flashback_data
                    stars = forced_stars  # Always 6 stars
                    mutation = final_mutation
                    
                    # Get rarity info for flashback (forced to 6 stars)
                    rarity = {"stars": 6, "name": "Mythical", "color": 0x9932CC}
                else:
                    # Normal card generation - get player from selected range
                    player = await self.get_random_player_from_range(
                        selected_range["min"], 
                        selected_range["max"]
                    )
                    
                    if not player:
                        attempts += 1
                        continue
                    
                    # Get rarity info for normal cards
                    rarity = self.get_rarity_from_rank(player["rank"])
                    
                    # Apply event bonuses if available
                    if event_bonuses:
                        rarity = self.apply_event_rarity_bonuses(rarity, event_bonuses, player)
                    
                    stars = rarity["stars"]
                    mutation = final_mutation
                    flashback_year = None
                
                if player:
                    # Calculate price
                    price = self.calculate_card_price(player, stars, mutation)
                    
                    # Generate card ID
                    card_id = self.generate_card_id(player, stars, mutation)
                    
                    # Create card data
                    card_data = {
                        "card_id": card_id,
                        "player_data": player,
                        "stars": stars,
                        "rarity_name": rarity["name"],
                        "rarity_color": rarity["color"],
                        "mutation": mutation,
                        "price": price,
                        "obtained_at": time.time(),
                        "crate_type": crate_type,
                        "favorite": False
                    }
                    
                    # Add event bonuses to card data
                    if event_bonuses:
                        card_data["event_bonuses"] = {
                            "event_name": event_bonuses["event_name"],
                            "bonus_credits": event_bonuses.get("bonus_credits", 0),
                            "is_event_crate": True,
                            "extra_cards": event_bonuses.get("extra_cards", [])
                        }
                    
                    # Special handling for flashback cards
                    if mutation == "flashback":
                        card_data["flashback_year"] = flashback_year
                        card_data["rarity_name"] = flashback_year  # Override rarity name with year
                    
                    return card_data
                
                attempts += 1
                await asyncio.sleep(0.1)  # Small delay between attempts
                
            except Exception as e:
                print(f"DEBUG: Exception in open_crate: {e}")
                attempts += 1
                if attempts >= max_attempts:
                    raise Exception("Failed to get player data after multiple attempts")
                await asyncio.sleep(0.5)
        
        raise Exception("Failed to get valid player after maximum attempts")
    
    def check_event_bonuses(self, user_id, guild_id, crate_type):
        """Check if user has event crates and return applicable bonuses"""
        try:
            # Get user data
            user_id_str = str(user_id)
            if user_id_str not in self.bot.osu_gacha_data:
                return None
            
            user_data = self.bot.osu_gacha_data[user_id_str]
            event_sources = user_data.get('event_crate_sources', {})
            
            # Check if this crate type has event sources
            if crate_type not in event_sources or not event_sources[crate_type]:
                return None
            
            # Get events cog to check active events
            events_cog = self.bot.get_cog("OsuGachaEvents")
            if not events_cog:
                return None
            
            active_event = events_cog.get_active_event_for_guild(guild_id)
            if not active_event:
                # Clean up expired event sources
                event_sources[crate_type] = []
                return None
            
            # Find matching event source for current active event
            for source in event_sources[crate_type][:]:  # Copy to avoid modification during iteration
                if source['event_id'] == active_event['id']:
                    # Found matching event source, get the item definition
                    store_items = active_event.get('definition', {}).get('store_items', [])
                    if source['item_index'] < len(store_items):
                        event_item = store_items[source['item_index']]
                        
                        # Remove this source (crate will be consumed)
                        event_sources[crate_type].remove(source)
                        
                        return {
                            'event_name': active_event['name'],
                            'item_data': event_item,
                            'active_event': active_event
                        }
            
            return None
            
        except Exception as e:
            print(f"Error checking event bonuses: {e}")
            return None
    
    def apply_event_rarity_bonuses(self, base_rarity, event_bonuses, player):
        """Apply event-specific rarity boosts to upgrade cards"""
        try:
            item_data = event_bonuses["item_data"]
            
            # Check if this item has rarity boosts
            if 'rarity_boosts' not in item_data:
                return base_rarity
            
            rarity_boosts = item_data['rarity_boosts']
            current_rarity_name = base_rarity["name"].lower()
            
            # Map rarity names to upgrade chances
            rarity_hierarchy = ["common", "uncommon", "rare", "epic", "legendary"]
            
            try:
                current_index = rarity_hierarchy.index(current_rarity_name)
            except ValueError:
                # Unknown rarity, return as-is
                return base_rarity
            
            # Check for upgrades from current rarity upward
            for i in range(current_index + 1, len(rarity_hierarchy)):
                target_rarity = rarity_hierarchy[i]
                
                if target_rarity in rarity_boosts:
                    boost_percent = rarity_boosts[target_rarity]
                    upgrade_chance = boost_percent / 100.0  # Convert to decimal
                    
                    if random.random() < upgrade_chance:
                        # Upgrade to this rarity!
                        upgraded_rarity = self.get_rarity_from_rank(1)  # Get base legendary
                        
                        # Override with target rarity info
                        if target_rarity == "legendary":
                            upgraded_rarity = {"stars": 6, "name": "Legendary", "color": 0xFFD700}
                        elif target_rarity == "epic":
                            upgraded_rarity = {"stars": 5, "name": "Epic", "color": 0x9932CC}
                        elif target_rarity == "rare":
                            upgraded_rarity = {"stars": 4, "name": "Rare", "color": 0x0099FF}
                        elif target_rarity == "uncommon":
                            upgraded_rarity = {"stars": 3, "name": "Uncommon", "color": 0x00FF00}
                        elif target_rarity == "common":
                            upgraded_rarity = {"stars": 2, "name": "Common", "color": 0x808080}
                        
                        return upgraded_rarity
            
            # No upgrades applied
            return base_rarity
            
        except Exception as e:
            print(f"Error applying event rarity bonuses: {e}")
            return base_rarity
    
    def get_rarity_from_stars(self, stars):
        """Get rarity info from star count"""
        for rarity_key, rarity_data in self.rarity_config.items():
            if rarity_data["stars"] == stars:
                return rarity_data
        
        # Fallback for unknown star counts
        return {"stars": stars, "color": 0x404040, "name": "Unknown"}

    def get_rarity_from_rank(self, rank):
        """Get star rarity based on rank"""
        if rank == 1:
            return self.rarity_config[1]
        
        for rank_range, rarity in self.rarity_config.items():
            if isinstance(rank_range, tuple):
                min_rank, max_rank = rank_range
                if min_rank <= rank <= max_rank:
                    return rarity
        
        return {"stars": 1, "color": 0x404040, "name": "Common"}

    def roll_mutation(self, crate_type="copper"):
        """Roll for card mutation based on rarity (EXACT 10% chance)"""
        if random.random() <= 0.1:
            # Filter mutations based on crate type
            available_mutations = {}
            for mutation, data in self.mutations.items():
                if mutation == "flashback" and crate_type not in ["rainbow", "diamond"]:
                    continue  # Skip flashback for lower tier crates
                available_mutations[mutation] = data
            
            if not available_mutations:
                return None
                
            # Calculate total weight from available mutations
            total_weight = sum(mutation_data["rarity"] for mutation_data in available_mutations.values())
            
            # Roll for specific mutation
            roll = random.uniform(0, total_weight)
            current_weight = 0
            
            for mutation, mutation_data in available_mutations.items():
                current_weight += mutation_data["rarity"]
                if roll <= current_weight:
                    return mutation
        return None
    
    def generate_flashback_card(self, mutation_result):
        """Generate a flashback card if mutation is flashback"""
        if mutation_result == "flashback":
            # Select random flashback player
            flashback_keys = list(self.flashback_cards.keys())
            selected_player = random.choice(flashback_keys)
            flashback_data = self.flashback_cards[selected_player]
            
            # Return player data, mutation, forced stars, and year
            return flashback_data["player_data"], "flashback", 6, flashback_data["flashback_year"]  # Return the actual player data
        return None, mutation_result, None, None

    def calculate_card_price(self, player_data, stars, mutation=None):
        """Calculate card price optimized for 10k players with player-favorable economics"""
        rank = player_data['rank']
        pp = player_data['pp']
        
        # Optimized pricing for 10k players (ranks 1-10000)
        if rank >= 8001:
            # Rank 8k-10k: Low value from 200 to 600 coins (increased base)
            base_price = 200 + (600 - 200) * (10000 - rank) / 2000
        elif rank >= 6001:
            # Rank 6k-8k: Mid-low value from 600 to 1500 coins
            base_price = 600 + (1500 - 600) * (8000 - rank) / 2000
        elif rank >= 4001:
            # Rank 4k-6k: Mid value from 1500 to 4000 coins
            base_price = 1500 + (4000 - 1500) * (6000 - rank) / 2000
        elif rank >= 2001:
            # Rank 2k-4k: Higher value from 4k to 12k coins
            base_price = 4000 + (12000 - 4000) * (4000 - rank) / 2000
        elif rank >= 1001:
            # Rank 1k-2k: High value from 12k to 50k coins
            base_price = 12000 + (50000 - 12000) * (2000 - rank) / 1000
        elif rank >= 501:
            # Rank 500-1k: Premium from 50k to 200k coins
            base_price = 50000 + (200000 - 50000) * (1000 - rank) / 500
        elif rank >= 101:
            # Rank 100-500: Elite exponential from 200k to 2M coins
            normalized_rank = (500 - rank) / 400  # 0 to 1
            base_price = 200000 + (2000000 - 200000) * (normalized_rank ** 2)
        elif rank >= 51:
            # Rank 50-100: Ultra elite from 2M to 20M coins
            normalized_rank = (100 - rank) / 50  # 0 to 1
            base_price = 2000000 + (20000000 - 2000000) * (normalized_rank ** 2.5)
        elif rank >= 11:
            # Rank 10-50: Legendary from 20M to 200M coins
            normalized_rank = (50 - rank) / 40  # 0 to 1
            base_price = 20000000 + (200000000 - 20000000) * (normalized_rank ** 3)
        else:
            # Rank 1-10: Ultimate tier
            if rank == 1:
                base_price = 1500000000  # 1.5B
            elif rank == 2:
                base_price = 1000000000  # 1B
            elif rank == 3:
                base_price = 700000000   # 700M
            elif rank == 4:
                base_price = 500000000   # 500M
            elif rank == 5:
                base_price = 400000000   # 400M
            else:
                # Ranks 6-10
                normalized_rank = (10 - rank) / 4  # 0 to 1 for ranks 10 to 6
                base_price = 200000000 + (200000000) * (normalized_rank ** 2)
        
        # Star multiplier (moderate)
        star_multiplier = 1 + (stars - 1) * 0.35  # Increased from 0.3
        
        # PP factor (minimal influence)
        pp_factor = 1 + (pp / 25000) * 0.15  # Decreased influence
        
        # Calculate final price
        final_price = int(base_price * star_multiplier * pp_factor)
        
        # Apply mutation multiplier
        if mutation and mutation in self.mutations:
            final_price = int(final_price * self.mutations[mutation]["multiplier"])
        
        # Minimum price
        final_price = max(100, final_price)  # Increased minimum
        
        return final_price
    
    def generate_card_id(self, player_data, stars, mutation=None):
        """Generate unique card ID"""
        mutation_suffix = f"_{mutation}" if mutation else ""
        return f"{player_data['user_id']}_{stars}_{int(time.time())}{mutation_suffix}"

    def format_mutation_text(self, player_name, mutation):
        """Format mutation text consistently: 'player - MUTATION' (NO EMOJI)"""
        if mutation:
            mutation_name = self.mutations.get(mutation, {}).get("name", mutation.upper())
            return f"{player_name} - {mutation_name}"
        return player_name

    def is_card_protected(self, card_data):
        """Check if card is protected from selling/trading"""
        return card_data.get("favorite", False)

    def get_crate_alias(self, crate_input):
        """Get crate type from user input (handles aliases)"""
        crate_input = crate_input.lower()
        
        # Direct matches
        if crate_input in self.crate_config:
            return crate_input
        
        # Check aliases
        for crate_type, config in self.crate_config.items():
            if crate_input in config.get('aliases', []):
                return crate_type
        
        return None
    
    def cleanup_old_cooldowns(self):
        """Clean up expired cooldowns to prevent memory leaks"""
        current_time = time.time()
        expired_users = [
            user_id for user_id, cooldown_time in self.user_cooldowns.items()
            if current_time - cooldown_time > self.crate_cooldown * 2
        ]
        for user_id in expired_users:
            del self.user_cooldowns[user_id]

    def cleanup_caches(self):
        """Clean up memory caches periodically"""
        # Clean font cache if too large
        if len(getattr(self, '_font_cache', {})) > 20:
            self._font_cache.clear()
        
        # Clean background cache if too large  
        if len(getattr(self, '_background_cache', {})) > 50:
            # Keep only the 25 most recently used
            items = list(self._background_cache.items())
            self._background_cache = dict(items[-25:])
        
        # Clean profile cache if too large
        if len(getattr(self, '_profile_cache', {})) > 100:
            # Keep only the 50 most recently used
            items = list(self._profile_cache.items())
            self._profile_cache = dict(items[-50:])
        
       # print("🧹 Cleaned up image caches")

    def check_cooldown(self, user_id):
        """Check if user is on cooldown with automatic cleanup"""
        # Clean up old cooldowns periodically
        if random.random() < 0.1:  # 10% chance to clean up on each check
            self.cleanup_old_cooldowns()

        # Clean up caches occasionally
        if random.random() < 0.05:  # 5% chance to clean up caches
            self.cleanup_caches()
        
        if user_id not in self.user_cooldowns:
            return 0
        
        cooldown_time = self.crate_cooldown
        time_passed = time.time() - self.user_cooldowns[user_id]
        
        if time_passed >= cooldown_time:
            del self.user_cooldowns[user_id]
            return 0
        
        return cooldown_time - time_passed

    def set_cooldown(self, user_id):
        """Set cooldown for user"""
        self.user_cooldowns[user_id] = time.time()

    def generate_player_store_stock(self, user_id):
        """Generate personalized store stock for user"""
        current_time = int(time.time())
        refresh_interval = self.store_config["refresh_interval_minutes"] * 60
        
        # Calculate when this user's store last refreshed
        last_refresh = (current_time // refresh_interval) * refresh_interval
        next_refresh = last_refresh + refresh_interval
        
        # Use user_id and refresh time as seed for consistency
        random.seed(user_id + last_refresh)
        
        individual_stock = {}
        global_inventory = {}
        
        for crate_type, config in self.crate_config.items():
            # Check appearance weight
            if random.random() <= self.store_config["appearance_weights"].get(crate_type, 0):
                # Individual stock for this user
                min_stock, max_stock = self.store_config["stock_ranges"][crate_type]
                individual_stock[crate_type] = random.randint(min_stock, max_stock)
                
                # Global inventory (simulated)
                global_inventory[crate_type] = random.randint(max_stock * 2, max_stock * 5)
            else:
                individual_stock[crate_type] = 0
                global_inventory[crate_type] = 0
        
        # Reset random seed
        random.seed()
        
        return {
            "stock": individual_stock,
            "global_inventory": global_inventory,
            "refresh_time": next_refresh
        }

    def generate_daily_rewards(self):
        """Generate daily rewards with bonus crate chance"""
        # Base coin reward
        coins = random.randint(self.daily_config["coins"]["min"], self.daily_config["coins"]["max"])
        
        rewards = {"coins": coins, "crates": {}}
        
        # Check for bonus crate
        if random.random() <= self.daily_config["bonus_crate_chance"]:
            # Select bonus crate type based on weights
            weighted_crates = []
            for crate_type, weight in self.daily_config["bonus_crate_weights"].items():
                weighted_crates.extend([crate_type] * int(weight * 10))
            
            if weighted_crates:
                bonus_crate = random.choice(weighted_crates)
                rewards["crates"][bonus_crate] = 1
        
        return rewards
    
    def get_cardboard_price(self, user_balance, user_crates_total=0, user_cards_total=0):
        """Get dynamic cardboard box price based on user's balance, existing crates, and cards"""
        base_price = self.crate_config["copper"]["price"]  # 500 from your config
        
        # Only allow dynamic pricing if user has no crates AND no cards (prevents exploitation)
        if user_balance >= base_price or user_crates_total > 0 or user_cards_total > 0:
            return base_price  # Normal price if they can afford it OR have existing items
        else:
            return max(0, user_balance)  # All their money if truly broke with nothing
    
    def get_user_gacha_data(self, user_id):
        """Get user's gacha data - this method is missing but called in achievements"""
        # This method is called but doesn't exist in OsuGachaSystem
        # It should probably access the bot's data
        if hasattr(self, 'bot') and hasattr(self.bot, 'osu_gacha_data'):
            user_id_str = str(user_id)
            if user_id_str not in self.bot.osu_gacha_data:
                from .osugacha_config import GAME_CONFIG
                self.bot.osu_gacha_data[user_id_str] = {
                    "currency": GAME_CONFIG["default_starting_coins"],
                    "cards": {},
                    "crates": {},
                    "daily_last_claimed": 0,
                    "total_opens": 0,
                    "achievements": {},
                    "achievement_stats": {}
                }
            return self.bot.osu_gacha_data[user_id_str]
        else:
            # Fallback for when bot reference isn't available
            return {
                "currency": 5000,
                "cards": {},
                "crates": {},
                "achievements": {},
                "achievement_stats": {}
            }

    # Achievement tracking methods
    async def handle_achievements_command(self, ctx, interaction=None):
        """Show all achievements and user's progress"""
        try:
            if hasattr(ctx, 'response'):
                await ctx.response.defer()
            else:
                message = await ctx.send("Loading achievements...")

            user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
            username = ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name
            user_data = self.get_user_gacha_data(user_id)
            
            user_achievements = user_data.get("achievements", {})
            total_achievements = len(self.achievement_definitions)
            unlocked_count = len(user_achievements)
            
            embed = discord.Embed(
                title=f"{username}'s Achievements",
                description=f"Progress: **{unlocked_count}/{total_achievements}** achievements unlocked ({(unlocked_count/total_achievements*100):.1f}%)",
                color=discord.Color.gold()
            )
            
            # Group achievements by category
            achievement_categories = {
                "Collection": ["first_card", "collector_100", "master_collector_500"],
                "Rarity Hunting": ["legend_hunter", "elite_club", "champion"],
                "Mutations": ["mutation_master", "mutation_holographic", "mutation_immortal"],
                "Wealth": ["wealthy_collector", "millionaire", "big_spender"],
                "Activity": ["daily_devotee", "crate_master", "trading_partner"],
                "Special": ["world_traveler", "lucky_streak"]
            }
            
            for category, achievement_ids in achievement_categories.items():
                category_text = []
                
                for achievement_id in achievement_ids:
                    if achievement_id in self.achievement_definitions:
                        achievement_def = self.achievement_definitions[achievement_id]
                        name = achievement_def["name"]
                        description = achievement_def["description"]
                        
                        if achievement_id in user_achievements:
                            # Unlocked - show when earned
                            timestamp = user_achievements[achievement_id]
                            days_ago = int((time.time() - timestamp) / 86400)
                            
                            if days_ago == 0:
                                time_text = "Today"
                            elif days_ago == 1:
                                time_text = "Yesterday"
                            else:
                                time_text = f"{days_ago}d ago"
                            
                            status = f"✅ **{name}** - *{time_text}*"
                        else:
                            # Locked - show requirement
                            status = f"🔒 **{name}** - {description}"
                        
                        category_text.append(status)
                
                if category_text:
                    embed.add_field(
                        name=category,
                        value="\n".join(category_text),
                        inline=False
                    )
            
            # Show recent achievements if any
            if user_achievements:
                recent_achievements = sorted(user_achievements.items(), key=lambda x: x[1], reverse=True)[:3]
                recent_text = []
                
                for achievement_id, timestamp in recent_achievements:
                    if achievement_id in self.gacha_system.achievement_definitions:
                        name = self.gacha_system.achievement_definitions[achievement_id]["name"]
                        days_ago = int((time.time() - timestamp) / 86400)
                        
                        if days_ago == 0:
                            time_text = "Today"
                        elif days_ago == 1:
                            time_text = "Yesterday"
                        else:
                            time_text = f"{days_ago}d ago"
                        
                        recent_text.append(f"**{name}** - {time_text}")
                
                if recent_text:
                    embed.add_field(
                        name="Recent Achievements",
                        value="\n".join(recent_text),
                        inline=False
                    )
            
            # Progress towards next achievements
            cards = user_data.get("cards", {})
            total_cards = len(cards)
            currency = user_data.get("currency", 0)
            total_mutations = sum(1 for card in cards.values() if card.get("mutation"))
            
            progress_text = []
            
            if "first_card" not in user_achievements and total_cards == 0:
                progress_text.append("**First Steps:** Open your first crate")
            elif "collector_100" not in user_achievements and total_cards < 100:
                remaining = 100 - total_cards
                progress_text.append(f"**Collector:** {remaining} more cards needed")
            elif "master_collector_500" not in user_achievements and total_cards < 500:
                remaining = 500 - total_cards
                progress_text.append(f"**Master Collector:** {remaining} more cards needed")
            
            if "millionaire" not in user_achievements and currency < 1000000:
                remaining = 1000000 - currency
                progress_text.append(f"**Millionaire:** {remaining:,} more coins needed")
            
            if "mutation_master" not in user_achievements and total_mutations < 5:
                remaining = 5 - total_mutations
                progress_text.append(f"**Mutation Master:** {remaining} more mutations needed")
            
            if progress_text:
                embed.add_field(
                    name="Next Goals",
                    value="\n".join(progress_text[:3]),  # Show top 3
                    inline=False
                )
            
            embed.set_footer(text="Keep playing to unlock more achievements!")
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=embed)
            else:
                await message.edit(embed=embed)
                
        except Exception as e:
            print(f"Error in achievements command: {e}")
            error_embed = discord.Embed(
                title="Error",
                description="There was an error loading achievements. Please try again later.",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=error_embed)
            elif hasattr(ctx, 'response'):
                await ctx.response.edit_message(embed=error_embed)
            else:
                await ctx.send(embed=error_embed)

    async def search_player_preview(self, search):
        """Search for a player in the top 10k for preview"""
        try:
            # Check if cache needs rebuilding (automatic rebuild)
            await self._ensure_cache_is_valid()
            
            # Try by rank number first
            if search.isdigit():
                rank = int(search)
                if 1 <= rank <= 10000:
                    # Find player by rank in cached data
                    for player in self.leaderboard_cache:
                        if player['rank'] == rank:
                            return player
            
            # Search by username
            search_lower = search.lower()
            for player in self.leaderboard_cache:
                if search_lower in player['username'].lower():
                    return player
            
            return None
            
        except Exception as e:
            print(f"Error searching player preview: {e}")
            return None
        
    def _get_cached_font(self, font_name, size):
        """Get cached font to avoid repeated loading with cross-platform support"""
        cache_key = f"{font_name}_{size}"
        if cache_key not in self._font_cache:
            # Try multiple font options for cross-platform compatibility
            font_options = []
            
            # Map Windows fonts to cross-platform alternatives
            if font_name == "arialbd.ttf":  # Arial Bold
                if os.name == 'nt':  # Windows
                    font_options = [
                        "arialbd.ttf",
                        "arial-bold.ttf",
                        "C:/Windows/Fonts/arialbd.ttf",
                    ]
                else:  # Linux/Unix
                    font_options = [
                        "DejaVuSans-Bold.ttf",
                        "LiberationSans-Bold.ttf",
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                        "/System/Library/Fonts/Arial Bold.ttf",  # macOS
                    ]
            elif font_name == "arial.ttf":  # Arial Regular
                if os.name == 'nt':  # Windows
                    font_options = [
                        "arial.ttf",
                        "C:/Windows/Fonts/arial.ttf",
                    ]
                else:  # Linux/Unix
                    font_options = [
                        "DejaVuSans.ttf",
                        "LiberationSans-Regular.ttf", 
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                        "/System/Library/Fonts/Arial.ttf",  # macOS
                    ]
            else:
                font_options = [font_name]
            
            # Try each font option until one works
            font_loaded = False
            for font_option in font_options:
                try:
                    self._font_cache[cache_key] = ImageFont.truetype(font_option, size)
                    font_loaded = True
                    break
                except:
                    continue
            
            # Fall back to default if no fonts work, but with a reasonable size
            if not font_loaded:
                try:
                    # Try to get a default font that's closer to the requested size
                    self._font_cache[cache_key] = ImageFont.load_default().font_variant(size=size)
                except:
                    self._font_cache[cache_key] = ImageFont.load_default()
                    
        return self._font_cache[cache_key]

    def _get_fitted_font(self, text, font_name, max_size, max_width, min_size=12):
        """Get a font that fits the text within the specified width"""
        # Start with the maximum size and work down
        for size in range(max_size, min_size - 1, -1):
            font = self._get_cached_font(font_name, size)
            # Get text bounding box
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            
            if text_width <= max_width:
                return font
        
        # If even minimum size doesn't fit, return minimum size font
        return self._get_cached_font(font_name, min_size)

    async def create_card_image(self, player_data, stars, mutation=None, card_price=0, flashback_year=None):
        """Create enhanced card image with FULL mutation effects - OPTIMIZED"""
        try:
            # Card dimensions
            width, height = 400, 600
            
            # Create base card
            card = Image.new('RGBA', (width, height), (255, 255, 255, 0))
            
            # Get rarity info
            rarity = self.get_rarity_from_rank(player_data['rank'])
            
            border_color = f"#{rarity['color']:06x}"
            # Use cached backgrounds when possible
            bg_cache_key = f"{mutation or 'rarity'}_{width}_{height}_{rarity['color']}"
            if bg_cache_key in self._background_cache:
                background = self._background_cache[bg_cache_key]
            else:
                # Create background based on mutation or rarity
                if mutation and mutation in self.mutations:
                    background = self._create_mutation_background(width, height, mutation)
                    border_color = self.mutations[mutation]["color"]
                else:
                    background = self._create_rarity_background(width, height, rarity['color'])
                
                # Cache the background (limit cache size)
                if len(self._background_cache) < 50:
                    self._background_cache[bg_cache_key] = background
            
            # Paste background
            card.paste(background, (0, 0))
            
            # Enhanced border for mutations
            if mutation:
                border_width = 15
                self._draw_mutation_border(card, mutation, border_width)
            else:
                border_width = 12
                draw = ImageDraw.Draw(card)
                draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=border_width)
            
            # Continue with rest of card creation
            draw = ImageDraw.Draw(card)
            
            # Download and add profile picture with caching
            profile_cache_key = player_data['user_id']
            profile_img = None
            
            if profile_cache_key in self._profile_cache:
                profile_img = self._profile_cache[profile_cache_key]
            else:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(player_data['profile_picture']) as resp:
                            if resp.status == 200:
                                img_data = await resp.read()
                                profile_img = Image.open(BytesIO(img_data)).convert('RGBA')
                                profile_img = profile_img.resize((140, 140))
                                
                                # Add profile picture with circular crop
                                mask = Image.new('L', (140, 140), 0)
                                mask_draw = ImageDraw.Draw(mask)
                                mask_draw.ellipse((0, 0, 140, 140), fill=255)
                                profile_img.putalpha(mask)
                                
                                # Cache the profile image (limit cache size)
                                if len(self._profile_cache) < 100:
                                    self._profile_cache[profile_cache_key] = profile_img
                except:
                    pass
            
            if profile_img:
                # Apply mutation effects to profile picture
                if mutation:
                    profile_img = self._apply_mutation_profile_effects(profile_img, mutation)
                
                # Paste profile picture
                card.paste(profile_img, (130, 30), profile_img)
            
            # Use cached fonts
            text_font = self._get_cached_font("arialbd.ttf", 20)
            small_font = self._get_cached_font("arial.ttf", 16)
            value_font = self._get_cached_font("arialbd.ttf", 22)
            
            # Player name with dynamic font sizing (no truncation)
            name_text = player_data['username']
            # Calculate max width for name (card width minus padding)
            max_name_width = width - 40  # 20px padding on each side
            title_font = self._get_fitted_font(name_text, "arialbd.ttf", 32, max_name_width, 16)
            
            self._draw_text_with_shadow(draw, (width//2, 190), name_text, title_font, 'white', 'black')
            
            # Custom stars with mutation effects
            star_y = 225
            self._draw_custom_stars(draw, width//2, star_y, stars, mutation)
            
            # Special handling for flashback cards
            if mutation == "flashback":
                # Add "ICON" text at top - with subtle shadow for visibility
                icon_font = self._get_cached_font("arialbd.ttf", 24)
                # Add subtle dark shadow for contrast
                draw.text((width//2-1, 50-1), "ICON", font=icon_font, fill="black", anchor="mm")
                draw.text((width//2, 50), "ICON", font=icon_font, fill="#FFD700", anchor="mm")
                
                # Use darker gold with subtle shadows for better visibility
                text_color = "#B8860B"  # Darker gold for better contrast
                shadow_color = "rgba(0,0,0,0.3)"  # Light shadow
                
                # Stats with subtle shadows
                draw.text((width//2-1, 270-1), f"#{player_data['rank']:,}", font=text_font, fill="black", anchor="mm")
                draw.text((width//2, 270), f"#{player_data['rank']:,}", font=text_font, fill=text_color, anchor="mm")
                
                draw.text((width//2-1, 305-1), f"{player_data['pp']:,} PP", font=text_font, fill="black", anchor="mm")
                draw.text((width//2, 305), f"{player_data['pp']:,} PP", font=text_font, fill=text_color, anchor="mm")
                
                draw.text((width//2-1, 340-1), f"{player_data['accuracy']}% ACC", font=text_font, fill="black", anchor="mm")
                draw.text((width//2, 340), f"{player_data['accuracy']}% ACC", font=text_font, fill=text_color, anchor="mm")
                
                # Country code with shadow
                draw.text((width//2-1, 375-1), player_data['country'], font=small_font, fill="black", anchor="mm")
                draw.text((width//2, 375), player_data['country'], font=small_font, fill=text_color, anchor="mm")
                
                # Level and plays with shadow
                draw.text((width//2-1, 410-1), f"Level {player_data['level']} • {player_data['play_count']:,} plays", font=small_font, fill="black", anchor="mm")
                draw.text((width//2, 410), f"Level {player_data['level']} • {player_data['play_count']:,} plays", font=small_font, fill=text_color, anchor="mm")
                
                # Mutation text with shadow
                mutation_name = self.mutations[mutation]["name"]
                mutation_text = f"{mutation_name}"
                draw.text((width//2-1, 445-1), mutation_text, font=text_font, fill="black", anchor="mm")
                draw.text((width//2, 445), mutation_text, font=text_font, fill="#DAA520", anchor="mm")  # Goldenrod for mutation
                
                # Price text with shadow
                if card_price >= 1000000000:
                    price_color = '#FF1493'
                elif card_price >= 100000000:
                    price_color = '#FF4500'
                elif card_price >= 10000000:
                    price_color = '#FFD700'
                elif card_price >= 1000000:
                    price_color = '#00FFFF'
                else:
                    price_color = '#00FF00'
                
                price_text = f"Value: {card_price:,} coins"
                draw.text((width//2-1, 520-1), price_text, font=value_font, fill="black", anchor="mm")
                draw.text((width//2, 520), price_text, font=value_font, fill=price_color, anchor="mm")
                
                # Year with shadow
                if flashback_year:
                    draw.text((width//2-1, 560-1), flashback_year, font=text_font, fill="black", anchor="mm")
                    draw.text((width//2, 560), flashback_year, font=text_font, fill='#DAA520', anchor="mm")
                
                stars = 6  # Force 6 stars display
            else:
                # Stats with mutation coloring
                text_color = self.mutations[mutation]["color"] if mutation else 'white'
                
                self._draw_text_with_shadow(draw, (width//2, 270), f"#{player_data['rank']:,}", text_font, text_color, 'black')
                self._draw_text_with_shadow(draw, (width//2, 305), f"{player_data['pp']:,} PP", text_font, text_color, 'black')
                self._draw_text_with_shadow(draw, (width//2, 340), f"{player_data['accuracy']}% ACC", text_font, text_color, 'black')
                
                # Country code
                self._draw_text_with_shadow(draw, (width//2, 375), player_data['country'], small_font, text_color, 'black')
                
                # Level and plays
                self._draw_text_with_shadow(draw, (width//2, 410), f"Level {player_data['level']} • {player_data['play_count']:,} plays", small_font, text_color, 'black')
                
                # Mutation text
                if mutation:
                    mutation_name = self.mutations[mutation]["name"]
                    mutation_text = f"{mutation_name}"
                    self._draw_text_with_shadow(draw, (width//2, 445), mutation_text, text_font, self.mutations[mutation]["color"], 'black')
                
                # Card value with tier-based colors
                if mutation == "flashback":
                    # Flashback cards have fixed color
                    price_color = '#FFD700'
                elif card_price >= 1000000000:
                    price_color = '#FF1493'
                elif card_price >= 100000000:
                    price_color = '#FF4500'
                elif card_price >= 10000000:
                    price_color = '#FFD700'
                elif card_price >= 1000000:
                    price_color = '#00FFFF'
                else:
                    price_color = '#00FF00'
                
                price_text = f"Value: {card_price:,} coins"
                self._draw_text_with_shadow(draw, (width//2, 520), price_text, value_font, price_color, 'black')
                
                # Rarity name
                if flashback_year:
                    self._draw_text_with_shadow(draw, (width//2, 560), flashback_year, text_font, '#FFD700', 'black')
                else:
                    self._draw_text_with_shadow(draw, (width//2, 560), rarity['name'], text_font, 'white', 'black')

            # Player name - handle flashback separately
            if mutation == "flashback":
                # Darker gold with shadow for player name
                draw.text((width//2-1, 190-1), name_text, font=title_font, fill="black", anchor="mm")
                draw.text((width//2, 190), name_text, font=title_font, fill="#DAA520", anchor="mm")
            else:
                self._draw_text_with_shadow(draw, (width//2, 190), name_text, title_font, 'white', 'black')
            
            # Apply final mutation effects overlay
            if mutation:
                card = self._apply_mutation_overlay(card, mutation)
            
            # Save to BytesIO
            img_buffer = BytesIO()
            card.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            return img_buffer
            
        except Exception as e:
            print(f"Error creating card image: {e}")
            return None

    # ENHANCED MUTATION EFFECT METHODS - FULL IMPLEMENTATIONS
    def _create_mutation_background(self, width, height, mutation):
        """Create mutation-specific background with dramatic effects"""
        effect = self.mutations[mutation]["effect"]
        color = self.mutations[mutation]["color"]
        
        # Convert hex to RGB
        hex_color = color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        if effect == "golden_glow":
            return self._create_golden_glow_background(width, height, (r, g, b))
        elif effect == "prismatic_refraction":
            return self._create_prismatic_background(width, height, (r, g, b))  # Add color parameter
        elif effect == "crystal_border":
            return self._create_crystalline_background(width, height, (r, g, b))
        elif effect == "shadow_aura":
            return self._create_shadow_background(width, height, (r, g, b))
        elif effect == "gold_flame":
            return self._create_gold_flame_background(width, height)
        elif effect == "rainbow_border":
            return self._create_rainbow_border_background(width, height)
        elif effect == "cosmic_swirl":
            return self._create_cosmic_background(width, height, (r, g, b))
        elif effect == "electric_pulse":
            return self._create_electric_background(width, height, (r, g, b))
        elif effect == "spectral_fade":
            return self._create_spectral_background(width, height, (r, g, b))
        elif effect == "immortal_flame":
            return self._create_immortal_flame_background(width, height)
        elif effect == "flashback_icon":
            bg = self._create_flashback_background(width, height)
            return self._add_golden_border(bg, width, height)
        else:
            return self._create_gradient_background(width, height, (r, g, b))

    def _create_golden_glow_background(self, width, height, color):
        """Enhanced golden shimmer effect - smooth and shiny"""
        img = Image.new('RGBA', (width, height), (50, 45, 30, 255))  # Warm golden base
        
        # Create smooth golden waves
        for y in range(height):
            for x in range(width):
                # Smooth sine wave pattern
                wave1 = math.sin(x * 0.02) * 0.3 + 0.7
                wave2 = math.sin(y * 0.015) * 0.2 + 0.8
                wave3 = math.sin((x + y) * 0.01) * 0.1 + 0.9
                
                intensity = wave1 * wave2 * wave3
                
                # Golden gradient
                r = int(255 * intensity)
                g = int(215 * intensity * 0.9)
                b = int(50 * intensity * 0.3)
                alpha = int(120 * intensity)
                
                current = img.getpixel((x, y))
                new_color = (
                    min(255, current[0] + r),
                    min(255, current[1] + g),
                    min(255, current[2] + b),
                    255
                )
                img.putpixel((x, y), new_color)
        
        return img

    def _create_prismatic_background(self, width, height, color):
        """Geometric prismatic refraction effect"""
        img = Image.new('RGBA', (width, height), (20, 40, 40, 255))
        
        # Create geometric patterns
        for i in range(30):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(20, 60)
            
            # Draw geometric shapes with the mutation color
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Triangle patterns using the mutation color
            points = [
                (x, y - size),
                (x - size, y + size),
                (x + size, y + size)
            ]
            draw.polygon(points, fill=(*color, 80))  # Use the color parameter
            img = Image.alpha_composite(img, overlay)
        
        return img

    def _create_crystalline_background(self, width, height, color):
        """Crystal structure effect"""
        img = Image.new('RGBA', (width, height), (10, 10, 30, 255))
        
        # Create crystal patterns
        for i in range(50):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(10, 30)
            
            # Draw crystal shapes
            points = []
            for j in range(6):
                angle = j * 60
                px = x + size * math.cos(math.radians(angle))
                py = y + size * math.sin(math.radians(angle))
                points.append((px, py))
            
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            draw.polygon(points, fill=(*color, 50))
            img = Image.alpha_composite(img, overlay)
        
        return img

    def _create_shadow_background(self, width, height, color):
        """Dark smoky shadow effect"""
        img = Image.new('RGBA', (width, height), (15, 15, 15, 255))
        
        # Dark smoke patterns
        for y in range(height):
            for x in range(width):
                # Smoky swirl effect
                smoke = math.sin(x * 0.03 + y * 0.02) * math.cos(x * 0.02 - y * 0.03)
                intensity = abs(smoke) * 0.4
                
                if intensity > 0.1:
                    alpha = int(80 * intensity)
                    current = img.getpixel((x, y))
                    new_color = (
                        min(255, current[0] + 47 * alpha // 255),
                        min(255, current[1] + 47 * alpha // 255),
                        min(255, current[2] + 47 * alpha // 255),
                        255
                    )
                    img.putpixel((x, y), new_color)
        
        return img
    

    def _create_gold_flame_background(self, width, height):
        """Enhanced golden shimmer effect with more detail - like the golden glow but richer"""
        img = Image.new('RGBA', (width, height), (50, 45, 30, 255))  # Warm golden base
        
        center_x, center_y = width // 2, height // 2
        
        # Create detailed golden waves
        for y in range(height):
            for x in range(width):
                # Distance from center for radial effects
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                normalized_distance = distance / (max(width, height) / 2)
                
                # Multiple layered sine wave patterns for complexity
                wave1 = math.sin(x * 0.02) * 0.3 + 0.7
                wave2 = math.sin(y * 0.015) * 0.2 + 0.8
                wave3 = math.sin((x + y) * 0.01) * 0.1 + 0.9
                wave4 = math.sin(x * 0.025 + y * 0.018) * 0.15 + 0.85
                wave5 = math.sin((x - y) * 0.012) * 0.12 + 0.88
                
                # Radial golden glow from center
                radial_glow = math.exp(-normalized_distance * 1.2) * 0.4 + 0.6
                
                # Diagonal shimmer patterns
                diagonal1 = math.sin((x + y) * 0.008 + distance * 0.005) * 0.1 + 0.9
                diagonal2 = math.sin((x - y) * 0.006) * 0.08 + 0.92
                
                # Combine all wave effects
                combined_intensity = wave1 * wave2 * wave3 * wave4 * wave5 * radial_glow * diagonal1 * diagonal2
                
                # Add golden hotspots for extra shimmer
                hotspot1 = math.sin(x * 0.04) * math.sin(y * 0.03) * 0.08 + 0.92
                hotspot2 = math.sin(x * 0.05 + math.pi/4) * math.sin(y * 0.04 + math.pi/6) * 0.06 + 0.94
                
                # Final intensity calculation
                intensity = combined_intensity * hotspot1 * hotspot2
                
                # Smooth fade from edges
                edge_fade = 1.0 - (normalized_distance * 0.3)
                intensity *= max(0.5, edge_fade)
                
                # Rich golden gradient with variation
                r = int(255 * intensity * (0.95 + wave1 * 0.05))
                g = int(215 * intensity * 0.9 * (0.9 + wave2 * 0.1))
                b = int(50 * intensity * 0.3 * (0.8 + wave3 * 0.2))
                
                # Add warm copper highlights in specific wave combinations
                if wave4 > 0.9 and wave1 > 0.8:
                    g = int(g * 0.93)  # Slightly more copper tone
                    b = int(b * 1.4)   # Warmer undertone
                
                # Smooth blending with existing pixels
                current = img.getpixel((x, y))
                blend_factor = 0.85
                new_color = (
                    min(255, current[0] + int(r * blend_factor)),
                    min(255, current[1] + int(g * blend_factor)),
                    min(255, current[2] + int(b * blend_factor * 0.8)),
                    255
                )
                img.putpixel((x, y), new_color)
        
        return img

    def _create_rainbow_border_background(self, width, height):
        """Rainbow gradient background with shimmering effect"""
        img = Image.new('RGBA', (width, height), (20, 20, 20, 255))  # Dark base
        
        # Create rainbow gradient effect
        for y in range(height):
            for x in range(width):
                # Distance from edges for border effect
                edge_distance = min(x, y, width - x - 1, height - y - 1)
                edge_factor = min(1.0, edge_distance / 50.0)  # Fade from edges
                
                # Rainbow hue based on position and shimmer
                hue = ((x + y) * 2 + time.time() * 50) % 360
                
                # Convert HSV to RGB for rainbow effect
                import colorsys
                r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 0.8, 1.0)
                r, g, b = int(r * 255), int(g * 255), int(b * 255)
                
                # Create shimmer effect - more transparent white shimmer
                shimmer = math.sin(x * 0.1) * math.sin(y * 0.1) * math.sin(time.time() * 3)
                base_intensity = 0.15  # Reduced from 0.3 for more transparency
                shimmer_intensity = 0.1  # Reduced from 0.2 for more transparency
                intensity = (base_intensity + shimmer_intensity * shimmer) * (1.0 - edge_factor * 0.5)

                # Add white shimmer overlay
                white_shimmer = abs(shimmer) * 0.05  # Very subtle white shimmer
                
                # Apply rainbow colors with intensity
                current = img.getpixel((x, y))
                new_color = (
                    min(255, current[0] + int(r * intensity) + int(255 * white_shimmer)),  # Add white shimmer
                    min(255, current[1] + int(g * intensity) + int(255 * white_shimmer)),  # Add white shimmer
                    min(255, current[2] + int(b * intensity) + int(255 * white_shimmer)),  # Add white shimmer
                    255
                )
                img.putpixel((x, y), new_color)
        
        return img

    def _create_cosmic_background(self, width, height, color):
        """Cosmic space effect with stars and galaxies"""
        img = Image.new('RGBA', (width, height), (5, 0, 20, 255))
        
        # Add stars
        for i in range(100):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(1, 3)
            
            overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            draw.ellipse([x-size, y-size, x+size, y+size], fill=(255, 255, 255, 200))
            img = Image.alpha_composite(img, overlay)
        
        # Add galaxy spiral
        center_x, center_y = width // 2, height // 2
        for y in range(height):
            for x in range(width):
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                angle = math.atan2(y - center_y, x - center_x)
                
                spiral = math.sin(angle * 2 + distance * 0.05) * math.exp(-distance * 0.01)
                if spiral > 0:
                    alpha = int(100 * spiral)
                    current = img.getpixel((x, y))
                    new_color = (
                        min(255, current[0] + color[0] * alpha // 255),
                        min(255, current[1] + color[1] * alpha // 255),
                        min(255, current[2] + color[2] * alpha // 255),
                        255
                    )
                    img.putpixel((x, y), new_color)
        
        return img

    def _create_electric_background(self, width, height, color):
        """Electric electric pulse effect"""
        img = Image.new('RGBA', (width, height), (0, 5, 0, 255))
        
        # Create electric patterns
        for i in range(20):
            # Random lightning-like paths
            start_x = random.randint(0, width)
            start_y = 0
            
            x, y = start_x, start_y
            while y < height:
                overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                
                next_x = x + random.randint(-20, 20)
                next_y = y + random.randint(10, 30)
                
                draw.line([(x, y), (next_x, next_y)], fill=(*color, 150), width=3)
                img = Image.alpha_composite(img, overlay)
                
                x, y = next_x, next_y
        
        return img

    def _create_spectral_background(self, width, height, color):
        """Ethereal ghostly spectral effect - restored original design"""
        img = Image.new('RGBA', (width, height), (25, 15, 40, 255))  # Dark purple base
        
        # Ethereal wave patterns
        for y in range(height):
            for x in range(width):
                # Ghostly flowing effect
                wave1 = math.sin(x * 0.03 + y * 0.02) * 0.5 + 0.5
                wave2 = math.sin(x * 0.02 - y * 0.03 + math.pi/4) * 0.3 + 0.7
                wave3 = math.sin((x + y) * 0.015) * 0.2 + 0.8
                
                intensity = wave1 * wave2 * wave3 * 0.7
                
                if intensity > 0.3:
                    alpha = int(120 * intensity)
                    current = img.getpixel((x, y))
                    new_color = (
                        min(255, current[0] + 147 * alpha // 255),  # Purple spectral
                        min(255, current[1] + 112 * alpha // 255),
                        min(255, current[2] + 219 * alpha // 255),
                        255
                    )
                    img.putpixel((x, y), new_color)
        
        return img

    def _create_immortal_flame_background(self, width, height):
        """Simplified immortal flame effect"""
        img = Image.new('RGBA', (width, height), (40, 20, 0, 255))  # Dark background
        
        # Simple flame gradient from bottom
        for y in range(height):
            flame_intensity = (height - y) / height * 0.6
            
            for x in range(width):
                # Gentle wave pattern
                wave = math.sin(x * 0.05) * 0.2 + 0.8
                intensity = flame_intensity * wave
                
                if intensity > 0.2:
                    r = int(255 * intensity)
                    g = int(100 * intensity)
                    b = 0
                    
                    current = img.getpixel((x, y))
                    new_color = (
                        min(255, current[0] + r // 3),  # Reduced intensity
                        min(255, current[1] + g // 3),
                        current[2],
                        255
                    )
                    img.putpixel((x, y), new_color)
        
        return img
    
    def _create_flashback_background(self, width, height):
        """Create FIFA Icon-style background - golden border with silver/white shiny finish"""
        img = Image.new('RGBA', (width, height), (255, 255, 255, 255))
        
        # Create silver/white metallic gradient background
        center_x, center_y = width // 2, height // 2
        max_distance = math.sqrt(center_x**2 + center_y**2)
        
        for y in range(height):
            for x in range(width):
                # Create radial gradient from center
                distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                normalized_distance = distance / max_distance
                
                # Silver to white gradient with metallic sheen
                base_intensity = 0.85 + (0.15 * (1.0 - normalized_distance))
                
                # Add diagonal shine effect
                shine_angle = math.atan2(y - center_y, x - center_x)
                shine_intensity = 0.95 + 0.05 * math.sin(shine_angle * 4)
                
                final_intensity = base_intensity * shine_intensity
                r = int(255 * final_intensity)
                g = int(255 * final_intensity)
                b = int(255 * final_intensity)
                
                img.putpixel((x, y), (r, g, b, 255))
        
        return img

    def _create_rarity_background(self, width, height, color):
        """Create rarity-based gradient background"""
        # Convert integer color to RGB tuple
        if isinstance(color, int):
            r = (color >> 16) & 255
            g = (color >> 8) & 255
            b = color & 255
        else:
            r, g, b = color
        
        return self._create_gradient_background(width, height, (r, g, b))

    def _create_gradient_background(self, width, height, color):
        """Fallback gradient background"""
        img = Image.new('RGBA', (width, height), (30, 30, 30, 255))
        
        for y in range(height):
            alpha = int(100 * (1 - y / height))
            for x in range(width):
                current = img.getpixel((x, y))
                new_color = (
                    min(255, current[0] + color[0] * alpha // 255),
                    min(255, current[1] + color[1] * alpha // 255),
                    min(255, current[2] + color[2] * alpha // 255),
                    255
                )
                img.putpixel((x, y), new_color)
        
        return img

    def _apply_mutation_profile_effects(self, profile_img, mutation):
        """Apply mutation effects to profile picture"""
        effect = self.mutations[mutation]["effect"]
        
        if effect in ["gold_flame", "golden_glow"]:
            return self._add_golden_glow(profile_img)
        elif effect == "crystal_border":
            return self._add_crystal_effect(profile_img)
        elif effect == "shadow_aura":
            return self._add_shadow_aura(profile_img)
        elif effect == "immortal_flame":
            return self._add_flame_effect(profile_img)
        elif effect == "rainbow_border":
            return self._add_rainbow_border_effect(profile_img)
        elif effect == "prismatic_refraction":
            return self._add_prismatic_effect(profile_img)
        elif effect == "cosmic_swirl":
            return self._add_cosmic_effect(profile_img)
        elif effect == "electric_pulse":
            return self._add_electric_effect(profile_img)
        elif effect == "spectral_fade":
            return self._add_spectral_effect(profile_img)
        else:
            return profile_img

    def _add_golden_glow(self, profile_img):
        """Simple golden ring border"""
        border = Image.new('RGBA', (profile_img.width + 12, profile_img.height + 12), (0, 0, 0, 0))
        
        # Single golden ring
        draw = ImageDraw.Draw(border)
        draw.ellipse([0, 0, border.width-1, border.height-1], 
                    outline=(255, 215, 0, 255), width=6)
        
        # Paste original image on top
        border.paste(profile_img, (6, 6), profile_img)
        return border.resize(profile_img.size)
    
    def _add_golden_border(self, img, width, height):
        """Add thick golden border for flashback cards"""
        draw = ImageDraw.Draw(img)
        border_width = 25  # Thick golden border
        
        # Create golden gradient border
        for i in range(border_width):
            # Outer border is darker gold, inner is brighter
            gold_intensity = 0.6 + (0.4 * (border_width - i) / border_width)
            r = int(255 * gold_intensity)
            g = int(215 * gold_intensity)
            b = int(0 * gold_intensity)
            
            draw.rectangle([i, i, width-i-1, height-i-1], 
                          outline=(r, g, b, 255), width=1)
        
        return img

    def _add_prismatic_effect(self, profile_img):
        """Add turquoise prismatic border"""
        border = Image.new('RGBA', (profile_img.width + 10, profile_img.height + 10), (0, 0, 0, 0))
        
        # Prismatic geometric border
        draw = ImageDraw.Draw(border)
        for i in range(3):
            draw.ellipse([i*2, i*2, border.width-1-i*2, border.height-1-i*2], 
                        outline=(64, 224, 208, 180-i*40), width=2)
        
        border.paste(profile_img, (5, 5), profile_img)
        return border.resize(profile_img.size)

    def _add_crystal_effect(self, profile_img):
        """Add crystalline effect"""
        enhanced = profile_img.copy()
        enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = enhancer.enhance(1.5)
        
        # Add crystal sparkles
        overlay = Image.new('RGBA', profile_img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        for i in range(20):
            x = random.randint(0, profile_img.width)
            y = random.randint(0, profile_img.height)
            draw.rectangle([x-1, y-1, x+1, y+1], fill=(0, 255, 255, 200))
        
        return Image.alpha_composite(enhanced, overlay)

    def _add_shadow_aura(self, profile_img):
        """Add dark shadow aura"""
        shadow = Image.new('RGBA', (profile_img.width + 15, profile_img.height + 15), (0, 0, 0, 0))
        
        # Create shadow layers
        for i in range(8):
            shadow_layer = Image.new('RGBA', shadow.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(shadow_layer)
            draw.ellipse([i, i, shadow.width-1-i, shadow.height-1-i], 
                        outline=(75, 0, 130, 80-i*10), width=2)
            shadow = Image.alpha_composite(shadow, shadow_layer)
        
        shadow.paste(profile_img, (7, 7), profile_img)
        return shadow.resize(profile_img.size)

    def _add_flame_effect(self, profile_img):
        """Add flame effect around profile"""
        flame = Image.new('RGBA', (profile_img.width + 20, profile_img.height + 20), (0, 0, 0, 0))
        draw = ImageDraw.Draw(flame)
        
        # Create flame-like spikes around the image
        center_x, center_y = flame.width // 2, flame.height // 2
        radius = min(flame.width, flame.height) // 2 - 5
        
        for angle in range(0, 360, 10):
            spike_length = random.randint(5, 15)
            end_x = center_x + (radius + spike_length) * math.cos(math.radians(angle))
            end_y = center_y + (radius + spike_length) * math.sin(math.radians(angle))
            
            draw.line([(center_x, center_y), (end_x, end_y)], 
                     fill=(255, 100, 0, 150), width=3)
        
        flame.paste(profile_img, (10, 10), profile_img)
        return flame.resize(profile_img.size)

    def _add_rainbow_border_effect(self, profile_img):
        """Add animated rainbow border effect"""
        border = Image.new('RGBA', (profile_img.width + 15, profile_img.height + 15), (0, 0, 0, 0))
        
        # Create multiple rainbow rings
        import colorsys
        import time
        
        center_x, center_y = border.width // 2, border.height // 2
        
        for ring in range(5):
            # Create rainbow border rings
            overlay = Image.new('RGBA', border.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Calculate ring position and thickness
            ring_radius = (border.width // 2) - ring * 2
            
            # Draw rainbow ring segments
            for angle in range(0, 360, 10):
                # Rainbow hue that changes over time and position
                hue = (angle + time.time() * 100 + ring * 60) % 360
                r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 1.0, 1.0)
                r, g, b = int(r * 255), int(g * 255), int(b * 255)
                
                # Calculate segment coordinates
                start_angle = math.radians(angle)
                end_angle = math.radians(angle + 10)
                
                # Draw arc segment
                bbox = [center_x - ring_radius, center_y - ring_radius, 
                    center_x + ring_radius, center_y + ring_radius]
                
                draw.arc(bbox, angle, angle + 10, fill=(r, g, b, 200 - ring * 30), width=3)
            
            border = Image.alpha_composite(border, overlay)
        
        # Paste original image in center
        border.paste(profile_img, (7, 7), profile_img)
        return border.resize(profile_img.size)

    def _add_cosmic_effect(self, profile_img):
        """Add cosmic space effect"""
        cosmic = profile_img.copy()
        
        # Add star sparkles
        overlay = Image.new('RGBA', cosmic.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        for i in range(30):
            x = random.randint(0, cosmic.width)
            y = random.randint(0, cosmic.height)
            size = random.randint(1, 2)
            draw.ellipse([x-size, y-size, x+size, y+size], fill=(255, 255, 255, 200))
        
        # Add nebula effect
        enhancer = ImageEnhance.Color(cosmic)
        cosmic = enhancer.enhance(1.3)
        
        return Image.alpha_composite(cosmic, overlay)

    def _add_electric_effect(self, profile_img):
        """Add yellow electric border effect"""
        electric = profile_img.copy()
        
        # Enhance brightness
        enhancer = ImageEnhance.Brightness(electric)
        electric = enhancer.enhance(1.2)
        
        # Add yellow electric border
        overlay = Image.new('RGBA', electric.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        for i in range(3):
            draw.ellipse([i, i, electric.width-1-i, electric.height-1-i], 
                        outline=(255, 255, 0, 200-i*50), width=2)
        
        return Image.alpha_composite(electric, overlay)

    def _add_spectral_effect(self, profile_img):
        """Add ethereal spectral effect - restored original design"""
        spectral = profile_img.copy()
        
        # Preserve the circular mask while adding ethereal transparency
        original_alpha = spectral.getchannel('A')
        
        # Create ethereal transparency but preserve the circular shape
        new_alpha = Image.new('L', spectral.size, 200)  # Slightly more transparent
        # Multiply the new alpha with the original circular mask
        final_alpha = Image.new('L', spectral.size)
        for y in range(spectral.height):
            for x in range(spectral.width):
                orig_val = original_alpha.getpixel((x, y))
                new_val = new_alpha.getpixel((x, y))
                # Multiply the alpha values (keeping circular mask)
                final_val = int((orig_val / 255) * (new_val / 255) * 255)
                final_alpha.putpixel((x, y), final_val)
        
        spectral.putalpha(final_alpha)
        
        # Purple ethereal flowing border
        glow = Image.new('RGBA', spectral.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)
        
        for i in range(5):
            alpha_val = 160 - i * 25
            # Purple spectral glow
            draw.ellipse([i*2, i*2, spectral.width-1-i*2, spectral.height-1-i*2], 
                        outline=(147, 112, 219, alpha_val), width=2)
        
        return Image.alpha_composite(spectral, glow)

    def _draw_custom_stars(self, draw, center_x, y, star_count, mutation=None):
        """Draw enhanced stars with mutation effects"""
        star_spacing = 35
        start_x = center_x - (star_count - 1) * star_spacing // 2
        
        for i in range(star_count):
            x = start_x + i * star_spacing
            
            if mutation:
                self._draw_mutation_star(draw, x, y, 12, mutation)
            else:
                self._draw_star(draw, x, y, 12)

    def _draw_mutation_star(self, draw, x, y, size, mutation):
        """Draw star with mutation effects"""
        color = self.mutations[mutation]["color"]
        
        # Convert hex to RGB
        hex_color = color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        # Draw enhanced star
        if mutation == "rainbow":
            # Rainbow star
            colors = [(255, 0, 0), (255, 165, 0), (255, 255, 0), (0, 255, 0), (0, 0, 255), (128, 0, 128)]
            color = random.choice(colors)
        else:
            color = (r, g, b)
        
        # Draw star with glow
        for glow_size in range(size + 5, size - 1, -1):
            alpha = max(50, 255 - (size + 5 - glow_size) * 50)
            self._draw_star_shape(draw, x, y, glow_size, (*color, alpha))

    def _draw_star_shape(self, draw, x, y, size, color):
        """Draw a 5-pointed star shape"""
        points = []
        for i in range(10):
            angle = math.radians(i * 36 - 90)
            radius = size if i % 2 == 0 else size * 0.4
            px = x + radius * math.cos(angle)
            py = y + radius * math.sin(angle)
            points.append((px, py))
        
        draw.polygon(points, fill=color)

    def _draw_star(self, draw, x, y, size):
        """Draw a 5-pointed star"""
        import math
        
        # Calculate star points
        points = []
        for i in range(10):
            angle = (i * math.pi) / 5
            if i % 2 == 0:
                # Outer points
                px = x + size * math.cos(angle - math.pi/2)
                py = y + size * math.sin(angle - math.pi/2)
            else:
                # Inner points
                px = x + (size * 0.4) * math.cos(angle - math.pi/2)
                py = y + (size * 0.4) * math.sin(angle - math.pi/2)
            points.append((px, py))
        
        # Draw star with gold color and black outline
        draw.polygon(points, fill='#FFD700', outline='black', width=2)

    def _draw_text_with_shadow(self, draw, position, text, font, color, shadow_color='black'):
        """Draw text with shadow for better visibility"""
        x, y = position
        
        # Draw shadow (offset by 2 pixels)
        draw.text((x-1, y-1), text, font=font, fill=shadow_color, anchor="mm")
        draw.text((x+1, y+1), text, font=font, fill=shadow_color, anchor="mm")
        
        # Draw main text
        draw.text((x, y), text, font=font, fill=color, anchor="mm")

    def _draw_mutation_border(self, card, mutation, border_width):
        """Draw mutation-specific border"""
        draw = ImageDraw.Draw(card)
        color = self.mutations[mutation]["color"]
        
        # Draw multiple border lines for glow effect
        for i in range(border_width):
            alpha = int(255 * (1 - i / border_width))
            draw.rectangle([i, i, card.width-1-i, card.height-1-i], outline=color, width=1)

    def _apply_mutation_overlay(self, card, mutation):
        """Apply final mutation overlay effects"""
        effect = self.mutations[mutation]["effect"]
        
        overlay = Image.new('RGBA', card.size, (0, 0, 0, 0))
        
        if effect == "cosmic_swirl":
            # Cosmic sparkle effect
            draw = ImageDraw.Draw(overlay)
            for _ in range(100):
                x = random.randint(0, card.width)
                y = random.randint(0, card.height)
                size = random.randint(1, 3)
                alpha = random.randint(100, 200)
                draw.ellipse([x-size, y-size, x+size, y+size], 
                           fill=(255, 255, 255, alpha))
                
        elif effect == "rainbow_border":  # Changed from "rainbow_explosion"
            # Rainbow sparkle effect
            import colorsys
            draw = ImageDraw.Draw(overlay)
            for _ in range(50):
                x = random.randint(0, card.width)
                y = random.randint(0, card.height)
                size = random.randint(1, 4)
                
                # Random rainbow color
                hue = random.uniform(0, 360)
                r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 1.0, 1.0)
                r, g, b = int(r * 255), int(g * 255), int(b * 255)
                
                draw.ellipse([x-size, y-size, x+size, y+size], 
                        fill=(r, g, b, 150))
        
        elif effect == "immortal_flame":
            # Minimal flame sparkles only
            draw = ImageDraw.Draw(overlay)
            for _ in range(15):  # Reduced from 100+
                x = random.randint(0, card.width)
                y = random.randint(card.height//2, card.height)  # Only bottom half
                size = random.randint(2, 5)
                draw.ellipse([x-size, y-size, x+size, y+size], 
                        fill=(255, 100, 0, 120))
                
        elif effect == "flashback_icon":
            # Golden sparkle effect for flashback cards
            draw = ImageDraw.Draw(overlay)
            for _ in range(30):
                x = random.randint(0, card.width)
                y = random.randint(0, card.height)
                size = random.randint(1, 3)
                alpha = random.randint(120, 200)
                draw.ellipse([x-size, y-size, x+size, y+size], 
                           fill=(255, 215, 0, alpha))  # Golden sparkles
        
        # Always ensure text is above effects by drawing text last
        if overlay:
            card = Image.alpha_composite(card, overlay)
        
        return card

    # ACHIEVEMENT SYSTEM
    def check_and_award_achievements(self, user_data, user_id):
        """Check for and award new achievements - OPTIMIZED"""
        # Use async lock to prevent race conditions
        new_achievements = []
        cards = user_data.get("cards", {})
        
        # Initialize achievement tracking
        if "achievements" not in user_data:
            user_data["achievements"] = {}
        if "achievement_stats" not in user_data:
            user_data["achievement_stats"] = {}
        
        # Pre-calculate expensive operations ONCE
        total_cards = len(cards)
        currency = user_data.get("currency", 0)
        total_opens = user_data.get("total_opens", 0)
        daily_count = user_data.get("daily_count", 0)

        has_20k_pp = any(card["player_data"].get("pp", 0) >= 20000 for card in cards.values())
        has_99_acc = any(card["player_data"].get("accuracy", 0) >= 99.0 for card in cards.values())
        
        # Batch card analysis (single pass through cards)
        six_star_count = 0
        five_star_count = 0
        four_star_count = 0
        mutation_count = 0
        total_value = 0
        countries = set()
        has_top_10 = False
        has_rank_1 = False
        has_holographic = False
        has_immortal = False
        has_prismatic = False
        
        for card in cards.values():
            stars = card.get("stars", 0)
            if stars == 6:
                six_star_count += 1
            elif stars == 5:
                five_star_count += 1
            elif stars == 4:
                four_star_count += 1
            
            if card.get("mutation"):
                mutation_count += 1
                mutation = card.get("mutation")
                if mutation == "holographic":
                    has_holographic = True
                elif mutation == "immortal":
                    has_immortal = True
                elif mutation == "prismatic":
                    has_prismatic = True
            
            total_value += card.get("price", 0)
            countries.add(card["player_data"]["country"])
            
            rank = card["player_data"]["rank"]
            if rank <= 10:
                has_top_10 = True
            if rank == 1:
                has_rank_1 = True
        
        # Current timestamp
        current_time = time.time()
        user_achievements = user_data["achievements"]
        
        # Batch achievement checks (no individual lookups)
        achievement_checks = [
            # (condition, achievement_id, threshold_met)
            (total_cards >= 1, "first_card", "first_card" not in user_achievements),
            (total_cards >= 100, "collector_100", "collector_100" not in user_achievements),
            (total_cards >= 500, "master_collector_500", "master_collector_500" not in user_achievements),
            (six_star_count >= 1, "six_star_collector", "six_star_collector" not in user_achievements),
            (five_star_count >= 1, "legend_hunter", "legend_hunter" not in user_achievements),
            (five_star_count >= 10, "five_star_master", "five_star_master" not in user_achievements),
            (four_star_count >= 25, "four_star_expert", "four_star_expert" not in user_achievements),
            (total_value >= 100000, "wealthy_collector", "wealthy_collector" not in user_achievements),
            (currency >= 1000000, "millionaire", "millionaire" not in user_achievements),
            (mutation_count >= 5, "mutation_master", "mutation_master" not in user_achievements),
            (has_holographic, "mutation_holographic", "mutation_holographic" not in user_achievements),
            (has_immortal, "mutation_immortal", "mutation_immortal" not in user_achievements),
            (has_prismatic, "mutation_prismatic", "mutation_prismatic" not in user_achievements),
            (len(countries) >= 10, "world_traveler", "world_traveler" not in user_achievements),
            (len(user_data.get("favorites", [])) >= 50, "collection_curator", "collection_curator" not in user_achievements),
            (user_data["achievement_stats"].get("crates_bought", 0) >= 100, "bargain_hunter", "bargain_hunter" not in user_achievements),
            (has_top_10, "elite_club", "elite_club" not in user_achievements),
            (has_rank_1, "champion", "champion" not in user_achievements),
            (has_20k_pp, "pp_hunter", "pp_hunter" not in user_achievements),
            (has_99_acc, "accuracy_perfectionist", "accuracy_perfectionist" not in user_achievements),
            (daily_count >= 30, "daily_devotee", "daily_devotee" not in user_achievements),
            (total_opens >= 100, "crate_crusher", "crate_crusher" not in user_achievements),
            (total_opens >= 500, "crate_master", "crate_master" not in user_achievements),
            (total_opens >= 1000, "opening_legend", "opening_legend" not in user_achievements),
            (user_data["achievement_stats"].get("coins_spent", 0) >= 1_000_000, "big_spender", "big_spender" not in user_achievements),
            (user_data.get("trading_stats", {}).get("completed_trades", 0) >= 10, "trading_partner", "trading_partner" not in user_achievements),
        ]
        
        # Process all achievements in batch
        for condition, achievement_id, not_already_achieved in achievement_checks:
            if condition and not_already_achieved:
                user_data["achievements"][achievement_id] = current_time
                new_achievements.append(achievement_id)
        
        return new_achievements
    
async def setup(bot):
    # Just initialize the system on the bot, don't add as cog
    if not hasattr(bot, 'gacha_system'):
        bot.gacha_system = OsuGachaSystem(bot)