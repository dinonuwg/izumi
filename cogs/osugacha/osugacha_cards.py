import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime 
import asyncio
import math
from utils.helpers import *
from utils.config import *

# Import all the configuration and system
from .osugacha_config import *
from .osugacha_system import OsuGachaSystem

class CardSelectionView(discord.ui.View):
    """View for selecting between multiple cards of the same player"""
    
    def __init__(self, user_id, cog, player_name, matching_cards, command_type):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.cog = cog
        self.player_name = player_name
        self.matching_cards = matching_cards  # List of (card_id, card_data) tuples
        self.command_type = command_type  # "view" or "favorite"
        
        # Add buttons for each card (max 5 for UI limit)
        for i, (card_id, card_data) in enumerate(matching_cards[:5]):
            player = card_data["player_data"]
            
            # Create button label with distinguishing info
            mutation_text = ""
            if card_data.get("mutation"):
                if card_data["mutation"] in self.cog.gacha_system.mutations:
                    mutation_name = self.cog.gacha_system.mutations[card_data["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"
                else:
                    # Legacy mutations
                    legacy_mutations = {"neon": "SHOCKED", "rainbow": "RAINBOW"}
                    mutation_name = legacy_mutations.get(card_data["mutation"], card_data["mutation"].upper())
                    mutation_text = f" - {mutation_name}"
            
            favorite_mark = " ❤️" if card_data.get("is_favorite", False) else ""
            obtained_date = datetime.fromtimestamp(card_data.get("obtained_at", 0)).strftime("%m/%d")
            
            button_label = f"{'⭐' * card_data['stars']} {player['username']}{mutation_text}{favorite_mark}"
            
            # Truncate if too long
            if len(button_label) > 80:
                button_label = button_label[:77] + "..."
            
            button = discord.ui.Button(
                label=button_label,
                style=discord.ButtonStyle.secondary,
                custom_id=f"card_{i}",
                row=i // 5  # Distribute across rows
            )
            
            button.callback = self.create_card_callback(card_id, card_data)
            self.add_item(button)
        
        # Add info about the cards in a dropdown if there are many
        if len(matching_cards) > 5:
            # Create a dropdown for the remaining cards
            options = []
            for i, (card_id, card_data) in enumerate(matching_cards[5:10], start=5):  # Next 5 cards
                player = card_data["player_data"]
                mutation_text = ""
                if card_data.get("mutation"):
                    if card_data["mutation"] in self.cog.gacha_system.mutations:
                        mutation_name = self.cog.gacha_system.mutations[card_data["mutation"]]["name"]
                        mutation_text = f" - {mutation_name.upper()}"
                    else:
                        legacy_mutations = {"neon": "SHOCKED", "rainbow": "RAINBOW"}
                        mutation_name = legacy_mutations.get(card_data["mutation"], card_data["mutation"].upper())
                        mutation_text = f" - {mutation_name}"
                
                favorite_mark = " ❤️" if card_data.get("is_favorite", False) else ""
                obtained_date = datetime.fromtimestamp(card_data.get("obtained_at", 0)).strftime("%m/%d")
                
                label = f"{'⭐' * card_data['stars']} {player['username']}{mutation_text}{favorite_mark}"
                description = f"#{player['rank']:,} • {card_data['price']:,} coins • {obtained_date}"
                
                if len(label) > 100:
                    label = label[:97] + "..."
                if len(description) > 100:
                    description = description[:97] + "..."
                
                options.append(discord.SelectOption(
                    label=label,
                    description=description,
                    value=f"card_{len(self.matching_cards[:5]) + i - 5}"
                ))
            
            if options:
                dropdown = discord.ui.Select(
                    placeholder=f"More {self.player_name} cards...",
                    options=options,
                    custom_id="card_dropdown"
                )
                dropdown.callback = self.dropdown_callback
                self.add_item(dropdown)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You cannot interact with this.", ephemeral=True)
            return False
        return True
    
    def create_card_callback(self, card_id, card_data):
        async def callback(interaction: discord.Interaction):
            if self.command_type == "view":
                # Show the selected card
                await self.cog._show_single_card(interaction, card_id, card_data)
            elif self.command_type == "favorite":
                # Handle favoriting the selected card
                await self.cog._handle_single_favorite(interaction, card_id, card_data)
            elif self.command_type == "showcase":
                # Handle adding the selected card to showcase
                user_data = self.cog.get_user_gacha_data(interaction.user.id)
                await self.cog._execute_showcase_add(interaction, card_id, card_data, user_data, None)
        return callback
    
    async def dropdown_callback(self, interaction: discord.Interaction):
        # Handle dropdown selection
        selected_value = interaction.data["values"][0]
        card_index = int(selected_value.split("_")[1]) + 5  # Offset for dropdown items
        
        if card_index < len(self.matching_cards):
            card_id, card_data = self.matching_cards[card_index]
            
            if self.command_type == "view":
                await self.cog._show_single_card(interaction, card_id, card_data)
            elif self.command_type == "favorite":
                await self.cog._handle_single_favorite(interaction, card_id, card_data)
            elif self.command_type == "showcase":
                user_data = self.cog.get_user_gacha_data(interaction.user.id)
                await self.cog._execute_showcase_add(interaction, card_id, card_data, user_data, None)

class CardPaginationView(discord.ui.View):
    """Paginated card collection view"""
    
    def __init__(self, user_id, cards, gacha_system, page_size=10, title="Card Collection"):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.cards = cards
        self.gacha_system = gacha_system
        self.page_size = page_size
        self.title = title
        self.current_page = 0
        self.max_pages = max(1, math.ceil(len(cards) / page_size))
        
        # Update button states
        self._update_buttons()
    
    def _update_buttons(self):
        """Update button states based on current page"""
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= self.max_pages - 1
        self.last_page.disabled = self.current_page >= self.max_pages - 1
    
    def _create_embed(self):
        """Create embed for current page"""
        embed = discord.Embed(
            title=f"{self.title} (Page {self.current_page + 1}/{self.max_pages})",
            color=discord.Color.blue()
        )
        
        if not self.cards:
            embed.description = "No cards found."
            return embed
        
        # Calculate page range
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.cards))
        page_cards = self.cards[start_idx:end_idx]
        
        # Add cards to embed
        card_list = []
        for i, (card_id, card) in enumerate(page_cards, start=start_idx + 1):
            player = card["player_data"]
            mutation_text = ""
            if card["mutation"]:
                # ✅ FIX: Handle legacy mutations that no longer exist
                if card["mutation"] in self.gacha_system.mutations:
                    mutation_name = self.gacha_system.mutations[card["mutation"]]["name"]
                else:
                    # Legacy mutation mapping
                    legacy_mutations = {
                        "neon": "SHOCKED",
                        "rainbow": "RAINBOW (Legacy)"
                    }
                    mutation_name = legacy_mutations.get(card["mutation"], card["mutation"].upper())
                
                mutation_text = f" - {mutation_name}"
            
            favorite_mark = " ❤️" if card.get("is_favorite", False) else ""
            
            card_text = f"**{i}.** {'⭐' * card['stars']} {player['username']}{mutation_text}{favorite_mark}"
            card_text += f"\n    #{player['rank']:,} • {player['pp']:,} PP • {card['price']:,} coins"
            card_list.append(card_text)
        
        embed.description = "\n\n".join(card_list)
        
        # Add summary
        total_value = sum(card[1]["price"] for card in self.cards)
        mutation_count = sum(1 for card_id, card in self.cards if card["mutation"])
        favorite_count = sum(1 for card_id, card in self.cards if card.get("is_favorite", False))
        
        embed.add_field(
            name="Collection Summary",
            value=f"**Total Cards:** {len(self.cards)}\n**Total Value:** {total_value:,} coins\n**Mutations:** {mutation_count}\n**Favorites:** {favorite_count}",
            inline=False
        )
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command user can interact"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You cannot interact with this.", ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self._update_buttons()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.max_pages - 1, self.current_page + 1)
        self._update_buttons()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = self.max_pages - 1
        self._update_buttons()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class FavoriteView(discord.ui.View):
    """Favorite/unfavorite confirmation view"""
    
    def __init__(self, user_id, cog, card_id, card_data, is_favoriting):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.cog = cog
        self.card_id = card_id
        self.card_data = card_data
        self.is_favoriting = is_favoriting
        
        # Update button text
        action = "Favorite" if is_favoriting else "Unfavorite"
        self.children[0].label = f"{action} Card"
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command user can interact"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "You cannot interact with this.", ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Favorite Card", style=discord.ButtonStyle.green)
    async def confirm_favorite(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._handle_favorite_action(interaction, self.card_id, self.card_data, self.is_favoriting)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_favorite(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Cancelled",
            description="Action cancelled.",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

class OsuGachaCardsCog(commands.Cog, name="Osu Gacha Cards"):
    """Card management and viewing system"""
    
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
                "favorites": []
            }
            save_json(FILE_PATHS["gacha_data"], self.bot.osu_gacha_data)
        return self.bot.osu_gacha_data[user_id_str]

    def save_user_data(self):
        """Save user data to file"""
        save_json(FILE_PATHS["gacha_data"], self.bot.osu_gacha_data)

    # SLASH COMMANDS
    @app_commands.command(name="osushowcase", description="Manage or view your card showcase")
    @app_commands.describe(
        action="Action to perform",
        player="Player name to add/remove from showcase"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="View Showcase", value="view"),
        app_commands.Choice(name="Add Card", value="add"),
        app_commands.Choice(name="Remove Card", value="remove"),
        app_commands.Choice(name="Clear All", value="clear")
    ])
    async def osu_showcase_slash(self, interaction: discord.Interaction, 
                                action: str = "view", 
                                player: str = None):
        await self._showcase_command(interaction, action, player, interaction)

    @app_commands.command(name="osucards", description="View your card collection")
    @app_commands.describe(
        search="Search for specific player names",
        sort="Sort cards by different criteria",
        rarity="Filter by card rarity",
        mutation="Filter by mutation type",
        favorites="Show only favorite cards"
    )
    @app_commands.choices(sort=[
        app_commands.Choice(name="Rank (Best to Worst)", value="rank_asc"),
        app_commands.Choice(name="Rank (Worst to Best)", value="rank_desc"),
        app_commands.Choice(name="Value (High to Low)", value="value_desc"),
        app_commands.Choice(name="Value (Low to High)", value="value_asc"),
        app_commands.Choice(name="Rarity (High to Low)", value="rarity_desc"),
        app_commands.Choice(name="Recently Obtained", value="recent")
    ])
    async def osu_cards_slash(self, interaction: discord.Interaction, search: str = None, sort: str = "rank_asc", rarity: str = None, mutation: str = None, favorites: bool = False):
        await self._cards_command(interaction, search, sort, rarity, mutation, favorites, interaction)

    @app_commands.command(name="osucard", description="View detailed card information")
    @app_commands.describe(search="Player name to search for")
    async def osu_card_slash(self, interaction: discord.Interaction, search: str):
        await self._card_command(interaction, search, interaction)

    @app_commands.command(name="osufavorite", description="Add or remove cards from favorites")
    @app_commands.describe(search="Player name to search for")
    async def osu_favorite_slash(self, interaction: discord.Interaction, search: str):
        await self._favorite_command(interaction, search, interaction)

    # PREFIX COMMANDS
    @commands.command(name="osucards", aliases=["ocards", "cards"])
    async def osu_cards_prefix(self, ctx: commands.Context, *, args: str = None):
        # Parse arguments
        search = None
        sort = "rank_asc"
        rarity = None
        mutation = None
        favorites = False
        
        if args:
            parts = args.split()
            for part in parts:
                if part.lower() in ["favorites", "favs", "fav"]:
                    favorites = True
                elif part.lower() in ["rank", "value", "rarity", "recent"]:
                    sort = f"{part.lower()}_desc" if part.lower() != "recent" else "recent"
                elif part.lower().startswith("rarity:"):
                    rarity = part.split(":", 1)[1]
                elif part.lower().startswith("mutation:"):
                    mutation = part.split(":", 1)[1]
                else:
                    search = part
        
        await self._cards_command(ctx, search, sort, rarity, mutation, favorites)

    @commands.command(name="osushowcase", aliases=["oshowcase", "showcase"])
    async def osu_showcase_prefix(self, ctx: commands.Context, action: str = "view", *, player: str = None):
        await self._showcase_command(ctx, action, player)

    @commands.command(name="osucard", aliases=["ocard", "card"])
    async def osu_card_prefix(self, ctx: commands.Context, *, search: str = None):
        if not search:
            await ctx.send("Please specify a player name to search for!")
            return
        await self._card_command(ctx, search)

    @commands.command(name="osufavorite", aliases=["ofavorite", "ofav", "favorite", "fav"])
    async def osu_favorite_prefix(self, ctx: commands.Context, *, search: str = None):
        if not search:
            await ctx.send("Please specify a player name to search for!")
            return
        await self._favorite_command(ctx, search)

    # SHARED COMMAND IMPLEMENTATIONS

    async def _showcase_command(self, ctx, action="view", player=None, interaction=None):
        """Manage and display user's card showcase"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        username = ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name
        
        # Initialize showcase if not exists
        if "showcase_cards" not in user_data:
            user_data["showcase_cards"] = []
        
        cards = user_data.get("cards", {})
        
        if action == "view":
            await self._show_showcase(ctx, user_data, username, interaction)
            
        elif action == "add":
            if not player:
                embed = discord.Embed(
                    title="Missing Player Name",
                    description="Please specify a player name to add to your showcase!\n\n**Usage:** `/osushowcase add mrekk`",
                    color=discord.Color.orange()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
            
            if len(user_data["showcase_cards"]) >= 3:
                embed = discord.Embed(
                    title="Showcase Full",
                    description="You can only showcase up to 3 cards!\n\nUse `/osushowcase remove [player]` to make space.",
                    color=discord.Color.red()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
            
            await self._add_to_showcase(ctx, player, user_data, interaction)
            
        elif action == "remove":
            if not player:
                embed = discord.Embed(
                    title="Missing Player Name", 
                    description="Please specify a player name to remove from your showcase!\n\n**Usage:** `/osushowcase remove mrekk`",
                    color=discord.Color.orange()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
            
            await self._remove_from_showcase(ctx, player, user_data, interaction)
            
        elif action == "clear":
            if not user_data["showcase_cards"]:
                embed = discord.Embed(
                    title="Nothing to Clear",
                    description="Your showcase is already empty!",
                    color=discord.Color.orange()
                )
                if interaction:
                    await interaction.response.send_message(embed=embed)
                else:
                    await ctx.send(embed=embed)
                return
            
            user_data["showcase_cards"] = []
            self.save_user_data()
            
            embed = discord.Embed(
                title="Showcase Cleared",
                description="All cards have been removed from your showcase.",
                color=discord.Color.green()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)

    async def _show_showcase(self, ctx, user_data, username, interaction=None):
        """Display the user's showcase"""
        showcase_card_ids = user_data.get("showcase_cards", [])
        
        if not showcase_card_ids:
            embed = discord.Embed(
                title=f"{username}'s Card Showcase",
                description="Your showcase is empty!\n\n💡 Use `/osushowcase add [player]` to add cards to your showcase.",
                color=discord.Color.blue()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Get actual card data for showcase cards
        cards = user_data.get("cards", {})
        showcase_cards = []
        
        for card_id in showcase_card_ids:
            if card_id in cards:
                showcase_cards.append((card_id, cards[card_id]))
            else:
                # Remove invalid card ID
                user_data["showcase_cards"].remove(card_id)
        
        if not showcase_cards:
            user_data["showcase_cards"] = []
            self.save_user_data()
            
            embed = discord.Embed(
                title=f"{username}'s Card Showcase",
                description="Your showcase cards were not found (possibly sold).\n\n💡 Use `/osushowcase add [player]` to rebuild your showcase.",
                color=discord.Color.orange()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Defer response for image generation
        if interaction:
            await interaction.response.defer()
        else:
            message = await ctx.send("🎨 Generating showcase...")

        try:
            # Generate individual card images
            card_images = []
            embed_descriptions = []
            
            for i, (card_id, card_data) in enumerate(showcase_cards):
                player = card_data["player_data"]
                
                # Handle flashback year for image generation
                flashback_year = None
                if card_data.get("mutation") == "flashback":
                    flashback_year = card_data.get("flashback_year")
                
                # Generate card image
                card_image = await self.gacha_system.create_card_image(
                    player,
                    card_data["stars"],
                    card_data.get("mutation"),
                    card_data["price"],
                    flashback_year=flashback_year
                )
                
                if card_image:
                    card_images.append(card_image)
                    
                    # Create description for this card
                    stars = "⭐" * card_data["stars"]
                    mutation_text = ""
                    
                    if card_data.get("mutation"):
                        if card_data["mutation"] in self.gacha_system.mutations:
                            mutation_info = self.gacha_system.mutations[card_data["mutation"]]
                            mutation_text = f" **{mutation_info['name'].upper()}** {mutation_info.get('emoji', '')}"
                        else:
                            # Legacy mutations
                            legacy_mutations = {
                                "rainbow": ("RAINBOW", "🌈"),
                                "neon": ("SHOCKED", "⚡")
                            }
                            name, emoji = legacy_mutations.get(card_data["mutation"], (card_data["mutation"].upper(), ""))
                            mutation_text = f" **{name}** {emoji}"
                    
                    favorite_emoji = "💖" if card_data.get("is_favorite", False) else ""
                    
                    card_desc = f"**{stars} {player['username']}**{mutation_text} {favorite_emoji}\n"
                    card_desc += f"#{player['rank']:,} • {player['pp']:,} PP • {card_data['price']:,} coins"
                    
                    embed_descriptions.append(card_desc)

            # Create collage image from individual card images
            collage_image = await self._create_showcase_collage(card_images)
            
            if collage_image:
                # Create showcase embed with collage
                embed = discord.Embed(
                    title=f"🏆 {username}'s Card Showcase",
                    description=f"Showing {len(showcase_cards)} showcase card{'s' if len(showcase_cards) > 1 else ''}:",
                    color=discord.Color.gold()
                )
                
                # Add each card as a field
                for i, desc in enumerate(embed_descriptions):
                    embed.add_field(
                        name=f"Card {i+1}",
                        value=desc,
                        inline=True
                    )
                
                # Add total value and management info
                total_value = sum(card[1]["price"] for card in showcase_cards)
                embed.add_field(
                    name="💰 Total Showcase Value",
                    value=f"{total_value:,} coins",
                    inline=False
                )
                
                embed.add_field(
                    name="🛠️ Manage Showcase",
                    value=f"• `/osushowcase add [player]` - Add card ({3 - len(showcase_cards)} slots left)\n"
                        f"• `/osushowcase remove [player]` - Remove card\n"
                        f"• `/osushowcase clear` - Clear all cards",
                    inline=False
                )
                
                embed.set_footer(text="💡 Your showcase is displayed whenever someone uses this command!")
                
                # Set the collage as the main embed image
                embed.set_image(url="attachment://showcase_collage.png")
                
                # Send the showcase with single collage image
                showcase_file = discord.File(collage_image, filename="showcase_collage.png")
                
                if interaction:
                    await interaction.edit_original_response(embed=embed, attachments=[showcase_file])
                else:
                    await message.edit(embed=embed, attachments=[showcase_file])
            else:
                raise Exception("Failed to create showcase collage")
                
        except Exception as e:
            print(f"Error in showcase display: {e}")
            error_embed = discord.Embed(
                title="❌ Showcase Display Failed",
                description="Failed to generate showcase images. Please try again.",
                color=discord.Color.red()
            )
            
            if interaction:
                await interaction.edit_original_response(embed=error_embed)
            else:
                await message.edit(embed=error_embed)

    async def _create_showcase_collage(self, card_images):
        """Create a collage image from multiple card images"""
        try:
            from PIL import Image
            import io
            
            if not card_images:
                return None
            
            # Convert BytesIO objects to PIL Images
            pil_images = []
            for img_bytes in card_images:
                img_bytes.seek(0)
                pil_img = Image.open(img_bytes).convert('RGBA')
                pil_images.append(pil_img)
            
            # Calculate collage dimensions
            if len(pil_images) == 1:
                # Single card - use as is
                collage = pil_images[0]
            elif len(pil_images) == 2:
                # Two cards - side by side
                card_width, card_height = pil_images[0].size
                collage_width = card_width * 2 + 20  # 20px gap
                collage_height = card_height + 20     # 10px padding top/bottom
                
                collage = Image.new('RGBA', (collage_width, collage_height), (0, 0, 0, 0))
                collage.paste(pil_images[0], (10, 10))
                collage.paste(pil_images[1], (card_width + 20, 10))
            else:
                # Three cards - triangle layout (1 top, 2 bottom)
                card_width, card_height = pil_images[0].size
                collage_width = card_width * 2 + 30   # 2 cards wide + gaps
                collage_height = card_height * 2 + 30 # 2 cards tall + gaps
                
                collage = Image.new('RGBA', (collage_width, collage_height), (0, 0, 0, 0))
                
                # Top card (centered)
                top_x = (collage_width - card_width) // 2
                collage.paste(pil_images[0], (top_x, 10))
                
                # Bottom left card
                collage.paste(pil_images[1], (10, card_height + 20))
                
                # Bottom right card
                collage.paste(pil_images[2], (card_width + 20, card_height + 20))
            
            # Convert back to BytesIO
            output = io.BytesIO()
            collage.save(output, format='PNG', optimize=True)
            output.seek(0)
            
            return output
            
        except Exception as e:
            print(f"Error creating showcase collage: {e}")
            return None
    
    async def _add_to_showcase(self, ctx, player_name, user_data, interaction=None):
        """Add a card to user's showcase"""
        cards = user_data.get("cards", {})
        if not cards:
            embed = discord.Embed(
                title="No Cards",
                description="You don't have any cards to showcase yet!\n\n💡 Use `/osuopen` to get some cards first.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Find matching cards for this player
        matching_cards = []
        for card_id, card_data in cards.items():
            player = card_data["player_data"]
            if player_name.lower() in player["username"].lower():
                matching_cards.append((card_id, card_data))
        
        if not matching_cards:
            embed = discord.Embed(
                title="Card Not Found",
                description=f"No cards found for **{player_name}**.\n\nMake sure you own a card of this player first!",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # NEW: Filter out cards that are already in showcase
        showcase_card_ids = user_data.get("showcase_cards", [])
        available_cards = []
        
        for card_id, card_data in matching_cards:
            if card_id not in showcase_card_ids:  # Only check specific card ID, not player
                available_cards.append((card_id, card_data))
        
        if not available_cards:
            embed = discord.Embed(
                title="All Cards Already Showcased",
                description=f"All your **{player_name}** cards are already in your showcase!\n\n💡 You can have multiple cards of the same player, but each specific card can only be showcased once.",
                color=discord.Color.orange()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # NEW: If only one available card, add it directly
        if len(available_cards) == 1:
            card_id, card_data = available_cards[0]
            await self._execute_showcase_add(ctx, card_id, card_data, user_data, interaction)
            return
        
        # NEW: Multiple available cards - show selection interface
        embed = discord.Embed(
            title=f"Multiple {player_name.title()} Cards Available",
            description=f"You have **{len(available_cards)}** available cards for **{player_name}**. Choose which one to showcase:",
            color=discord.Color.blue()
        )
        
        # Add preview of available cards
        card_preview = []
        for i, (card_id, card) in enumerate(available_cards[:10], 1):
            player = card["player_data"]
            mutation_text = ""
            if card.get("mutation"):
                if card["mutation"] in self.gacha_system.mutations:
                    mutation_name = self.gacha_system.mutations[card["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"
                else:
                    legacy_mutations = {"neon": "SHOCKED", "rainbow": "RAINBOW"}
                    mutation_name = legacy_mutations.get(card["mutation"], card["mutation"].upper())
                    mutation_text = f" - {mutation_name}"
            
            favorite_mark = " ❤️" if card.get("is_favorite", False) else ""
            obtained_date = datetime.fromtimestamp(card.get("obtained_at", 0)).strftime("%m/%d/%y")
            
            card_text = f"**{i}.** {'⭐' * card['stars']} {player['username']}{mutation_text}{favorite_mark}"
            card_text += f"\n    #{player['rank']:,} • {card['price']:,} coins • Obtained: {obtained_date}"
            card_preview.append(card_text)
        
        if len(available_cards) > 10:
            card_preview.append(f"... and {len(available_cards) - 10} more")
        
        embed.add_field(
            name="Available Cards",
            value="\n\n".join(card_preview),
            inline=False
        )
        
        embed.set_footer(text="Use the buttons below to select which card to showcase")
        
        # Use CardSelectionView with "showcase" command type
        view = CardSelectionView(
            user_id=ctx.author.id if hasattr(ctx, 'author') else ctx.user.id,
            cog=self,
            player_name=player_name,
            matching_cards=available_cards,  # Pass only available cards
            command_type="showcase"
        )
        
        if interaction:
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def _execute_showcase_add(self, ctx, card_id, card_data, user_data, interaction=None):
        """Execute adding a card to showcase"""
        # Add to showcase
        user_data["showcase_cards"].append(card_id)
        self.save_user_data()
        
        # Create success embed
        player = card_data["player_data"]
        stars = "⭐" * card_data["stars"]
        
        mutation_text = ""
        if card_data.get("mutation"):
            if card_data["mutation"] in self.gacha_system.mutations:
                mutation_info = self.gacha_system.mutations[card_data["mutation"]]
                mutation_text = f" **{mutation_info['name'].upper()}** {mutation_info.get('emoji', '')}"
            else:
                legacy_mutations = {
                    "rainbow": ("RAINBOW", "🌈"),
                    "neon": ("SHOCKED", "⚡")
                }
                name, emoji = legacy_mutations.get(card_data["mutation"], (card_data["mutation"].upper(), ""))
                mutation_text = f" **{name}** {emoji}"
        
        embed = discord.Embed(
            title="✅ Card Added to Showcase!",
            description=f"Added **{stars} {player['username']}**{mutation_text} to your showcase!\n\n"
                    f"**Showcase slots:** {len(user_data['showcase_cards'])}/3",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Card Details",
            value=f"#{player['rank']:,} • {player['pp']:,} PP • {card_data['price']:,} coins",
            inline=False
        )
        
        embed.set_footer(text="💡 Use /osushowcase to view your complete showcase!")
        
        if hasattr(ctx, 'response') and not ctx.response.is_done():
            await ctx.response.send_message(embed=embed)
        elif hasattr(ctx, 'edit_original_response'):
            await ctx.edit_original_response(embed=embed, view=None)
        elif interaction:
            await interaction.edit_original_response(embed=embed, view=None)
        else:
            await ctx.send(embed=embed)

    async def _remove_from_showcase(self, ctx, player_name, user_data, interaction=None):
        """Remove a card from user's showcase"""
        showcase_card_ids = user_data.get("showcase_cards", [])
        
        if not showcase_card_ids:
            embed = discord.Embed(
                title="Empty Showcase",
                description="Your showcase is empty! Nothing to remove.",
                color=discord.Color.orange()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        cards = user_data.get("cards", {})
        card_to_remove = None
        
        # Find the card in showcase that matches the player name
        for card_id in showcase_card_ids:
            if card_id in cards:
                card_data = cards[card_id]
                player = card_data["player_data"]
                if player_name.lower() in player["username"].lower():
                    card_to_remove = (card_id, card_data)
                    break
        
        if not card_to_remove:
            embed = discord.Embed(
                title="Card Not in Showcase",
                description=f"**{player_name}** is not in your showcase.",
                color=discord.Color.red()
            )
            
            # Show current showcase
            if showcase_card_ids:
                current_players = []
                for card_id in showcase_card_ids:
                    if card_id in cards:
                        current_players.append(cards[card_id]["player_data"]["username"])
                
                if current_players:
                    embed.add_field(
                        name="Current Showcase",
                        value="\n".join(f"• {player}" for player in current_players),
                        inline=False
                    )
            
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Remove from showcase
        card_id, card_data = card_to_remove
        user_data["showcase_cards"].remove(card_id)
        self.save_user_data()
        
        # Create success embed
        player = card_data["player_data"]
        embed = discord.Embed(
            title="✅ Card Removed from Showcase!",
            description=f"Removed **{player['username']}** from your showcase.\n\n"
                       f"**Showcase slots:** {len(user_data['showcase_cards'])}/3",
            color=discord.Color.green()
        )
        
        if interaction:
            await interaction.response.send_message(embed=embed)
        else:
            await ctx.send(embed=embed)
            
    async def _cards_command(self, ctx, search, sort, rarity, mutation, favorites, interaction=None):
        """Cards collection viewing command"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        username = ctx.author.display_name if hasattr(ctx, 'author') else ctx.user.display_name
        
        cards = user_data.get("cards", {})
        if not cards:
            embed = discord.Embed(
                title="No Cards",
                description="You don't have any cards yet! Use `/osuopen` to get some crates.",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Filter cards
        filtered_cards = []
        for card_id, card in cards.items():
            # Search filter
            if search and search.lower() not in card["player_data"]["username"].lower():
                continue
            
            # Rarity filter
            if rarity and rarity.lower() != card["rarity_name"].lower():
                continue
            
            # Mutation filter
            if mutation:
                card_mutation = card.get("mutation", "")
                if mutation.lower() != card_mutation.lower():
                    continue
            
            # Favorites filter
            if favorites and not card.get("is_favorite", False):
                continue
            
            filtered_cards.append((card_id, card))
        
        if not filtered_cards:
            embed = discord.Embed(
                title="No Cards Found",
                description="No cards match your search criteria.",
                color=discord.Color.orange()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Sort cards
        if sort == "rank_asc":
            filtered_cards.sort(key=lambda x: x[1]["player_data"]["rank"])
        elif sort == "rank_desc":
            filtered_cards.sort(key=lambda x: x[1]["player_data"]["rank"], reverse=True)
        elif sort == "value_desc":
            filtered_cards.sort(key=lambda x: x[1]["price"], reverse=True)
        elif sort == "value_asc":
            filtered_cards.sort(key=lambda x: x[1]["price"])
        elif sort == "rarity_desc":
            filtered_cards.sort(key=lambda x: x[1]["stars"], reverse=True)
        elif sort == "recent":
            # Keep original order (newest first)
            pass
        
        # Create pagination view
        title_parts = [f"{username}'s Cards"]
        if search:
            title_parts.append(f"(Search: {search})")
        if favorites:
            title_parts.append("(Favorites)")
        
        title = " ".join(title_parts)
        view = CardPaginationView(user_id, filtered_cards, self.gacha_system, title=title)
        embed = view._create_embed()
        
        if interaction:
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def _card_command(self, ctx, search, interaction=None):
        """Individual card display command"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)
        
        cards = user_data.get("cards", {})
        if not cards:
            embed = discord.Embed(
                title="No Cards",
                description="You don't have any cards yet!",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Find matching cards
        matching_cards = []
        for card_id, card in cards.items():
            if search.lower() in card["player_data"]["username"].lower():
                matching_cards.append((card_id, card))
        
        if not matching_cards:
            embed = discord.Embed(
                title="Card Not Found",
                description=f"No cards found for: `{search}`",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # If only one card, show it directly
        if len(matching_cards) == 1:
            card_id, card = matching_cards[0]
            await self._show_single_card(ctx if not interaction else interaction, card_id, card, interaction)
            return
        
        # Multiple cards found - show selection interface
        embed = discord.Embed(
            title=f"Multiple {search.title()} Cards Found",
            description=f"You have **{len(matching_cards)}** cards for **{search}**. Choose which one to view:",
            color=discord.Color.blue()
        )
        
        # Add preview of the cards
        card_preview = []
        for i, (card_id, card) in enumerate(matching_cards[:10], 1):
            player = card["player_data"]
            mutation_text = ""
            if card.get("mutation"):
                if card["mutation"] in self.gacha_system.mutations:
                    mutation_name = self.gacha_system.mutations[card["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"
                else:
                    legacy_mutations = {"neon": "SHOCKED", "rainbow": "RAINBOW"}
                    mutation_name = legacy_mutations.get(card["mutation"], card["mutation"].upper())
                    mutation_text = f" - {mutation_name}"
            
            favorite_mark = " ❤️" if card.get("is_favorite", False) else ""
            obtained_date = datetime.fromtimestamp(card.get("obtained_at", 0)).strftime("%m/%d/%y")
            
            card_text = f"**{i}.** {'⭐' * card['stars']} {player['username']}{mutation_text}{favorite_mark}"
            card_text += f"\n    #{player['rank']:,} • {card['price']:,} coins • Obtained: {obtained_date}"
            card_preview.append(card_text)
        
        if len(matching_cards) > 10:
            card_preview.append(f"... and {len(matching_cards) - 10} more")
        
        embed.add_field(
            name="Your Cards",
            value="\n\n".join(card_preview),
            inline=False
        )
        
        embed.set_footer(text="Use the buttons below to select which card to view")
        
        view = CardSelectionView(user_id, self, search, matching_cards, "view")
        
        if interaction:
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def _show_single_card(self, ctx_or_interaction, card_id, card_data, original_interaction=None):
        """Show a single card's details"""
        try:
            # Generate card image
            if hasattr(ctx_or_interaction, 'response'):
                await ctx_or_interaction.response.defer()
            
            # Handle flashback year for card image generation
            flashback_year = None
            if card_data.get("mutation") == "flashback":
                # Extract flashback year from card data
                flashback_year = card_data.get("flashback_year")
            
            card_image = await self.gacha_system.create_card_image(
                card_data["player_data"], 
                card_data["stars"], 
                card_data.get("mutation"), 
                card_data["price"],
                flashback_year=flashback_year  # Add this parameter
            )
            
            # Create detailed embed
            player = card_data["player_data"]
            
            stars_display = "★" * card_data["stars"]
            mutation_text = ""
            if card_data.get("mutation"):
                # Handle legacy mutations
                if card_data["mutation"] in self.gacha_system.mutations:
                    mutation_name = self.gacha_system.mutations[card_data["mutation"]]["name"]
                    mutation_emoji = self.gacha_system.mutations[card_data["mutation"]]["emoji"]
                else:
                    # Legacy mutation mapping
                    legacy_mutations = {
                        "neon": ("SHOCKED", "⚡"),
                        "rainbow": ("RAINBOW (Legacy)", "🌈")
                    }
                    mutation_name, mutation_emoji = legacy_mutations.get(card_data["mutation"], (card_data["mutation"].upper(), "❓"))
                
                mutation_text = f" - {mutation_name} {mutation_emoji}"
            
            # For flashback cards, use flashback year as rarity display if available
            rarity_display = card_data['rarity_name']
            if card_data.get("mutation") == "flashback" and flashback_year:
                rarity_display = flashback_year
            
            embed = discord.Embed(
                title=f"{player['username']}{mutation_text}",
                description=f"**{rarity_display}\n{stars_display}**",
                color=discord.Color.blue()
            )
            
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
            
            embed.add_field(
                name="Card Value",
                value=f"**{card_data['price']:,}** coins",
                inline=True
            )
            
            # Add mutation description if present
            if card_data.get("mutation") and card_data["mutation"] in self.gacha_system.mutations:
                mutation_info = self.gacha_system.mutations[card_data["mutation"]]
                embed.add_field(
                    name="",
                    value=f"{mutation_info['description']}\n",
                    inline=False
                )
            
            # Add obtained date
            obtained_date = datetime.fromtimestamp(card_data.get("obtained_at", 0)).strftime("%B %d, %Y")
            embed.add_field(
                name="Obtained",
                value=obtained_date,
                inline=True
            )
            
            favorite_status = "❤️ Favorited" if card_data.get("is_favorite", False) else ""
            if favorite_status:
                embed.set_footer(text=favorite_status)
            
            # Send with image
            if card_image:
                file = discord.File(card_image, filename="card.png")
                embed.set_image(url="attachment://card.png")
                
                if hasattr(ctx_or_interaction, 'edit_original_response'):
                    await ctx_or_interaction.edit_original_response(embed=embed, attachments=[file], view=None)
                elif original_interaction:
                    await original_interaction.edit_original_response(embed=embed, attachments=[file])
                else:
                    await ctx_or_interaction.send(embed=embed, file=file)
            else:
                if hasattr(ctx_or_interaction, 'edit_original_response'):
                    await ctx_or_interaction.edit_original_response(embed=embed, view=None)
                elif original_interaction:
                    await original_interaction.edit_original_response(embed=embed)
                else:
                    await ctx_or_interaction.send(embed=embed)
                    
        except Exception as e:
            print(f"Error generating card image: {e}")
            # Fallback to text-only display
            embed = discord.Embed(
                title="Card Details",
                description="Unable to generate card image.",
                color=discord.Color.red()
            )
            
            if hasattr(ctx_or_interaction, 'edit_original_response'):
                await ctx_or_interaction.edit_original_response(embed=embed, view=None)
            elif original_interaction:
                await original_interaction.edit_original_response(embed=embed)
            else:
                await ctx_or_interaction.send(embed=embed)

    async def _favorite_command(self, ctx, search, interaction=None):
        """Favorite/unfavorite cards command"""
        user_id = ctx.author.id if hasattr(ctx, 'author') else ctx.user.id
        user_data = self.get_user_gacha_data(user_id)

        # Check if confirmations are enabled
        confirmations_enabled = user_data.get("confirmations_enabled", True)
        
        cards = user_data.get("cards", {})
        if not cards:
            embed = discord.Embed(
                title="No Cards",
                description="You don't have any cards yet!",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # Find matching cards
        matching_cards = []
        for card_id, card in cards.items():
            if search.lower() in card["player_data"]["username"].lower():
                matching_cards.append((card_id, card))
        
        if not matching_cards:
            embed = discord.Embed(
                title="Card Not Found",
                description=f"No cards found for: `{search}`",
                color=discord.Color.red()
            )
            if interaction:
                await interaction.response.send_message(embed=embed)
            else:
                await ctx.send(embed=embed)
            return
        
        # If only one card, handle it directly
        if len(matching_cards) == 1:
            card_id, card = matching_cards[0]
            await self._handle_single_favorite(ctx if not interaction else interaction, card_id, card, interaction)
            return
        
        # Multiple cards found - show selection interface
        embed = discord.Embed(
            title=f"Multiple {search.title()} Cards Found",
            description=f"You have **{len(matching_cards)}** cards for **{search}**. Choose which one to favorite/unfavorite:",
            color=discord.Color.blue()
        )
        
        # Add preview of the cards with favorite status
        card_preview = []
        for i, (card_id, card) in enumerate(matching_cards[:10], 1):
            player = card["player_data"]
            mutation_text = ""
            if card.get("mutation"):
                if card["mutation"] in self.gacha_system.mutations:
                    mutation_name = self.gacha_system.mutations[card["mutation"]]["name"]
                    mutation_text = f" - {mutation_name.upper()}"
                else:
                    legacy_mutations = {"neon": "SHOCKED", "rainbow": "RAINBOW"}
                    mutation_name = legacy_mutations.get(card["mutation"], card["mutation"].upper())
                    mutation_text = f" - {mutation_name}"
            
            is_favorited = card.get("is_favorite", False)
            favorite_mark = " ❤️" if is_favorited else ""
            status = "Favorited" if is_favorited else "Not Favorited"
            obtained_date = datetime.fromtimestamp(card.get("obtained_at", 0)).strftime("%m/%d/%y")
            
            card_text = f"**{i}.** {'⭐' * card['stars']} {player['username']}{mutation_text}{favorite_mark}"
            card_text += f"\n    #{player['rank']:,} • {card['price']:,} coins • {status} • {obtained_date}"
            card_preview.append(card_text)
        
        if len(matching_cards) > 10:
            card_preview.append(f"... and {len(matching_cards) - 10} more")
        
        embed.add_field(
            name="Your Cards",
            value="\n\n".join(card_preview),
            inline=False
        )
        
        embed.set_footer(text="Use the buttons below to select which card to favorite/unfavorite")
        
        view = CardSelectionView(user_id, self, search, matching_cards, "favorite")
        
        if interaction:
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    async def _handle_single_favorite(self, ctx_or_interaction, card_id, card_data, original_interaction=None):
        """Handle favoriting/unfavoriting a single specific card"""
        user_id = ctx_or_interaction.user.id if hasattr(ctx_or_interaction, 'user') else ctx_or_interaction.author.id
        user_data = self.get_user_gacha_data(user_id)
        confirmations_enabled = user_data.get("confirmations_enabled", True)
        
        player = card_data["player_data"]
        is_favorited = card_data.get("is_favorite", False)
        is_favoriting = not is_favorited

        if confirmations_enabled:
            # Create confirmation embed
            action = "favorite" if is_favoriting else "unfavorite"
            mutation_text = ""
            if card_data.get("mutation"):
                # Handle legacy mutations
                if card_data["mutation"] in self.gacha_system.mutations:
                    mutation_name = self.gacha_system.mutations[card_data["mutation"]]["name"]
                else:
                    legacy_mutations = {"neon": "SHOCKED"}
                    mutation_name = legacy_mutations.get(card_data["mutation"], card_data["mutation"].upper())
                
                mutation_text = f" - {mutation_name}"
            
            embed = discord.Embed(
                title=f"Confirm {action.title()}",
                description=f"{action.title()} this card?\n\n**{'⭐' * card_data['stars']} {player['username']}{mutation_text}**\n#{player['rank']:,} • {player['pp']:,} PP • {card_data['price']:,} coins",
                color=discord.Color.green() if is_favoriting else discord.Color.orange()
            )
            
            # Add obtained date for identification
            obtained_date = datetime.fromtimestamp(card_data.get("obtained_at", 0)).strftime("%B %d, %Y")
            embed.add_field(
                name="Card Details",
                value=f"**Obtained:** {obtained_date}\n**Current Status:** {'Favorited' if is_favorited else 'Not Favorited'}",
                inline=False
            )
            
            view = FavoriteView(user_id, self, card_id, card_data, is_favoriting)
            
            if hasattr(ctx_or_interaction, 'response'):
                await ctx_or_interaction.response.edit_message(embed=embed, view=view)
            elif original_interaction:
                await original_interaction.edit_original_response(embed=embed, view=view)
            else:
                await ctx_or_interaction.send(embed=embed, view=view)
        else:
            # Execute action directly
            await self._execute_favorite_action(ctx_or_interaction, card_id, card_data, is_favoriting, original_interaction)

    async def _handle_favorite_action(self, interaction, card_id, card_data, is_favoriting):
        """Handle the actual favorite action"""
        user_data = self.get_user_gacha_data(interaction.user.id)
        
        # Update card
        user_data["cards"][card_id]["is_favorite"] = is_favoriting
        
        # Save data
        self.save_user_data()
        
        # Create result embed
        player = card_data["player_data"]
        action = "favorited" if is_favoriting else "unfavorited"
        
        embed = discord.Embed(
            title=f"Card {action.title()}!",
            description=f"Successfully {action} **{player['username']}**",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

    async def _execute_favorite_action(self, ctx, card_id, card_data, is_favoriting, interaction=None):
        """Execute the favorite action directly"""
        if hasattr(ctx, 'user'):
            user_id = ctx.user.id
        else:
            user_id = ctx.author.id
        
        user_data = self.get_user_gacha_data(user_id)
        
        # Update card
        user_data["cards"][card_id]["is_favorite"] = is_favoriting
        
        # Save data
        self.save_user_data()
        
        # Create result embed
        player = card_data["player_data"]
        action = "favorited" if is_favoriting else "unfavorited"
        
        embed = discord.Embed(
            title=f"Card {action.title()}!",
            description=f"Successfully {action} **{player['username']}**",
            color=discord.Color.green()
        )
        
        # FIX: Handle different response types properly
        if hasattr(ctx, 'response') and not ctx.response.is_done():
            # It's an interaction that hasn't been responded to yet
            await ctx.response.send_message(embed=embed)
        elif hasattr(ctx, 'edit_original_response'):
            # It's an interaction that has already been responded to
            await ctx.edit_original_response(embed=embed, view=None)
        elif interaction:
            # We have an original interaction to edit
            await interaction.edit_original_response(embed=embed, view=None)
        elif hasattr(ctx, 'send'):
            # It's a regular context
            await ctx.send(embed=embed)
        else:
            # Fallback - try followup
            try:
                await ctx.followup.send(embed=embed)
            except:
                print(f"Could not send favorite response for user {user_id}")

async def setup(bot):
    await bot.add_cog(OsuGachaCardsCog(bot))