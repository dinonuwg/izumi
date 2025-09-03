import discord
from discord.ext import commands
import time
import random
import asyncio
from datetime import datetime, timezone, timedelta
from utils.helpers import *
from utils.config import *

# Import all the configuration and system
from .osugacha_config import *
from .osugacha_system import OsuGachaSystem

class OsuGachaHandlers:
    """Handler class containing all gacha command implementations"""
    
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

    def save_user_data(self):
        """Save user data to file"""
        save_json(FILE_PATHS["gacha_data"], self.bot.osu_gacha_data)

    # COMMAND HANDLERS
    async def handle_open_command(self, ctx, crate_type, amount, interaction=None):
        """Handle crate opening command with API failure protection"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)

        # ONE-TIME cache check at the beginning - only build once per command
        cache_needs_refresh = (
            not self.gacha_system.leaderboard_cache or 
            time.time() - self.gacha_system.leaderboard_cache_time > self.gacha_system.leaderboard_cache_duration
        )
        
        if cache_needs_refresh:
            print("🔄 Cache refresh needed, building once for entire command...")
            await self.gacha_system.build_leaderboard_cache_with_retry(retries=3, ctx=ctx)
        
        # Check user's confirmation preference
        confirmations_enabled = user_data.get("confirmations_enabled", True)

        # Validate amount
        if amount < 1 or amount > 10:
            embed = discord.Embed(
                title="Invalid Amount",
                description="You can open 1-10 crates at once.",
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
            await self.show_crate_help(ctx, interaction)
            return

        # Check if user has enough crates
        user_crates = user_data.get("crates", {})
        available = user_crates.get(resolved_crate, 0)
        if available < amount:
            crate_info = self.gacha_system.crate_config[resolved_crate]
            embed = discord.Embed(
                title="Insufficient Crates",
                description=f"You need {amount}x {crate_info['name']} but only have {available}.\n\nUse `/osustore` to buy more crates.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        # Check cooldown
        cooldown_remaining = self.gacha_system.check_cooldown(user_id)
        if cooldown_remaining > 0:           
            embed = discord.Embed(
                title="Cooldown Active",
                description=f"Please wait **{cooldown_remaining:.1f} seconds** before opening another crate",
                color=discord.Color.orange()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        # For single crate opening with animation
        if amount == 1:
            try:
                # IMMEDIATELY consume crate and set cooldown to prevent spam
                user_data["crates"][resolved_crate] -= 1
                user_data["total_opens"] += 1
                self.gacha_system.set_cooldown(user_id)
                
                # Defer response for long operation
                crate_info = self.gacha_system.crate_config[resolved_crate]
                user_mention = ctx.author.mention if hasattr(ctx, 'author') else ctx.user.mention

                # Defer response for long operation
                if interaction:
                    await interaction.response.defer()
                else:
                    message = await ctx.send(f"Opening {crate_info['name']}... {user_mention}")

                # Show loading message
                embed = discord.Embed(
                    title=f"Opening {crate_info['name']}... {user_mention}",
                    description="🔄 Finding a player...",
                    color=crate_info["color"]
                )

                if hasattr(ctx, 'edit_original_response'):
                    await ctx.edit_original_response(embed=embed)
                else:
                    await message.edit(embed=embed)
                
                # Get valid player with re-rolling
                final_player = await self.gacha_system.get_valid_player_for_crate(resolved_crate, ctx=ctx)
                
                # Check for mutation
                mutation = self.gacha_system.roll_mutation(resolved_crate)
                
                # Handle flashback mutation - replace player with flashback player
                flashback_year = None
                if mutation == "flashback":
                    # Get random flashback player
                    flashback_keys = list(self.gacha_system.flashback_cards.keys())
                    selected_player = random.choice(flashback_keys)
                    flashback_data = self.gacha_system.flashback_cards[selected_player]
                    
                    final_player = flashback_data["player_data"]
                    flashback_year = flashback_data["flashback_year"]
                    
                    # Force 6 stars for flashback cards
                    rarity = self.gacha_system.get_rarity_from_stars(6)
                else:
                    # Calculate rarity for normal cards
                    rarity = self.gacha_system.get_rarity_from_rank(final_player['rank'])
                
                # Calculate price
                stars = rarity['stars']
                card_price = self.gacha_system.calculate_card_price(final_player, stars, mutation)
                
                # Get random players for animation with retry
                try:
                    # Use existing cache instead of rebuilding again
                    if self.gacha_system.leaderboard_cache:
                        leaderboard = self.gacha_system.leaderboard_cache
                    else:
                        leaderboard = await self.gacha_system.build_leaderboard_cache_with_retry(retries=2, ctx=ctx)
                except Exception as e:
                    print(f"⚠️ Could not load leaderboard for animation, skipping: {e}")
                    leaderboard = [final_player]  # Use final player as fallback
                
                # Get random players for animation
                random_players = random.sample(leaderboard, min(6, len(leaderboard)))
                
                # CS:GO style opening animation (fast)
                for i, player in enumerate(random_players[:4]):
                    embed = discord.Embed(
                        title=f"Opening {crate_info['name']}",
                        description=f"**{player['username']}**\nRank #{player['rank']:,} | {player['pp']:,} PP",
                        color=crate_info["color"]
                    )
                    embed.set_thumbnail(url=player['profile_picture'])
                    
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed)
                    else:
                        await message.edit(embed=embed)
                    
                    # Progressive speed increase
                    if i < 2:
                        await asyncio.sleep(0.6)
                    elif i < 3:
                        await asyncio.sleep(0.8)
                    else:
                        await asyncio.sleep(1.2)
                
                # Final dramatic pause
                embed = discord.Embed(
                    title=f"Opening {crate_info['name']}",
                    description="Determining result...",
                    color=crate_info["color"]
                )
                
                if hasattr(ctx, 'edit_original_response'):
                    await ctx.edit_original_response(embed=embed)
                else:
                    await message.edit(embed=embed)
                await asyncio.sleep(1.6)
                
                # Create card
                card_id = self.gacha_system.generate_card_id(final_player, rarity['stars'], mutation)
                
                card_data = {
                    "player_data": final_player,
                    "stars": rarity['stars'],
                    "rarity_name": rarity['name'],
                    "obtained_at": time.time(),
                    "crate_type": resolved_crate,
                    "mutation": mutation,
                    "price": card_price
                }

                # Special handling for flashback cards
                if mutation == "flashback":
                    card_data["flashback_year"] = flashback_year
                    # Override rarity name with year for display
                    card_data["rarity_name"] = flashback_year

                # Add to user's collection
                user_data["cards"][card_id] = card_data

                # Update achievement stats for new card
                if hasattr(self, 'update_achievement_stats'):
                    self.update_achievement_stats(user_data, card_data, "add")
                else:
                    # Fallback - update stats manually
                    if "achievement_stats" not in user_data:
                        user_data["achievement_stats"] = {}
                    
                    stats = user_data["achievement_stats"]
                    player = final_player

                    if mutation:
                        user_data["achievement_stats"]["mutation_streak"] = user_data["achievement_stats"].get("mutation_streak", 0) + 1
                    else:
                        user_data["achievement_stats"]["mutation_streak"] = 0
                    
                    user_data["achievement_stats"]["coins_spent"] = user_data["achievement_stats"].get("coins_spent", 0) + crate_info['price']
                    
                    # Update best rank ever
                    current_best = stats.get("best_rank_ever", float('inf'))
                    if player["rank"] < current_best:
                        stats["best_rank_ever"] = player["rank"]
                    
                    # Update highest card value ever
                    current_highest = stats.get("highest_card_value", 0)
                    if card_price > current_highest:
                        stats["highest_card_value"] = card_price
                    
                    # Track countries visited
                    if "countries_ever" not in stats:
                        stats["countries_ever"] = []
                    if player["country"] not in stats["countries_ever"]:
                        stats["countries_ever"].append(player["country"])
                    
                    # Track mutations found
                    if mutation:
                        if "mutations_ever" not in stats:
                            stats["mutations_ever"] = []
                        if mutation not in stats["mutations_ever"]:
                            stats["mutations_ever"].append(mutation)
                    
                    # Update current maximums
                    cards = user_data.get("cards", {})
                    currency = user_data.get("currency", 0)
                    
                    if cards:
                        current_cards = len(cards)
                        stats["max_cards"] = max(stats.get("max_cards", 0), current_cards)
                        current_value = sum(card.get("price", 0) for card in cards.values())
                        stats["max_collection_value"] = max(stats.get("max_collection_value", 0), current_value)
                    
                    stats["max_currency"] = max(stats.get("max_currency", 0), currency)
                
                # Create card image - pass flashback_year for flashback cards
                card_image = await self.gacha_system.create_card_image(final_player, rarity['stars'], mutation, card_price, flashback_year)
                
                # Show final result - match preview format
                stars_display = "★" * rarity['stars']
                mutation_text = ""
                flashback_era = None

                if mutation:
                    mutation_name = self.gacha_system.mutations[mutation]["name"]
                    mutation_emoji = self.gacha_system.mutations[mutation]["emoji"]
                    mutation_text = f" - {mutation_name} {mutation_emoji}"
                    
                    # Get flashback era for footer
                    if mutation == "flashback" and flashback_year:
                        # Find the flashback era from the config
                        for key, data in self.gacha_system.flashback_cards.items():
                            if data["player_data"]["username"].lower() == final_player["username"].lower():
                                flashback_era = data["flashback_era"]
                                break

                # For flashback cards, use flashback year instead of rarity name
                display_rarity = rarity['name']
                if mutation == "flashback" and flashback_year:
                    display_rarity = flashback_year

                embed = discord.Embed(
                    title=f"{crate_info['name']} Opened!",  # Show crate name opened
                    description=f"**{final_player['username']}{mutation_text}**\n{display_rarity} • {stars_display}",  # Use flashback year instead of rarity
                    color=rarity["color"]
                )

                embed.add_field(
                    name="",
                    value=f"**Rank** #{final_player['rank']:,}\n**PP** {final_player['pp']:,}\n**Accuracy** {final_player['accuracy']}%",
                    inline=True
                )

                embed.add_field(
                    name="",
                    value=f"**Country** {final_player['country']}\n**Level** {final_player['level']}\n**Plays** {final_player['play_count']:,}",
                    inline=True
                )

                embed.add_field(
                    name="Card Value",
                    value=f"**{card_price:,}** coins",
                    inline=True
                )

                # Add mutation description if present
                if mutation:
                    mutation_info = self.gacha_system.mutations[mutation]
                    embed.add_field(
                        name=f"{mutation_info['emoji']} {mutation_info['name']}",
                        value=f"{mutation_info['description']}\n**Rarity:** {mutation_info['rarity']*100:.1f}% chance",
                        inline=False
                    )

                # Special celebration messages with flashback era
                if mutation == "flashback" and flashback_era:
                    embed.set_footer(text=f"{flashback_era}")
                elif final_player['rank'] == 1:
                    embed.set_footer(text="INCREDIBLE! You got the #1 player! Breaking the limits!")
                elif final_player['rank'] <= 10:
                    embed.set_footer(text="AMAZING! Top 10 player! Holy skibidi!")
                elif final_player['rank'] <= 50:
                    embed.set_footer(text="GREAT PULL! Top 50 player! First page player!")
                elif final_player['rank'] <= 100:
                    embed.set_footer(text="Nice! Top 100 player!")
                elif mutation:
                    embed.set_footer(text=f"Rare {self.gacha_system.mutations[mutation]['name']} mutation! Extra valuable!")
                else:
                    embed.set_footer(text="Added to your collection!")
                
                if card_image:
                    file = discord.File(card_image, filename=f"card_{card_id}.png")
                    embed.set_image(url=f"attachment://card_{card_id}.png")
                    
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed, attachments=[file])
                    else:
                        await message.edit(embed=embed, attachments=[file])
                else:
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed)
                    else:
                        await message.edit(embed=embed)
                
                # Check achievements
                new_achievements = self.gacha_system.check_and_award_achievements(user_data, user_id)
                
                # Save data
                self.save_user_data()
                
            except Exception as e:
                # RESTORE crate on error since we consumed it early
                user_data["crates"][resolved_crate] += 1
                user_data["total_opens"] -= 1
                # Remove cooldown on error
                if user_id in self.gacha_system.user_cooldowns:
                    del self.gacha_system.user_cooldowns[user_id]
                    
                print(f"⚠️ Crate opening failed: {e}")
                
                error_embed = discord.Embed(
                    title="Error Opening Crate",
                    description="Something went wrong, please try again later\n*Your crate was restored*",
                    color=discord.Color.red()
                )
                
                if hasattr(ctx, 'edit_original_response'):
                    await ctx.edit_original_response(embed=error_embed)
                elif hasattr(ctx, 'followup'):
                    await ctx.followup.send(embed=error_embed)
                else:
                    await ctx.send(embed=error_embed)

        else:
            # Check if confirmations are enabled for bulk opening
            if confirmations_enabled:
                # Show confirmation for multiple crates 
                crate_info = self.gacha_system.crate_config[resolved_crate]
                embed = discord.Embed(
                    title="Confirm Crate Opening",
                    description=f"Open {amount}x {crate_info['name']}?\n\n"
                            f"**Bulk Opening:**\n"
                            f"• Animation showing your best result\n"
                            f"• Complete summary of all {amount} cards\n"
                            f"• Highlights mutations and rare pulls",
                    color=discord.Color.blue()
                )
                view = OpenView(user_id, self, resolved_crate, amount)
                
                if interaction:
                    await interaction.response.send_message(embed=embed, view=view)
                else:
                    await ctx.send(embed=embed, view=view)
            else:
                # Open directly with enhanced bulk opening
                await self.handle_enhanced_bulk_opening(ctx, resolved_crate, amount, interaction)

    async def handle_open_crate(self, ctx, crate_type, amount):
        """Handle the actual crate opening"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        try:
            # Set cooldown and open crates
            self.gacha_system.set_cooldown(user_id)
            
            opened_cards = []
            total_value = 0
            mutations_found = []
            
            for i in range(amount):
                try:
                    # Open crate and get card (pass user_id and guild_id for event bonuses)
                    user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
                    guild_id = ctx.guild.id if hasattr(ctx, 'guild') and ctx.guild else None
                    card_data = await self.gacha_system.open_crate(crate_type, user_id, guild_id)
                    
                    # Add to user's collection
                    card_id = self.gacha_system.generate_card_id(
                        card_data["player_data"], 
                        card_data["stars"], 
                        card_data["mutation"]
                    )
                    user_data["cards"][card_id] = card_data
                    
                    opened_cards.append(card_data)
                    total_value += card_data["price"]
                    
                    if card_data["mutation"]:
                        mutations_found.append(card_data)
                        
                except Exception as e:
                    print(f"Error opening crate: {e}")
                    embed = discord.Embed(
                        title="Crate Opening Error",
                        description="There was an error opening the crate. Please try again later.",
                        color=discord.Color.red()
                    )
                    
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed)
                    elif hasattr(ctx, 'response'):
                        await ctx.response.edit_message(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                    return
        
            # Consume crates
            user_data["crates"][crate_type] -= amount
            user_data["total_opens"] += amount
            
            # Check achievements
            new_achievements = self.gacha_system.check_and_award_achievements(user_data, user_id)
            
            # Save data
            self.save_user_data()
            
            # Create result embed
            crate_info = self.gacha_system.crate_config[crate_type]
            embed = discord.Embed(
                title=f"Crate Opening Results",
                color=crate_info['color']
            )
            
            if amount == 1:
                # Single card display
                card = opened_cards[0]
                player = card["player_data"]
                
                description = f"Opened 1x {crate_info['name']}\n\n"
                
                if card["mutation"]:
                    mutation_name = self.gacha_system.mutations[card["mutation"]]["name"]
                    description += f"**{'⭐' * card['stars']} {player['username']} - {mutation_name.upper()}**"
                else:
                    description += f"**{'⭐' * card['stars']} {player['username']}**"
                
                description += f"\n#{player['rank']:,} • {player['pp']:,} PP • {player['accuracy']}%"
                description += f"\nValue: {card['price']:,} coins"
                
                # Add event bonus info if present
                if "event_bonuses" in card:
                    event_info = card["event_bonuses"]
                    description += f"\n\n🎊 **{event_info['event_name']} Bonus Applied!**"
                    if event_info.get('bonus_credits', 0) > 0:
                        description += f"\n💰 +{event_info['bonus_credits']:,} bonus coins!"
                
                embed.description = description
            else:
                # Multiple cards summary
                embed.description = f"Opened {amount}x {crate_info['name']}"
                
                # Group by rarity
                rarity_counts = {}
                for card in opened_cards:
                    rarity = card["rarity_name"]
                    if rarity not in rarity_counts:
                        rarity_counts[rarity] = []
                    rarity_counts[rarity].append(card)
                
                # Show summary by rarity
                for rarity, cards in rarity_counts.items():
                    card_list = []
                    for card in cards[:5]:  # Show first 5
                        player = card["player_data"]
                        if card["mutation"]:
                            mutation_name = self.gacha_system.mutations[card["mutation"]]["name"]
                            player_text = f"{player['username']} - {mutation_name.upper()}"
                        else:
                            player_text = player['username']
                        card_list.append(f"{'⭐' * card['stars']} {player_text}")
                    
                    if len(cards) > 5:
                        card_list.append(f"... and {len(cards) - 5} more")
                    
                    embed.add_field(
                        name=f"{rarity} ({len(cards)})",
                        value="\n".join(card_list),
                        inline=True
                    )
            
            # Add mutations section
            if mutations_found:
                mutation_text = []
                for card in mutations_found:
                    player = card["player_data"]
                    mutation_name = self.gacha_system.mutations[card["mutation"]]["name"]
                    mutation_text.append(f"{player['username']} - {mutation_name.upper()}")
                
                embed.add_field(
                    name="Mutations Found!",
                    value="\n".join(mutation_text),
                    inline=False
                )
            
            # Add summary
            embed.add_field(
                name="Summary",
                value=f"Total Value: {total_value:,} coins\nMutations: {len(mutations_found)}",
                inline=False
            )
            
            # Add achievements
            if new_achievements:
                achievement_text = []
                for achievement_id in new_achievements:
                    achievement = self.gacha_system.achievement_definitions[achievement_id]
                    achievement_text.append(f"**{achievement['name']}** - {achievement['description']}")
                
                embed.add_field(
                    name="New Achievements!",
                    value="\n".join(achievement_text),
                    inline=False
                )
            
            # Send result
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=embed, view=None)  # Add view=None
            elif hasattr(ctx, 'response'):
                await ctx.response.edit_message(embed=embed, view=None)   # Add view=None
            else:
                await ctx.send(embed=embed)
                
        except Exception as e:
            print(f"Error in crate opening: {e}")
            embed = discord.Embed(
                title="Error",
                description="There was an error processing your request. Please try again later.",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=embed)
            elif hasattr(ctx, 'response'):
                await ctx.response.edit_message(embed=embed)
            else:
                await ctx.send(embed=embed)

    async def handle_enhanced_bulk_opening(self, ctx, crate_type, amount, interaction=None):
        """Enhanced bulk opening with animation for most valuable card + summary"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        user_mention = ctx.author.mention if hasattr(ctx, 'author') else ctx.user.mention
        
        try:
            # Immediately consume crates and set cooldown
            user_data["crates"][crate_type] -= amount
            user_data["total_opens"] += amount
            self.gacha_system.set_cooldown(user_id)
            
            # Defer response for long operation - BUT CHECK IF ALREADY RESPONDED
            crate_info = self.gacha_system.crate_config[crate_type]
            
            # FIX: Don't defer if interaction already responded to
            if interaction and not interaction.response.is_done():
                await interaction.response.defer()
            elif not interaction:
                message = await ctx.send(f"Opening {amount}x {crate_info['name']}... {user_mention}")

            # Step 1: Show initial loading
            embed = discord.Embed(
                title=f"Opening {amount}x {crate_info['name']}...",
                description="Opening crates...",
                color=crate_info["color"]
            )

            # FIX: Use proper method to edit message
            if interaction and interaction.response.is_done():
                # Interaction already responded to (came from button) - use edit_original_response
                await interaction.edit_original_response(embed=embed)
            elif interaction:
                # Fresh interaction - use edit_original_response after defer
                await interaction.edit_original_response(embed=embed)
            else:
                # Context command - edit the message we just sent
                await message.edit(embed=embed)
            
            # Step 2: Open all crates and collect results
            opened_cards = []
            total_value = 0
            mutations_found = []
            event_bonuses_applied = 0
            total_bonus_credits = 0
            
            for i in range(amount):
                try:
                    # Pass user_id and guild_id for event bonuses
                    user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
                    guild_id = ctx.guild.id if hasattr(ctx, 'guild') and ctx.guild else None
                    card_data = await self.gacha_system.open_crate(crate_type, user_id, guild_id)
                    
                    # Add to user's collection
                    card_id = self.gacha_system.generate_card_id(
                        card_data["player_data"], 
                        card_data["stars"], 
                        card_data["mutation"]
                    )
                    user_data["cards"][card_id] = card_data
                    
                    opened_cards.append(card_data)
                    total_value += card_data["price"]
                    
                    if card_data["mutation"]:
                        mutations_found.append(card_data)
                    
                    # Track event bonuses
                    if "event_bonuses" in card_data:
                        event_bonuses_applied += 1
                        total_bonus_credits += card_data["event_bonuses"].get("bonus_credits", 0)
                
                except Exception as e:
                    print(f"Error opening crate {i+1}: {e}")
                    continue
            
            # Add bonus credits to user's balance
            if total_bonus_credits > 0:
                user_data["credits"] += total_bonus_credits
            
            if not opened_cards:
                raise Exception("Failed to open any crates")
            
            # Step 3: Find the most valuable card for animation
            most_valuable_card = max(opened_cards, key=lambda card: card["price"])
            final_player = most_valuable_card["player_data"]
            
            # Step 4: Show animation with the most valuable card
            # Get random players for animation
            try:
                if self.gacha_system.leaderboard_cache:
                    leaderboard = self.gacha_system.leaderboard_cache
                else:
                    leaderboard = await self.gacha_system.build_leaderboard_cache_with_retry(retries=2, ctx=ctx)
            except Exception as e:
                print(f"Could not load leaderboard for animation: {e}")
                leaderboard = [final_player]
            
            # Get random players for animation
            random_players = random.sample(leaderboard, min(6, len(leaderboard)))
            
            # CS:GO style opening animation (faster for bulk)
            for i, player in enumerate(random_players[:3]):  # Shorter animation for bulk
                embed = discord.Embed(
                    title=f"Opening {amount}x {crate_info['name']}..",
                    description=f"**{player['username']}**\nRank #{player['rank']:,} | {player['pp']:,} PP",
                    color=crate_info["color"]
                )
                embed.set_thumbnail(url=player['profile_picture'])
                
                # FIX: Use consistent edit method
                if interaction:
                    await interaction.edit_original_response(embed=embed)
                else:
                    await message.edit(embed=embed)
                
                # Faster animation for bulk
                if i < 1:
                    await asyncio.sleep(0.4)
                elif i < 2:
                    await asyncio.sleep(0.6)
                else:
                    await asyncio.sleep(0.8)
            
            # Step 5: Show "determining best result"
            embed = discord.Embed(
                title=f"Opening {amount}x {crate_info['name']}.",
                description="Determining best result...",
                color=crate_info["color"]
            )
            
            # FIX: Use consistent edit method
            if interaction:
                await interaction.edit_original_response(embed=embed)
            else:
                await message.edit(embed=embed)
            await asyncio.sleep(1.0)
            
            # Step 6: Show the most valuable card result with animation
            mutation = most_valuable_card.get("mutation")
            rarity = {"stars": most_valuable_card["stars"], "name": most_valuable_card["rarity_name"], "color": discord.Color.gold()}
            card_price = most_valuable_card["price"]
            flashback_year = most_valuable_card.get("flashback_year")
            
            # Create animated result for best card
            stars_display = "★" * most_valuable_card["stars"]
            mutation_text = ""
            
            if mutation:
                mutation_name = self.gacha_system.mutations[mutation]["name"]
                mutation_emoji = self.gacha_system.mutations[mutation]["emoji"]
                mutation_text = f" - {mutation_name} {mutation_emoji}"
            
            # Create the main result embed showing the best card
            embed = discord.Embed(
                title=f"{amount}x {crate_info['name']} Opened!",
                description=f"**{final_player['username']}{mutation_text}**\n{most_valuable_card['rarity_name']} • {stars_display}",
                color=rarity["color"]
            )

            # Show best card stats
            embed.add_field(
                name="",
                value=f"**Rank** #{final_player['rank']:,}\n**PP** {final_player['pp']:,}\n**Value** {card_price:,} coins",
                inline=True
            )
            
            embed.add_field(
                name="",
                value=f"**Total Value: {total_value:,} coins**\n**Mutations:** {len(mutations_found)}",
                inline=True
            )
            
            # Add event bonus field if applicable
            if event_bonuses_applied > 0:
                bonus_text = f"**Event Bonuses:** {event_bonuses_applied} cards"
                if total_bonus_credits > 0:
                    bonus_text += f"\n**Bonus Credits:** +{total_bonus_credits:,}"
                embed.add_field(
                    name="🎉 Event Bonuses",
                    value=bonus_text,
                    inline=True
                )
            
            # Add mutation info for best card if present
            if mutation:
                mutation_info = self.gacha_system.mutations[mutation]
                embed.add_field(
                    name=f"{mutation_info['name']} {mutation_info['emoji']}",
                    value=f"{mutation_info['description']}",
                    inline=False
                )
                        
            # Step 7: SHOW ALL CARDS - NO TRUNCATION
            # Group by rarity for summary
            rarity_counts = {}
            for card in opened_cards:
                rarity = card["rarity_name"]
                if rarity not in rarity_counts:
                    rarity_counts[rarity] = []
                rarity_counts[rarity].append(card)

            summary_text = f"**All {amount} cards opened:**\n"
            if event_bonuses_applied > 0:
                summary_text += f"🎉 **{event_bonuses_applied}** cards received event bonuses"
                if total_bonus_credits > 0:
                    summary_text += f" (+{total_bonus_credits:,} credits)"
                summary_text += "\n"
            summary_text += "\n"

            # Create horizontal display of rarity categories
            rarity_sections = []

            for rarity, cards in sorted(rarity_counts.items(), key=lambda x: len(x[1]), reverse=True):
                # SHOW ALL CARDS VERTICALLY within each rarity
                card_names = []
                
                for card in cards:
                    player = card["player_data"]
                    
                    # Mark the best card with a crown
                    is_best = card == most_valuable_card
                    crown = "👑 - " if is_best else ""
                    
                    if card["mutation"]:
                        mutation_name = self.gacha_system.mutations[card["mutation"]]["name"]
                        player_text = f"{crown}{'⭐' * card['stars']} {player['username']} ({mutation_name.upper()})"
                    else:
                        player_text = f"{crown}{'⭐' * card['stars']} {player['username']}"
                    45
                    card_names.append(player_text)
                
                # Join players vertically within rarity, create rarity section
                rarity_section = f"**{rarity} ({len(cards)}):**\n" + "\n".join(card_names)
                rarity_sections.append(rarity_section)

            # Join rarity sections horizontally with double newlines for separation
            summary_text += "\n\n".join(rarity_sections) + "\n\n"

            # Add mutations summary if any - SHOW ALL VERTICALLY
            if mutations_found:
                mutation_names = []
                for card in mutations_found:
                    player = card["player_data"]
                    mutation_name = self.gacha_system.mutations[card["mutation"]]["name"]
                    is_best = card == most_valuable_card
                    crown = "👑 - " if is_best else ""
                    mutation_names.append(f"{crown}{player['username']} ({mutation_name.upper()})")
                
                summary_text += f"**Mutations Found ({len(mutations_found)}):**\n" + "\n".join(mutation_names)

            # Add summary as single field (Discord will truncate if too long)
            embed.add_field(
                name="",
                value=summary_text[:1024],  # Discord's field limit
                inline=False
            )
            
            # Set footer based on best result
            if mutation == "flashback" and flashback_year:
                embed.set_footer(text=f"Best result: {flashback_year} • Total opened: {amount}")
            elif final_player['rank'] == 1:
                embed.set_footer(text="INCREDIBLE! #1 player in your bulk opening!")
            elif final_player['rank'] <= 10:
                embed.set_footer(text="AMAZING! Top 10 player in your bulk opening!")
            elif final_player['rank'] <= 50:
                embed.set_footer(text="GREAT! Top 50 player in your bulk opening!")
            elif mutation:
                embed.set_footer(text=f"Mutation in bulk opening! {mutation_name} variant!")
            else:
                embed.set_footer(text=f"Bulk opening complete! Best card shown above.")
            
            # Generate and show image for the best card
            try:
                card_image = await self.gacha_system.create_card_image(
                    final_player, most_valuable_card["stars"], mutation, card_price, flashback_year
                )
                
                if card_image:
                    file = discord.File(card_image, filename=f"bulk_best_{most_valuable_card['stars']}star.png")
                    embed.set_image(url=f"attachment://bulk_best_{most_valuable_card['stars']}star.png")
                    
                    # FIX: Use consistent edit method
                    if interaction:
                        await interaction.edit_original_response(embed=embed, attachments=[file])
                    else:
                        await message.edit(embed=embed, attachments=[file])
                else:
                    # FIX: Use consistent edit method
                    if interaction:
                        await interaction.edit_original_response(embed=embed)
                    else:
                        await message.edit(embed=embed)
            except Exception as e:
                print(f"Error generating best card image: {e}")
                # FIX: Use consistent edit method
                if interaction:
                    await interaction.edit_original_response(embed=embed)
                else:
                    await message.edit(embed=embed)
            
            # Check achievements and save data
            new_achievements = self.gacha_system.check_and_award_achievements(user_data, user_id)
            self.save_user_data()
            
        except Exception as e:
            # Restore crates on error
            user_data["crates"][crate_type] += amount
            user_data["total_opens"] -= amount
            if user_id in self.gacha_system.user_cooldowns:
                del self.gacha_system.user_cooldowns[user_id]
                
            print(f"Bulk crate opening failed: {e}")
            
            error_embed = discord.Embed(
                title="Error Opening Crates",
                description="Something went wrong, please try again later\n*Your crates were restored*",
                color=discord.Color.red()
            )
            
            # FIX: Use consistent error handling
            if interaction:
                await interaction.edit_original_response(embed=error_embed)
            else:
                await ctx.send(embed=error_embed)

    async def handle_daily_command(self, ctx, interaction=None):
        """Daily rewards command implementation"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        # Check if already claimed today
        now = datetime.now(timezone.utc)
        last_claimed = user_data.get("daily_last_claimed", 0)
        
        if last_claimed > 0:
            last_claimed_date = datetime.fromtimestamp(last_claimed, tz=timezone.utc).date()
            if last_claimed_date >= now.date():
                # Calculate time until next claim
                tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                time_until_reset = tomorrow - now
                hours, remainder = divmod(int(time_until_reset.total_seconds()), 3600)
                minutes = remainder // 60
                
                embed = discord.Embed(
                    title="Daily Already Claimed",
                    description=f"You've already claimed your daily rewards today!\n\nNext claim available in: **{hours}h {minutes}m**",
                    color=discord.Color.orange()
                )
                
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
        
        # Check if streak should continue or reset
        current_streak = user_data.get("daily_count", 0)
        
        if last_claimed > 0:
            last_claimed_date = datetime.fromtimestamp(last_claimed, tz=timezone.utc).date()
            yesterday = now.date() - timedelta(days=1)
            
            # If last claim was yesterday, continue streak
            if last_claimed_date == yesterday:
                current_streak += 1
            # If last claim was today (already handled above) or earlier than yesterday, reset streak
            elif last_claimed_date < yesterday:
                current_streak = 1  # Reset to 1 (today's claim)
            # If somehow last_claimed_date is today, this shouldn't happen due to check above
            else:
                current_streak += 1  # Continue streak (shouldn't reach here normally)
        else:
            # First time claiming
            current_streak = 1
        
        # Generate and apply rewards directly
        rewards = self.gacha_system.generate_daily_rewards()
        
        # Apply rewards
        user_data["currency"] += rewards["coins"]
        for crate_type, amount in rewards["crates"].items():
            user_data["crates"][crate_type] = user_data["crates"].get(crate_type, 0) + amount
        
        # Update daily count (streak) and timestamp
        user_data["daily_count"] = current_streak
        user_data["daily_last_claimed"] = time.time()
        
        # Check achievements
        new_achievements = self.gacha_system.check_and_award_achievements(user_data, user_id)
        
        # Save data
        self.save_user_data()
        
        # Create success embed
        embed = discord.Embed(
            title="Daily Rewards Claimed!",
            description=f"**Coins:** +{rewards['coins']:,}",
            color=discord.Color.green()
        )
        
        # Add crate rewards
        if rewards["crates"]:
            crate_text = []
            for crate_type, amount in rewards["crates"].items():
                crate_info = self.gacha_system.crate_config[crate_type]
                crate_text.append(f"**{crate_info['name']}:** +{amount}")
            
            embed.add_field(
                name="Bonus Crates!",
                value="\n".join(crate_text),
                inline=False
            )
        
        # Add achievements
        if new_achievements:
            achievement_text = []
            for achievement_id in new_achievements:
                achievement = self.gacha_system.achievement_definitions[achievement_id]
                achievement_text.append(f"**{achievement['name']}** - {achievement['description']}")
            
            embed.add_field(
                name="New Achievements!",
                value="\n".join(achievement_text),
                inline=False
            )
        
        # Show new balances
        total_crates = sum(user_data["crates"].values())
        embed.add_field(
            name="New Balance",
            value=f"**Coins:** {user_data['currency']:,}\n**Crates:** {total_crates}",
            inline=True
        )
        
        # Show streak with streak break notification if applicable
        streak_text = f"**Days:** {user_data['daily_count']}"
        if last_claimed > 0 and current_streak == 1:
            # Streak was reset
            last_claimed_date = datetime.fromtimestamp(last_claimed, tz=timezone.utc).date()
            days_missed = (now.date() - last_claimed_date).days - 1
            if days_missed > 0:
                streak_text += f"\n💔 Streak reset! You missed {days_missed} day{'s' if days_missed > 1 else ''}"
        elif current_streak > 1:
            # Continuing streak
            streak_text += f" 🔥"
        
        embed.add_field(
            name="Daily Streak",
            value=streak_text,
            inline=True
        )
        
        embed.set_footer(text="Come back tomorrow to continue your streak!")
        
        if interaction:
            await interaction.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)

    async def handle_balance_command(self, ctx, interaction=None):
        """Balance command implementation - shows coins and crates"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        username = ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name
        
        # Get currency and crates
        currency = user_data.get("currency", 0)
        crates = user_data.get("crates", {})
        total_crates = sum(crates.values())
        
        # Create embed with coins
        embed = discord.Embed(
            title=f"{username}'s Balance",
            description=f"**{currency:,}** coins",
            color=discord.Color.gold()
        )
        
        # Add crates field
        if total_crates > 0:
            crate_text = []
            for crate_type, amount in crates.items():
                if amount > 0:
                    crate_info = self.gacha_system.crate_config.get(crate_type, {"name": crate_type, "emoji": "📦"})
                    crate_text.append(f"{crate_info['emoji']} **{crate_info['name']}:** {amount}")
            
            embed.add_field(
                name="Crates",
                value="\n".join(crate_text) if crate_text else "None",
                inline=False
            )
        else:
            embed.add_field(
                name="Crates", 
                value="None",
                inline=False
            )
        
        if interaction:
            await interaction.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)

    async def handle_simulate_command(self, ctx, crate_type, amount, interaction=None):
        """Simulate command implementation - uses REAL cache data like backup"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id

        # Check if user has administrator permissions
        if hasattr(ctx, 'author'):  # Prefix command
            if not ctx.author.guild_permissions.administrator:
                embed = discord.Embed(
                    title="❌ Permission Denied",
                    description="This command requires Administrator permissions.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
        elif hasattr(ctx, 'user'):  # Slash command
            if not ctx.user.guild_permissions.administrator:
                embed = discord.Embed(
                    title="❌ Permission Denied", 
                    description="This command requires Administrator permissions.",
                    color=discord.Color.red()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await ctx.send(embed=embed)
                return
        
        # Validate amount - match backup limits
        if amount < 100 or amount > 100000:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Simulation amount must be between 100 and 100,000",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return
        
        # Resolve crate type
        resolved_crate = self.gacha_system.get_crate_alias(crate_type)
        if not resolved_crate and crate_type.lower() != "all":
            await self.show_crate_help(ctx, interaction)
            return
        
        if interaction:
            await interaction.response.defer()
        
        # Create starting embed like backup
        embed = discord.Embed(
            title="Gacha Simulation Running",
            description=f"Running {amount:,} crate simulations using actual bot logic...",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value="🚀 Running simulation...", inline=False)
        embed.set_footer(text="This may take a moment for large simulations (10-30 seconds). Please wait...")
        
        progress_msg = None
        if hasattr(ctx, 'edit_original_response'):
            await ctx.edit_original_response(embed=embed)
        else:
            progress_msg = await ctx.send(embed=embed)
        
        try:
            start_time = time.time()
            
            if crate_type.lower() == "all":
                # Simulate all crate types like backup
                results = {}
                total_crates = amount * 5  # 5 crate types
                current_progress = 0

                await self.gacha_system.build_leaderboard_cache_with_retry(retries=3, ctx=ctx)
                
                for crate in ["common", "uncommon", "rare", "epic", "legendary"]:
                    embed.set_field_at(0, name="Status", value=f"🎲 Simulating {self.gacha_system.crate_config[crate]['name']}... ({current_progress}/{total_crates:,})", inline=False)
                    
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed)
                    else:
                        await progress_msg.edit(embed=embed)
                    
                    result = await self._run_single_simulation(crate, amount, ctx, current_progress, total_crates)
                    results[crate] = result
                    current_progress += amount
                
                # Show combined results like backup
                await self._show_all_results(ctx, results, amount, progress_msg)
                
            else:
                # Simulate single crate type
                result = await self._run_single_simulation(resolved_crate, amount, ctx, 0, amount)
                await self._show_single_result(ctx, resolved_crate, result, amount, progress_msg)
            
            total_time = time.time() - start_time
            print(f"🎯 Total simulation completed in {total_time:.2f}s")
                
        except Exception as e:
            print(f"Simulation error: {e}")
            embed = discord.Embed(
                title="❌ Simulation Failed",
                description=f"An error occurred during simulation: {str(e)}",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=embed)
            else:
                await progress_msg.edit(embed=embed)

    async def _run_single_simulation(self, crate_type, amount, ctx, current_progress, total_progress):
        """Run simulation for a single crate type using cached data"""
        crate_info = self.gacha_system.crate_config[crate_type]
        
        # Simulation data
        values = []
        ranks = []
        mutations = {"none": 0}
        stars_count = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        
        # Special tracking
        rank_1_count = 0
        top_10_count = 0
        top_50_count = 0
        top_100_count = 0
        
        # Time-based progress updates (every 5 seconds)
        start_time = time.time()
        last_update_time = start_time
        update_interval_seconds = 5.0
        
        # Ensure cache is built with notification
        await self.gacha_system.build_leaderboard_cache_with_retry(retries=3, ctx=ctx)
        
        for i in range(amount):
            # Time-based progress updates (every 5 seconds)
            current_time = time.time()
            if current_time - last_update_time >= update_interval_seconds and i > 0:
                progress_percent = ((current_progress + i) / total_progress) * 100
                completion_percent = (i / amount) * 100
                
                # Calculate proper timing
                elapsed_time = current_time - start_time
                if i > 0:
                    time_per_iteration = elapsed_time / i
                    remaining_iterations = amount - i
                    eta_seconds = time_per_iteration * remaining_iterations
                    eta_text = f"ETA: {eta_seconds:.0f}s"
                else:
                    eta_text = "ETA: Calculating..."
                
                embed = discord.Embed(
                    title="🎲 Gacha Simulation Running",
                    description=f"Simulating {amount:,} {crate_info['name']} openings...",
                    color=crate_info["color"]
                )
                embed.add_field(
                    name="Progress", 
                    value=f"**{i:,}/{amount:,}** ({completion_percent:.1f}%)\nOverall: {progress_percent:.1f}%",
                    inline=False
                )
                embed.add_field(
                    name="Current Stats",
                    value=f"Avg Value: {sum(values)/len(values):,.0f} coins\nTop 10 Rate: {(top_10_count/i)*100:.3f}%\nBest Rank: #{min(ranks) if ranks else 'N/A'}",
                    inline=False
                )
                embed.add_field(
                    name="⏱️ Timing",
                    value=f"Elapsed: {elapsed_time:.0f}s\n{eta_text}\nSpeed: {i/elapsed_time:.0f} sims/sec",
                    inline=False
                )
                
                try:
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed)
                    else:
                        # For prefix commands, don't spam with updates
                        pass
                except:
                    pass  # Ignore rate limit errors on progress updates
                
                last_update_time = current_time
            
            # Simulate one crate opening using actual bot logic with REAL DATA
            try:
                # Use the same logic as real crate opening to select rank
                crate_data = self.gacha_system.crate_config[crate_type]
                rank_ranges = crate_data["rank_ranges"]
                
                # Create weighted list of rank ranges
                weighted_ranges = []
                for range_data in rank_ranges:
                    weight = int(range_data["weight"] * 100)
                    weighted_ranges.extend([range_data] * weight)
                
                # Select random range and rank
                selected_range = random.choice(weighted_ranges)
                rank = random.randint(selected_range["min"], selected_range["max"])
                ranks.append(rank)
                
                # Track special ranks
                if rank == 1:
                    rank_1_count += 1
                if rank <= 10:
                    top_10_count += 1
                if rank <= 50:
                    top_50_count += 1
                if rank <= 100:
                    top_100_count += 1
                
                # Get rarity using actual algorithm
                rarity = self.gacha_system.get_rarity_from_rank(rank)
                stars_count[rarity['stars']] += 1
                
                # Roll mutation using actual algorithm
                mutation = self.gacha_system.roll_mutation()
                if mutation:
                    mutations[mutation] = mutations.get(mutation, 0) + 1
                else:
                    mutations["none"] += 1
                
                # Get REAL player data from cache or create fallback
                player_data = await self.gacha_system.get_player_by_rank(rank)
                if not player_data:
                    # Fallback player if not in cache (like backup)
                    player_data = {
                        'rank': rank,
                        'pp': max(28000 - rank * 2, 1000),  # Same approximation as backup
                        'username': f'Player{rank}',
                        'accuracy': 99.0,
                        'play_count': 50000,
                        'country': 'US',
                        'level': 100.0
                    }
                
                # Calculate price using actual algorithm
                card_price = self.gacha_system.calculate_card_price(player_data, rarity['stars'], mutation)
                values.append(card_price)
                
            except Exception as e:
                print(f"❌ Error in simulation iteration {i}: {type(e).__name__}: {str(e)}")
                # Use fallback values like backup
                ranks.append(5000)
                values.append(1000)
                stars_count[1] += 1
                mutations["none"] += 1
        
        return {
            'values': values,
            'ranks': ranks,
            'mutations': mutations,
            'stars_count': stars_count,
            'rank_1_count': rank_1_count,
            'top_10_count': top_10_count,
            'top_50_count': top_50_count,
            'top_100_count': top_100_count,
            'total_simulated': amount
        }

    async def _show_single_result(self, ctx, crate_type, result, amount, progress_msg=None):
        """Show results for single crate simulation - edit the existing embed"""
        crate_info = self.gacha_system.crate_config[crate_type]
        values = result['values']
        
        # Calculate statistics
        avg_value = sum(values) / len(values)
        crate_cost = crate_info['price']
        profit = avg_value - crate_cost
        roi = (profit / crate_cost) * 100
        
        embed = discord.Embed(
            title=f"📊 {crate_info['name']} Simulation Results",
            description=f"**{amount:,}** crates simulated using actual bot logic",
            color=crate_info['color']
        )
        
        # Financial analysis
        embed.add_field(
            name="💰 Financial Analysis",
            value=f"**Crate Cost:** {crate_cost:,} coins\n**Average Value:** {avg_value:,.0f} coins\n**Average Profit:** {profit:,.0f} coins\n**ROI:** {roi:+.1f}%",
            inline=True
        )
        
        # Pull rates
        embed.add_field(
            name="🎯 Elite Pull Rates",
            value=f"**Rank #1:** {result['rank_1_count']:,} ({(result['rank_1_count']/amount)*100:.4f}%)\n**Top 10:** {result['top_10_count']:,} ({(result['top_10_count']/amount)*100:.3f}%)\n**Top 50:** {result['top_50_count']:,} ({(result['top_50_count']/amount)*100:.2f}%)\n**Top 100:** {result['top_100_count']:,} ({(result['top_100_count']/amount)*100:.2f}%)",
            inline=True
        )
        
        # Value stats
        best_value = max(values)
        worst_value = min(values)
        median_value = sorted(values)[len(values)//2]
        
        embed.add_field(
            name="📈 Value Statistics",
            value=f"**Highest:** {best_value:,.0f} coins\n**Lowest:** {worst_value:,.0f} coins\n**Median:** {median_value:,.0f} coins\n**Best Rank:** #{min(result['ranks']):,}",
            inline=True
        )
        
        # Star distribution
        stars_text = ""
        for stars in [5, 4, 3, 2, 1]:
            count = result['stars_count'][stars]
            percentage = (count / amount) * 100
            stars_text += f"{'★' * stars}: {count:,} ({percentage:.2f}%)\n"
        
        embed.add_field(
            name="⭐ Star Distribution",
            value=stars_text,
            inline=True
        )
        
        # Mutation stats
        mutation_text = ""
        total_cards = amount
        total_mutations = sum(count for name, count in result['mutations'].items() if name != "none")
        mutation_rate = (total_mutations / total_cards) * 100
        
        # Sort mutations by count (excluding "none")
        sorted_mutations = sorted(
            [(name, count) for name, count in result['mutations'].items() if name != "none" and count > 0],
            key=lambda x: x[1], 
            reverse=True
        )
        
        if total_mutations > 0:
            mutation_text += f"**Any Mutation:** {total_mutations:,} ({mutation_rate:.2f}%)\n\n"
            
            # Show individual mutations
            for mutation_name, count in sorted_mutations:
                percentage = (count / total_cards) * 100
                mutation_text += f"**{mutation_name.title()}:** {count:,} ({percentage:.3f}%)\n"
        else:
            mutation_text = "**No mutations found**\n(Check if mutation system is working)"
        
        # Add non-mutated cards count
        none_count = result['mutations'].get("none", 0)
        none_percentage = (none_count / total_cards) * 100
        mutation_text += f"\n**Normal:** {none_count:,} ({none_percentage:.2f}%)"
        
        embed.add_field(
            name="✨ Mutations",
            value=mutation_text,
            inline=True
        )
        
        embed.set_footer(text=f"Simulation completed using real player data and bot algorithms")
        
        # Edit the original message instead of sending new one
        if hasattr(ctx, 'edit_original_response'):
            await ctx.edit_original_response(embed=embed)
        else:
            # Use the passed progress_msg to edit instead of sending new
            if progress_msg:
                await progress_msg.edit(embed=embed)
            else:
                await ctx.send(embed=embed)

    async def _show_all_results(self, ctx, results, amount, progress_msg=None):
        """Show combined results for all crate types - edit the existing embed"""
        embed = discord.Embed(
            title="📊 Complete Gacha Simulation Results",
            description=f"**{amount:,}** crates simulated per type using actual bot logic",
            color=discord.Color.gold()
        )
        
        # Summary table
        summary_text = ""
        total_mutations_all_crates = 0
        
        for crate_type, result in results.items():
            crate_info = self.gacha_system.crate_config[crate_type]
            avg_value = sum(result['values']) / len(result['values'])
            profit = avg_value - crate_info['price']
            roi = (profit / crate_info['price']) * 100
            top_10_rate = (result['top_10_count'] / amount) * 100
            rank_1_rate = (result['rank_1_count'] / amount) * 100
            
            # Calculate mutation rate for this crate
            crate_mutations = sum(count for name, count in result['mutations'].items() if name != "none")
            mutation_rate = (crate_mutations / amount) * 100
            total_mutations_all_crates += crate_mutations
            
            summary_text += f"**{crate_info['name']}**\n"
            summary_text += f"Avg Profit: {profit:,.0f} (+{roi:.1f}%)\n"
            summary_text += f"Rank #1: {rank_1_rate:.4f}% | Top 10: {top_10_rate:.3f}%\n"
            summary_text += f"Mutations: {mutation_rate:.2f}%\n\n"
        
        embed.add_field(
            name="💰 Profitability Summary",
            value=summary_text,
            inline=False
        )
        
        # Best crate analysis
        best_roi_crate = max(results.items(), key=lambda x: ((sum(x[1]['values'])/len(x[1]['values'])) - self.gacha_system.crate_config[x[0]]['price']) / self.gacha_system.crate_config[x[0]]['price'])
        best_value_crate = max(results.items(), key=lambda x: sum(x[1]['values'])/len(x[1]['values']))
        
        best_roi_name = self.gacha_system.crate_config[best_roi_crate[0]]['name']
        best_value_name = self.gacha_system.crate_config[best_value_crate[0]]['name']
        
        embed.add_field(
            name="🏆 Best Crates",
            value=f"**Best ROI:** {best_roi_name}\n**Highest Avg Value:** {best_value_name}",
            inline=True
        )
        
        # Total stats including mutations
        total_simulated = amount * 5
        total_rank_1 = sum(result['rank_1_count'] for result in results.values())
        overall_mutation_rate = (total_mutations_all_crates / total_simulated) * 100
        
        embed.add_field(
            name="📈 Total Statistics",
            value=f"**Total Simulated:** {total_simulated:,}\n**Total Rank #1:** {total_rank_1:,}\n**Overall #1 Rate:** {(total_rank_1/total_simulated)*100:.4f}%\n**Overall Mutation Rate:** {overall_mutation_rate:.2f}%",
            inline=True
        )
        
        embed.set_footer(text="All values calculated using real player data and actual bot algorithms")
        
        # Edit the original message instead of sending new one
        if hasattr(ctx, 'edit_original_response'):
            await ctx.edit_original_response(embed=embed)
        else:
            # Use the passed progress_msg to edit instead of sending new
            if progress_msg:
                await progress_msg.edit(embed=embed)
            else:
                await ctx.send(embed=embed)   

    async def handle_stats_command(self, ctx, target_user=None, interaction=None):
        """Show comprehensive user statistics with current and historical data"""
        try:
            if hasattr(ctx, 'response'):
                await ctx.response.defer()
            else:
                message = await ctx.send("Loading statistics...")

            # Determine which user to check
            if target_user is None:
                # Check own stats
                user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
                username = ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name
                user_mention = ctx.author.mention if hasattr(ctx, 'author') else ctx.user.mention
            else:
                # Check another user's stats
                user_id = target_user.id
                username = target_user.display_name
                user_mention = target_user.mention
            
            user_data = self.get_user_gacha_data(user_id)
            cards = user_data.get("cards", {})
            
            # Get historical stats
            historical = user_data.get("achievement_stats", {})
            total_opens = user_data.get("total_opens", 0)  # ✅ Check actual opens

            # Current stats (from current cards)
            total_cards = len(cards)
            total_value = sum(card.get("price", 0) for card in cards.values())
            currency = user_data.get("currency", 0)

            # ✅ FIX: Check total_opens instead of just current cards
            if total_opens == 0:  # ✅ Actually hasn't opened crates
                embed = discord.Embed(
                    title=f"{username}'s Collection Statistics",
                    description=f"{user_mention} hasn't opened any crates yet!" + (" Use `/osuopen` to start collecting." if target_user is None else ""),
                    color=discord.Color.blue()
                )
                
                if hasattr(ctx, 'edit_original_response'):
                    await ctx.edit_original_response(embed=embed)
                else:
                    await message.edit(embed=embed)
                return

            # ✅ NEW: Show message for users who opened crates but have no cards (sold them all)
            if total_cards == 0 and total_opens > 0:
                embed = discord.Embed(
                    title=f"{username}'s Collection Statistics",
                    description=f"{user_mention} has opened **{total_opens}** crates but currently has no cards.\n\n"
                            f"💰 **Current Balance:** {currency:,} coins\n"
                            f"📈 **Historical Stats Available Below**" + 
                            (" \n\n💡 Use `/osuopen` to get more cards!" if target_user is None else ""),
                    color=discord.Color.orange()
                )
                
                # Still show historical achievements and stats even with no current cards
                # Continue with the rest of the stats logic below...
            else:
                # User has cards - create normal embed
                embed = discord.Embed(
                    title=f"{username}'s Collection Statistics",
                    description=f"Complete overview of {user_mention}'s osu! gacha collection",
                    color=discord.Color.gold()
                )

            # Get stats regardless of current cards (for historical data)
            total_opens = user_data.get("total_opens", 0)
            daily_count = user_data.get("daily_count", 0)
            
            # Historical stats (all-time bests)
            max_cards_ever = historical.get("max_cards", total_cards)
            max_currency_ever = historical.get("max_currency", currency)
            max_value_ever = historical.get("max_collection_value", total_value)
            countries_ever = len(historical.get("countries_ever", []))
            mutations_ever = len(historical.get("mutations_ever", []))
            
            # Only calculate current card stats if user has cards
            if total_cards > 0:
                # Star distribution (current)
                star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
                for card in cards.values():
                    stars = card.get("stars", 1)
                    star_counts[stars] = star_counts.get(stars, 0) + 1
                
                # Mutation stats (current)
                mutation_counts = {}
                total_mutations = 0
                for card in cards.values():
                    mutation = card.get("mutation")
                    if mutation:
                        total_mutations += 1
                        mutation_counts[mutation] = mutation_counts.get(mutation, 0) + 1
                
                # Country diversity (current)
                countries = set()
                for card in cards.values():
                    countries.add(card["player_data"]["country"])
                
                # Best cards (current and historical)
                current_best_rank = min((card["player_data"]["rank"] for card in cards.values()), default=0)
                current_highest_value = max((card.get("price", 0) for card in cards.values()), default=0)
                best_rank_ever = historical.get("best_rank_ever", current_best_rank)
                highest_card_value_ever = historical.get("highest_card_value", current_highest_value)
                
                # Basic stats (current)
                embed.add_field(
                    name="Collection Overview",
                    value=f"**Total Cards:** {total_cards:,}\n**Collection Value:** {total_value:,} coins\n**Current Balance:** {currency:,} coins\n**Total Worth:** {total_value + currency:,} coins",
                    inline=True
                )
                
                # Star distribution (current)
                star_text = ""
                for stars in [6, 5, 4, 3, 2, 1]:
                    count = star_counts[stars]
                    if count > 0:
                        star_symbols = "★" * stars
                        percentage = (count / total_cards * 100)
                        star_text += f"**{star_symbols}:** {count} ({percentage:.1f}%)\n"
                
                embed.add_field(
                    name="Star Distribution",
                    value=star_text if star_text else "No cards yet",
                    inline=True
                )
                
                # Mutation stats (current, with legacy mutation handling)
                if total_mutations > 0:
                    mutation_rate = (total_mutations / total_cards * 100)
                    mutation_text = f"**Total Mutations:** {total_mutations} ({mutation_rate:.1f}%)\n"
                    
                    # Top 3 mutations with legacy handling
                    sorted_mutations = sorted(mutation_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                    for mutation, count in sorted_mutations:
                        # Handle legacy mutations that no longer exist
                        if mutation in self.gacha_system.mutations:
                            mutation_name = self.gacha_system.mutations[mutation]["name"]
                        else:
                            # Legacy mutation mapping
                            legacy_mutations = {
                                "rainbow": "RAINBOW (Legacy)",
                                "neon": "SHOCKED (Legacy)"
                            }
                            mutation_name = legacy_mutations.get(mutation, mutation.upper())
                        
                        mutation_text += f"**{mutation_name}:** {count}\n"
                    
                    embed.add_field(
                        name="Mutations",
                        value=mutation_text,
                        inline=True
                    )
                
                # Current vs Historical comparison (if applicable)
                if current_best_rank != best_rank_ever or len(countries) != countries_ever or current_highest_value != highest_card_value_ever:
                    embed.add_field(
                        name="Current vs Best",
                        value=f"**Current Rank:** #{current_best_rank:,} (Best: #{best_rank_ever:,})\n**Current Countries:** {len(countries)} (Total: {countries_ever})\n**Current Top Card:** {current_highest_value:,} (Best: {highest_card_value_ever:,})",
                        inline=True
                    )
                
                # Collection analysis (current)
                if total_cards >= 10:
                    avg_value = total_value / total_cards
                    elite_cards = sum(1 for card in cards.values() if card["player_data"]["rank"] <= 100)
                    elite_percentage = (elite_cards / total_cards * 100)
                    
                    embed.add_field(
                        name="Collection Analysis",
                        value=f"**Average Value:** {avg_value:,.0f} coins\n**Elite Cards (Top 100):** {elite_cards} ({elite_percentage:.1f}%)\n**Mutation Rate:** {(total_mutations / total_cards * 100):.1f}%",
                        inline=False
                    )
            else:
                # No current cards but has opened crates - show balance info
                best_rank_ever = historical.get("best_rank_ever", 0)
                highest_card_value_ever = historical.get("highest_card_value", 0)
                
                embed.add_field(
                    name="Current Status",
                    value=f"**Cards:** 0 (sold or never pulled good ones)\n**Balance:** {currency:,} coins\n**Crates Opened:** {total_opens:,}",
                    inline=True
                )

            # Achievement stats
            achievements = user_data.get("achievements", {})
            achievement_count = len(achievements)
            
            # Records (historical) - always show this
            embed.add_field(
                name="📊 Records (All-Time)",
                value=f"**Best Rank:** #{best_rank_ever:,}\n**Most Valuable Card:** {highest_card_value_ever:,} coins\n**Countries Visited:** {countries_ever}\n**Mutations Found:** {mutations_ever}\n**Achievements:** {achievement_count}",
                inline=True
            )
            
            # Activity stats - always show this
            embed.add_field(
                name="Activity",
                value=f"**Crates Opened:** {total_opens:,}\n**Daily Claims:** {daily_count}",
                inline=True
            )
            
            # Historical achievements section if different from current
            if max_cards_ever > total_cards or max_currency_ever > currency or max_value_ever > total_value:
                embed.add_field(
                    name="🏆 Historical Bests",
                    value=f"**Peak Cards:** {max_cards_ever:,}\n**Peak Currency:** {max_currency_ever:,} coins\n**Peak Collection Value:** {max_value_ever:,} coins",
                    inline=True
                )
            
            # Recent achievements (last 5) - always show if any exist
            if achievements:
                recent_achievements = sorted(achievements.items(), key=lambda x: x[1], reverse=True)[:5]
                achievement_text = ""
                
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
                        achievement_text += f"**{name}** - {time_text}\n"
                
                if achievement_text:
                    embed.add_field(
                        name="Recent Achievements",
                        value=achievement_text,
                        inline=False
                    )
            
            # Progress towards next achievements (only show for own stats, using historical data)
            if target_user is None:
                progress_text = ""
                
                # Use historical maximums for achievement progress
                if "first_card" not in achievements and max_cards_ever == 0:
                    progress_text += "**First Steps:** Open your first crate\n"
                elif "collector_100" not in achievements and max_cards_ever < 100:
                    remaining = 100 - max_cards_ever
                    progress_text += f"**Collector:** {remaining} more cards needed (Progress: {max_cards_ever}/100)\n"
                elif "master_collector_500" not in achievements and max_cards_ever < 500:
                    remaining = 500 - max_cards_ever
                    progress_text += f"**Master Collector:** {remaining} more cards needed (Progress: {max_cards_ever}/500)\n"
                
                if "millionaire" not in achievements and max_currency_ever < 1000000:
                    remaining = 1000000 - max_currency_ever
                    progress_text += f"**Millionaire:** {remaining:,} more coins needed (Peak: {max_currency_ever:,})\n"
                
                if "mutation_master" not in achievements and mutations_ever < 5:
                    remaining = 5 - mutations_ever
                    progress_text += f"**Mutation Master:** {remaining} more mutation types needed (Found: {mutations_ever}/5)\n"
                
                if "world_traveler" not in achievements and countries_ever < 10:
                    remaining = 10 - countries_ever
                    progress_text += f"**World Traveler:** {remaining} more countries needed (Visited: {countries_ever}/10)\n"
                
                if progress_text:
                    embed.add_field(
                        name="Next Goals",
                        value=progress_text[:3] if isinstance(progress_text, list) else progress_text,
                        inline=False
                    )
            
            embed.set_footer(text="Use /osuleaderboard to compare with other players")
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=embed)
            else:
                await message.edit(embed=embed)
                
        except Exception as e:
            print(f"Error in stats command: {e}")
            error_embed = discord.Embed(
                title="Error",
                description="There was an error loading statistics. Please try again later.",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=error_embed)
            elif hasattr(ctx, 'response'):
                await ctx.response.edit_message(embed=error_embed)
            else:
                await ctx.send(embed=error_embed)
                
    async def handle_crates_command(self, ctx, interaction=None):
        """Show user's available crates (matches backup format)"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        embed = discord.Embed(
            title="Your Crates",
            color=discord.Color.blue()
        )
        
        total_crates = 0
        crate_list = []
        
        for crate_type, crate_info in self.gacha_system.crate_config.items():
            count = user_data["crates"].get(crate_type, 0)
            total_crates += count
            
            if count > 0:
                crate_list.append(f"{crate_info['emoji']} **{crate_info['name']}**: {count}")
            else:
                crate_list.append(f"{crate_info['emoji']} **{crate_info['name']}**: 0")
        
        if total_crates == 0:
            embed.description = "You don't have any crates!\n\n💡 Use `/osudaily` to get free crates daily"
        else:
            embed.description = "\n".join(crate_list)
            embed.add_field(
                name="Total Crates",
                value=f"**{total_crates}** crates available",
                inline=False
            )
        
        embed.set_footer(text="Use /osuopen [crate] to open crates")
        
        if interaction:
            await interaction.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)

    async def show_crate_help(self, ctx, interaction=None):
        """Show crate help information"""
        crate_names = [crate_info['name'] for crate_info in self.gacha_system.crate_config.values()]
        
        embed = discord.Embed(
            title="❌ Invalid Crate",
            description=f"Available crates: {', '.join(crate_names)}",
            color=discord.Color.red()
        )
        
        if interaction:
            await interaction.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)


    async def _preview_command(self, ctx, search, mutation=None):
        """Preview any player's card from top 10k with optional mutation"""
        try:
            if hasattr(ctx, 'response'):
                await ctx.response.defer()
            else:
                message = await ctx.send("🔍 Searching player...")

            # Parse search for mutation syntax: "mrekk rainbow" or "cookiezi flashback"
            search_parts = search.split()
            if len(search_parts) > 1:
                potential_mutation = search_parts[-1].lower()
                if potential_mutation in self.gacha_system.mutations:
                    mutation = potential_mutation
                    search = " ".join(search_parts[:-1])
            
            player = None
            flashback_year = None
            
            # Check if requesting flashback card specifically
            if mutation and mutation.lower() == "flashback":
                # ✅ FIX: Only allow flashback mutation for existing flashback players
                found_flashback = False
                for fb_name, fb_data in self.gacha_system.flashback_cards.items():
                    if fb_name.lower() == search.lower():
                        player = fb_data["player_data"]
                        flashback_year = fb_data["flashback_year"]
                        found_flashback = True
                        break
                
                if not found_flashback:
                    # Show error with available flashback players
                    available_flashback = ", ".join(self.gacha_system.flashback_cards.keys())
                    embed = discord.Embed(
                        title="❌ Invalid Flashback Player",
                        description=f"**'{search}'** is not available as a flashback card.\n\n"
                                f"🎯 **Available flashback players:**\n{available_flashback}\n\n"
                                f"💡 **Usage:** `/osupreview cookiezi flashback`",
                        color=discord.Color.red()
                    )
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed)
                    else:
                        await message.edit(embed=embed)
                    return
            else:
                # Regular player search (non-flashback mutations)
                player = await self.gacha_system.search_player_preview(search)
                
                # ✅ NEW: Prevent flashback mutation on regular players
                if mutation and mutation.lower() == "flashback":
                    embed = discord.Embed(
                        title="❌ Invalid Mutation",
                        description=f"The flashback mutation can only be used with predefined flashback players.\n\n"
                                f"🎯 **Available flashback players:**\n{', '.join(self.gacha_system.flashback_cards.keys())}\n\n"
                                f"💡 **For regular players, try other mutations like:** `rainbow`, `cosmic`, `immortal`, etc.",
                        color=discord.Color.red()
                    )
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed)
                    else:
                        await message.edit(embed=embed)
                    return

            if not player:
                embed = discord.Embed(
                    title="❌ Player Not Found",
                    description=f"No player found for **'{search}'** in top 10k players.",
                    color=discord.Color.red()
                )
                if hasattr(ctx, 'edit_original_response'):
                    await ctx.edit_original_response(embed=embed)
                else:
                    await message.edit(embed=embed)
                return

            # For flashback cards, force 6 stars
            if mutation == "flashback":
                rarity_info = {"stars": 6, "name": flashback_year, "color": 0xFFD700}
            else:
                rarity_info = self.gacha_system.get_rarity_from_rank(player['rank'])

            # Calculate card price with mutation
            card_price = self.gacha_system.calculate_card_price(player, rarity_info["stars"], mutation)

            # Create preview embed
            stars_display = "★" * rarity_info["stars"]
            
            title = f"Preview: {player['username']}"
            embed_color = rarity_info["color"]
            
            if mutation:
                mutation_name = self.gacha_system.mutations[mutation]["name"]
                mutation_emoji = self.gacha_system.mutations[mutation]["emoji"]
                title += f" - {mutation_name} {mutation_emoji}"
                
                mutation_color = self.gacha_system.mutations[mutation]["color"]
                if isinstance(mutation_color, str):
                    embed_color = int(mutation_color.lstrip('#'), 16)
                else:
                    embed_color = mutation_color

            embed = discord.Embed(
                title=title,
                description=f"**{rarity_info['name']}\n{stars_display}**",
                color=embed_color
            )

            # Add fields...
            embed.add_field(
                name="",
                value=f"**Rank** #{player['rank']:,}\n**PP** {player['pp']:,}\n**Accuracy** {player['accuracy']}%",
                inline=True
            )

            embed.add_field(
                name="",
                value=f"**Country** {player['country']}\n**Level** {player['level']}\n**Plays** {player['play_count']:,}",
                inline=True
            )

            # Add mutation info if present
            if mutation:
                mutation_info = self.gacha_system.mutations[mutation]
                embed.add_field(
                    name=f"{mutation_info['name']} {mutation_info['emoji']}",
                    value=f"{mutation_info['description']}",
                    inline=False
                )
                
                # ✅ NEW: Add special note for flashback cards
                if mutation == "flashback":
                    # Find flashback era
                    flashback_era = None
                    for key, data in self.gacha_system.flashback_cards.items():
                        if data["player_data"]["username"].lower() == player["username"].lower():
                            flashback_era = data["flashback_era"]
                            break
                    
                    if flashback_era:
                        embed.add_field(
                            name=f"*{flashback_era}*",
                            value=f"",
                            inline=False
                        )

            embed.set_footer(text="🔍 This is a preview - you don't own this card")

            # Generate card image
            try:
                card_image = await self.gacha_system.create_card_image(
                    player, rarity_info["stars"], mutation, card_price, flashback_year
                )

                if card_image:
                    mutation_suffix = f"_{mutation}" if mutation else ""
                    filename = f"preview_{player['user_id']}{mutation_suffix}.png"
                    file = discord.File(card_image, filename=filename)
                    embed.set_image(url=f"attachment://{filename}")
                    
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed, attachments=[file])
                    else:
                        await message.edit(embed=embed, attachments=[file])
                else:
                    if hasattr(ctx, 'edit_original_response'):
                        await ctx.edit_original_response(embed=embed)
                    else:
                        await message.edit(embed=embed)
                        
            except Exception as e:
                print(f"Error generating preview image: {e}")
                if hasattr(ctx, 'edit_original_response'):
                    await ctx.edit_original_response(embed=embed)
                else:
                    await message.edit(embed=embed)
                    
        except Exception as e:
            print(f"Major error in preview command: {e}")
            error_embed = discord.Embed(
                title="❌ Preview Failed",
                description="Failed to preview card. Try again later.",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=error_embed)
            else:
                await ctx.send(embed=error_embed)

    async def handle_achievements_command(self, ctx, interaction=None):
        """Show all achievements and user's progress with emojis"""
        try:
            if hasattr(ctx, 'response'):
                await ctx.response.defer()
            else:
                message = await ctx.send("Loading achievements...")

            user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
            username = ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name
            user_data = self.get_user_gacha_data(user_id)
            
            user_achievements = user_data.get("achievements", {})
            total_achievements = len(self.gacha_system.achievement_definitions)
            unlocked_count = len(user_achievements)
            
            embed = discord.Embed(
                title=f"🏆 {username}'s Achievements",
                description=f"Progress: **{unlocked_count}/{total_achievements}** achievements unlocked ({(unlocked_count/total_achievements*100):.1f}%)",
                color=discord.Color.gold()
            )
            
            # Group achievements by category
            achievement_categories = {
                "Collection": ["first_card", "collector_100", "master_collector_500"],
                "Rarity Hunting": ["legend_hunter", "six_star_collector", "five_star_master", "four_star_expert", "elite_club", "champion"],
                "Mutations": ["mutation_master", "mutation_holographic", "mutation_immortal", "mutation_prismatic"],
                "Wealth": ["wealthy_collector", "millionaire", "big_spender"], 
                "Activity": ["daily_devotee", "crate_crusher", "crate_master", "opening_legend", "trading_partner", "bargain_hunter"],
                "Special": ["world_traveler", "country_collector", "pp_hunter", "accuracy_perfectionist", "collection_curator", "lucky_streak"]
            }
            
            for category, achievement_ids in achievement_categories.items():
                category_text = []
                
                for achievement_id in achievement_ids:
                    if achievement_id in self.gacha_system.achievement_definitions:
                        achievement_def = self.gacha_system.achievement_definitions[achievement_id]
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
                            
                            status = f"✅ **{name}**  - {description} - *{time_text}*"
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
            
            # Progress towards next achievements using historical data
            historical = user_data.get("achievement_stats", {})
            progress_text = []
            
            max_cards = historical.get("max_cards", len(user_data.get("cards", {})))
            max_currency = historical.get("max_currency", user_data.get("currency", 0))
            mutations_ever = len(historical.get("mutations_ever", []))
            countries_ever = len(historical.get("countries_ever", []))
            
            if "first_card" not in user_achievements and max_cards == 0:
                progress_text.append("🎯 **First Steps:** Open your first crate")
            elif "collector_100" not in user_achievements and max_cards < 100:
                remaining = 100 - max_cards
                progress_text.append(f"📚 **Collector:** {remaining} more cards needed (Progress: {max_cards}/100)")
            elif "master_collector_500" not in user_achievements and max_cards < 500:
                remaining = 500 - max_cards
                progress_text.append(f"🏆 **Master Collector:** {remaining} more cards needed (Progress: {max_cards}/500)")
            
            if "millionaire" not in user_achievements and max_currency < 1000000:
                remaining = 1000000 - max_currency
                progress_text.append(f"💸 **Millionaire:** {remaining:,} more coins needed (Peak: {max_currency:,})")
            
            if "mutation_master" not in user_achievements and mutations_ever < 5:
                remaining = 5 - mutations_ever
                progress_text.append(f"🧬 **Mutation Master:** {remaining} more mutation types needed (Found: {mutations_ever}/5)")
            
            if "world_traveler" not in user_achievements and countries_ever < 10:
                remaining = 10 - countries_ever
                progress_text.append(f"🌍 **World Traveler:** {remaining} more countries needed (Visited: {countries_ever}/10)")
            
            if progress_text:
                embed.add_field(
                    name="🎯 Next Goals",
                    value="\n".join(progress_text[:3]),  # Show top 3
                    inline=False
                )
            
            embed.set_footer(text="Keep playing to unlock more achievements! 🎮")
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=embed)
            else:
                await message.edit(embed=embed)
                
        except Exception as e:
            print(f"Error in achievements command: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="There was an error loading achievements. Please try again later.",
                color=discord.Color.red()
            )
            
            if hasattr(ctx, 'edit_original_response'):
                await ctx.edit_original_response(embed=error_embed)
            elif hasattr(ctx, 'response'):
                await ctx.response.edit_message(embed=error_embed)
            else:
                await ctx.send(embed=error_embed)

    async def handle_toggle_confirmations(self, ctx_or_interaction):
        """Toggle confirmation prompts on/off"""
        # Determine if it's a context or interaction
        if hasattr(ctx_or_interaction, 'response'):
            # It's an interaction
            user_id = ctx_or_interaction.user.id
            is_interaction = True
        else:
            # It's a context
            user_id = ctx_or_interaction.author.id
            is_interaction = False
        
        user_data = self.get_user_gacha_data(user_id)
        
        # Toggle the setting
        current_setting = user_data.get("confirmations_enabled", True)
        user_data["confirmations_enabled"] = not current_setting
        
        # Save data
        self.save_user_data()
        
        status = "enabled" if user_data["confirmations_enabled"] else "disabled"
        emoji = "✅" if user_data["confirmations_enabled"] else "❌"
        
        embed = discord.Embed(
            title="Confirmation Settings Updated",
            description=f"{emoji} Confirmation prompts are now **{status}**",
            color=discord.Color.green() if user_data["confirmations_enabled"] else discord.Color.orange()
        )
        
        embed.add_field(
            name="What this affects:",
            value="• Buying crates\n• Selling cards\n• Bulk operations\n• Large purchases (5M+ coins)",
            inline=False
        )
        
        embed.add_field(
            name="Safety note:",
            value="Large purchases (5M+ coins) will still show confirmations for safety",
            inline=False
        )
        
        embed.set_footer(text="Use /osutoggle again to change this setting")
        
        if is_interaction:
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)

    async def handle_wipe_command(self, ctx, target, interaction=None):
        """Admin-only command to wipe a user's gacha data completely"""
        
        # Check if user is the bot owner (dinonuwg)
        user_name = ctx.author.name if hasattr(ctx, 'author') else ctx.user.name
        if user_name.lower() != "dinonuwg":
            embed = discord.Embed(
                title="Access Denied",
                description="This command is restricted to the bot owner only.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return

        if not target:
            embed = discord.Embed(
                title="Usage",
                description="**Wipe User Data:** `!owipe @user`",
                color=discord.Color.blue()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        # Get user data to show what will be wiped
        target_data = self.get_user_gacha_data(target.id)
        
        # Calculate stats for confirmation
        total_cards = len(target_data.get("cards", {}))
        total_currency = target_data.get("currency", 0)
        total_crates = sum(target_data.get("crates", {}).values())
        total_opens = target_data.get("total_opens", 0)
        
        # Create confirmation embed
        embed = discord.Embed(
            title="⚠️ CONFIRM DATA WIPE",
            description=f"Are you sure you want to **COMPLETELY WIPE** all gacha data for {target.display_name}?",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="📊 Current Data",
            value=f"**Cards:** {total_cards:,}\n"
                f"**Currency:** {total_currency:,} coins\n"
                f"**Crates:** {total_crates:,}\n"
                f"**Total Opens:** {total_opens:,}",
            inline=True
        )
        
        embed.add_field(
            name="⚠️ Warning",
            value="This action is **IRREVERSIBLE**!\nAll cards, coins, crates, achievements,\nand stats will be permanently deleted.",
            inline=False
        )
        
        embed.set_footer(text="This action cannot be undone!")
        
        # Create confirmation view
        view = WipeConfirmationView(target.id, target.display_name, self)
        
        if interaction:
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def handle_give_command(self, ctx, target, amount_or_player, mutation=None, interaction=None):
        """Admin-only command to give coins or cards to players"""
        
        # Check if user is the bot owner (dinonuwg)
        user_name = ctx.author.name if hasattr(ctx, 'author') else ctx.user.name
        if user_name.lower() != "dinonuwg":
            embed = discord.Embed(
                title="Access Denied",
                description="This command is restricted to the bot owner only.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed)
            return

        if not target:
            embed = discord.Embed(
                title="Usage",
                description="**Give Coins:** `!ogive @user 1000`\n"
                        "**Give Card:** `!ogive @user mrekk` (random mutation)\n"
                        "**Give Card with Mutation:** `!ogive @user mrekk immortal`",
                color=discord.Color.blue()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        if not amount_or_player:
            embed = discord.Embed(
                title="Missing Arguments",
                description="Please specify coins amount or player name!",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        # Get user data
        target_data = self.get_user_gacha_data(target.id)

        # Check if it's a coin amount (number)
        try:
            coin_amount = int(amount_or_player)
            
            # Give coins
            target_data["currency"] += coin_amount
            self.save_user_data()
            
            embed = discord.Embed(
                title="Coins Given!",
                description=f"✅ **{target.display_name}** received **{coin_amount:,} coins**!\n\n"
                        f"**New Balance:** {target_data['currency']:,} coins",
                color=discord.Color.green()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        except ValueError:
            # It's a player name, proceed with card giving
            pass

        # Give card logic
        player_name = amount_or_player.lower()

        # Check if requesting flashback card specifically
        found_player = None
        flashback_year = None
        
        if mutation and mutation.lower() == "flashback":
            # Look for flashback player first
            for fb_name, fb_data in self.gacha_system.flashback_cards.items():
                if fb_name.lower() == player_name:
                    found_player = fb_data["player_data"]
                    flashback_year = fb_data["flashback_year"]
                    break

        if not found_player:
            # Use the same search method as preview command
            found_player = await self.gacha_system.search_player_preview(player_name)

        if not found_player:
            available_flashback = ""
            if mutation and mutation.lower() == "flashback":
                available_flashback = f"\n\n**Available flashback players:** {', '.join(self.gacha_system.flashback_cards.keys())}"
            
            embed = discord.Embed(
                title="Player Not Found",
                description=f"Could not find player: `{amount_or_player}`\n\n"
                        f"Make sure the player is in the top 10k rankings.\n"
                        f"Try searching by exact username or rank number.{available_flashback}",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return

        # Determine mutation
        selected_mutation = None
        if mutation:
            mutation_lower = mutation.lower()
            
            # Check if mutation exists
            if mutation_lower in self.gacha_system.mutations:
                selected_mutation = mutation_lower
            else:
                # List available mutations
                available_mutations = list(self.gacha_system.mutations.keys())
                embed = discord.Embed(
                    title="Invalid Mutation",
                    description=f"Unknown mutation: `{mutation}`\n\n"
                            f"**Available mutations:**\n" + 
                            "\n".join([f"• `{mut}`" for mut in available_mutations]),
                    color=discord.Color.red()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
            
        # For flashback cards, force 6 stars and use flashback year
        if mutation and mutation.lower() == "flashback":
            rarity_info = {"stars": 6, "name": flashback_year, "color": 0xFFD700}
        else:
            rarity_info = self.gacha_system.get_rarity_from_rank(found_player['rank'])

        # Calculate card rarity and price
        player_rank = found_player['rank']
        if selected_mutation != "flashback":  # Don't override flashback rarity
            rarity_info = self.gacha_system.get_rarity_from_rank(player_rank)

        # Calculate price with mutation
        card_price = self.gacha_system.calculate_card_price(found_player, rarity_info["stars"], selected_mutation)

        # Generate unique card ID
        card_id = self.gacha_system.generate_card_id(found_player, rarity_info["stars"], selected_mutation)

        # Create card data
        card_data = {
            "player_data": found_player,
            "stars": rarity_info["stars"],
            "rarity_name": rarity_info["name"],
            "rarity_color": rarity_info["color"],
            "obtained_at": time.time(),
            "crate_type": "admin_gift",  # Special marker for admin-given cards
            "mutation": selected_mutation,
            "price": card_price,
            "favorite": False
        }

        # Add flashback year to card data if it's a flashback card
        if selected_mutation == "flashback" and flashback_year:
            card_data["flashback_year"] = flashback_year

        # Add card to user's collection
        if "cards" not in target_data:
            target_data["cards"] = {}

        target_data["cards"][card_id] = card_data

        # Save data
        self.save_user_data()

        # Create success embed
        mutation_text = ""
        if selected_mutation:
            mutation_name = self.gacha_system.mutations[selected_mutation]["name"]
            mutation_emoji = self.gacha_system.mutations[selected_mutation]["emoji"]
            mutation_text = f" - {mutation_name} {mutation_emoji}"

        # For display, use flashback year if available
        display_rarity = rarity_info["name"]
        if selected_mutation == "flashback" and flashback_year:
            display_rarity = flashback_year

        embed = discord.Embed(
            title="Card Given!",
            description=f"✅ **{target.display_name}** received a new card!\n\n"
                    f"**{'⭐' * rarity_info['stars']} {found_player['username']}{mutation_text}**\n"
                    f"#{found_player['rank']:,} • {found_player['pp']:,} PP • {card_price:,} coins\n\n"
                    f"**Rarity:** {display_rarity}",
            color=rarity_info["color"]
        )

        embed.add_field(
            name="Player Stats",
            value=f"**Country:** {found_player['country']}\n"
                f"**Accuracy:** {found_player['accuracy']}%\n"
                f"**Play Count:** {found_player['play_count']:,}",
            inline=True
        )

        if selected_mutation:
            mutation_info = self.gacha_system.mutations[selected_mutation]
            embed.add_field(
                name=f"Mutation: {mutation_info['name']} {mutation_info['emoji']}",
                value=mutation_info['description'],
                inline=False
            )

        embed.set_footer(text="Admin Gift • Use /osucard to view the card")

        if interaction:
            await interaction.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)

    async def handle_help_command(self, ctx, interaction=None):
        """Comprehensive help command explaining the gacha system"""
        embed = discord.Embed(
            title="osu! Gacha System Guide",
            description="Welcome to the osu! gacha system! Collect cards of top osu! players, trade with friends, and build your collection.",
            color=discord.Color.blue()
        )
        
        # Getting Started
        embed.add_field(
            name="Getting Started",
            value="• Use `/osudaily` to get free coins and crates daily\n• Use `/osustore` to buy crates with coins\n• Use `/osuopen [crate]` to open crates and get player cards\n• Check `/osubalance` to see your coins and crates",
            inline=False
        )
        
        # Crate Types
        crate_info_text = ""
        for crate_type, crate_data in self.gacha_system.crate_config.items():
            price = crate_data['price']
            emoji = crate_data['emoji']
            name = crate_data['name']
            crate_info_text += f"{emoji} **{name}** - {price:,} coins\n"
        
        embed.add_field(
            name="Crate Types",
            value=crate_info_text,
            inline=True
        )
        
        # Card Rarities
        rarity_text = ""
        for rank_range, rarity_info in {
            "Rank #1": {"stars": 6, "name": "Limit Breaker", "color": "💗"},
            "Rank #2-5": {"stars": 6, "name": "Divine", "color": "✨"},
            "Rank #6-10": {"stars": 5, "name": "Transcendent", "color": "💜"},
            "Rank #11-50": {"stars": 4, "name": "Mythical", "color": "🟠"},
            "Rank #51-100": {"stars": 4, "name": "Legend", "color": "🟡"},
            "Rank #101-500": {"stars": 3, "name": "Epic", "color": "🟣"},
            "Rank #501-2500": {"stars": 3, "name": "Rare", "color": "🔵"},
            "Rank #2501-5000": {"stars": 2, "name": "Uncommon", "color": "🟢"},
            "Rank #5001-10000": {"stars": 1, "name": "Common", "color": "⚫"}
        }.items():
            stars = "★" * rarity_info["stars"]
            rarity_text += f"{rarity_info['color']} **{stars} {rarity_info['name']}** - {rank_range}\n"
        
        embed.add_field(
            name="Card Rarities",
            value=rarity_text,
            inline=True
        )
        
        # Mutations
        mutation_text = "🧬 **Mutations** are rare card variants with special effects!\n\n"
        mutation_examples = []
        for mutation_id, mutation_data in list(self.gacha_system.mutations.items())[:10]: 
            name = mutation_data["name"]
            emoji = mutation_data["emoji"]
            rarity = mutation_data["rarity"]
            mutation_examples.append(f"{emoji} **{name}** - {rarity*100:.1f}% chance")
        
        mutation_text += "\n".join(mutation_examples)
        mutation_text += f"\n\n**Total mutation chance:** {GAME_CONFIG['mutation_chance']*100:.0f}%"

        # Add flashback cards section
        if self.gacha_system.flashback_cards:
            mutation_text += "\n\n⬅️ **FLASHBACK Cards** - Legendary players from past eras:\n"
            flashback_list = []
            for player_name, data in list(self.gacha_system.flashback_cards.items())[:5]:  # Show first 5
                year = data["flashback_year"]
                era = data["flashback_era"]
                flashback_list.append(f"• **{player_name.title()}** ({year}) - {era}")
            
            mutation_text += "\n".join(flashback_list)
            if len(self.gacha_system.flashback_cards) > 5:
                mutation_text += f"\n... and {len(self.gacha_system.flashback_cards) - 5} more legendary players!"
            
            mutation_text += "\n*Back in my day...*"
        
        embed.add_field(
            name="Mutations",
            value=mutation_text,
            inline=False
        )
        
        # Commands Overview
        commands_text = """**Core Commands:**
    • `/osudaily` - Claim daily rewards
    • `/osuopen [crate] [amount]` - Open 1-5 crates
    • `/osustore` - Buy crates with coins
    • `/osubalance` - View coins and crates
    • `/osucards` - View your collection

    **Collection Management:**
    • `/osucard [player]` - View specific card
    • `/osufavorite [player]` - Protect cards from selling
    • `/osusell [player]` - Sell cards for coins

    **Trading & Economy:**
    • `/osutrade @user` - Trade with other players
    • `/osusellbulk [players]` - Sell multiple cards
    • `/osusellall [rarity] yes` - Sell all cards of rarity

    **Information:**
    • `/osustats [@user]` - View collection statistics
    • `/osuachievements` - View achievement progress
    • `/osuleaderboard` - See top collectors
    • `/osupreview [player]` - Preview any card"""
        
        embed.add_field(
            name="Commands",
            value=commands_text,
            inline=False
        )
        # Add PvP section
        embed.add_field(
            name="PvP Games",
            value="• `/osupvp` - Challenge players to PvP games\n"
                "• `/osupvpstats` - View your PvP statistics\n"
                "• **PP Duel** - Compare card PP values\n"
                "• **Rank Guesser** - Guess rank from stats\n"
                "• **Background Guesser** - Guess songs from beatmap backgrounds",
            inline=False
        )
        
        # Advanced Features
        advanced_text = """**Achievements:** Complete challenges to earn titles and bragging rights

    **Statistics:** Track your best pulls, collection value, and countries visited

    **Favorites:** Protect valuable cards from accidental selling

    **Simulation:** Test crate odds with `/osusimulate [crate] [amount]`

    **Trading:** Exchange cards and coins with other players safely"""
        
        embed.add_field(
            name="Advanced Features",
            value=advanced_text,
            inline=False
        )
        
        # Tips & Strategy
        tips_text = """💡 **Pro Tips:**
    • Higher tier crates have better odds for rare players
    • Favorite your best cards to prevent accidental selling
    • Check the store daily - it refreshes with different stock
    • Trade duplicate cards with friends for cards you need
    • Complete daily quests for steady income
    • Mutations significantly increase card value"""
        
        embed.add_field(
            name="Tips & Strategy 💡",
            value=tips_text,
            inline=False
        )
        
        embed.set_footer(text="Need more help? Ask in chat or use specific command help!")
        
        if interaction:
            await interaction.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)


# UI VIEWS FOR CONFIRMATIONS
class WipeConfirmationView(discord.ui.View):
    """Confirmation view for wiping user data"""
    
    def __init__(self, target_id, target_name, handler):
        super().__init__(timeout=60)
        self.target_id = target_id
        self.target_name = target_name
        self.handler = handler
    
    @discord.ui.button(label="CONFIRM WIPE", style=discord.ButtonStyle.danger, emoji="💀")
    async def confirm_wipe(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Double check it's the owner
        if interaction.user.name.lower() != "dinonuwg":
            await interaction.response.send_message("❌ Only the bot owner can use this!", ephemeral=True)
            return
        
        try:
            # Get user data one more time for final stats
            target_data = self.handler.get_user_gacha_data(self.target_id)
            total_cards = len(target_data.get("cards", {}))
            total_currency = target_data.get("currency", 0)
            
            # Completely wipe the user's gacha data
            user_id_str = str(self.target_id)
            if user_id_str in self.handler.bot.osu_gacha_data:
                del self.handler.bot.osu_gacha_data[user_id_str]
            
            # Save data
            self.handler.save_user_data()
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            # Create success embed
            embed = discord.Embed(
                title="💀 USER DATA WIPED",
                description=f"**{self.target_name}**'s gacha data has been completely wiped!",
                color=discord.Color.dark_red()
            )
            
            embed.add_field(
                name="🗑️ Deleted Data",
                value=f"**Cards:** {total_cards:,}\n**Currency:** {total_currency:,} coins\n**All achievements and stats**",
                inline=False
            )
            
            embed.set_footer(text="Data wipe completed successfully")
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Wipe Failed",
                description=f"An error occurred while wiping data: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_wipe(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="✅ Wipe Cancelled",
            description=f"Data wipe for **{self.target_name}** has been cancelled.\nNo data was deleted.",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    async def on_timeout(self):
        """Handle view timeout"""
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="⏰ Confirmation Expired",
            description="Wipe confirmation timed out. No data was deleted.",
            color=discord.Color.orange()
        )
        
        # Try to edit the message if possible
        try:
            await self.message.edit(embed=embed, view=self)
        except:
            pass

class OpenView(discord.ui.View):
    def __init__(self, user_id, handlers, crate_type, amount):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.handlers = handlers
        self.crate_type = crate_type
        self.amount = amount

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Open Crates", style=discord.ButtonStyle.green, emoji="📦")
    async def open_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't use this button!", ephemeral=True)
            return
        
        try:
            # Disable all buttons immediately to prevent double-clicking
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)
            
            # FIX: Pass interaction as the ctx parameter AND as interaction parameter
            if self.amount > 1:
                await self.handlers.handle_enhanced_bulk_opening(interaction, self.crate_type, self.amount, interaction)
            else:
                # For single crate, you might want to use a different method or fix this too
                await self.handlers.handle_open_crate(interaction, self.crate_type, self.amount)
            
            self.stop()
            
        except Exception as e:
            print(f"Error in open button: {e}")
            # Re-enable buttons on error
            for item in self.children:
                item.disabled = False
            await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌") 
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You can't use this button!", ephemeral=True)
            return
        
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="Cancelled",
            description="Crate opening cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

class SimulateView(discord.ui.View):
    def __init__(self, user_id, handlers, crate_type, amount):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.handlers = handlers
        self.crate_type = crate_type
        self.amount = amount

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @discord.ui.button(label="Run Simulation", style=discord.ButtonStyle.success)
    async def confirm_simulate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.handlers.handle_simulate(interaction, self.crate_type, self.amount)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_simulate(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Simulation Cancelled",
            description="Simulation has been cancelled.",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=None)