import discord
import json
import os
import math
from datetime import datetime, timezone
from utils.config import *

def load_json(file_path):
    """Loads JSON data from a file."""
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading or decoding JSON from {file_path}: {e}. Returning empty data.")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred while loading {file_path}: {e}")
        return {}

def save_json(filename, data):
    """Save data to JSON file with error handling"""
    try:
        # Create a clean copy of the data to avoid circular references
        clean_data = deep_clean_data(data)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"An unexpected error occurred while saving {filename}: {e}")

def deep_clean_data(obj, seen=None):
    """Remove circular references and temporary fields from data"""
    if seen is None:
        seen = set()
    
    # Handle different types
    if isinstance(obj, dict):
        # Skip if we've seen this object before (circular reference)
        obj_id = id(obj)
        if obj_id in seen:
            return {}
        seen.add(obj_id)
        
        cleaned = {}
        for key, value in obj.items():
            # Skip temporary display fields
            if key in ['display_count', 'all_cards', 'total_group_value', 'latest_obtained']:
                continue
            cleaned[key] = deep_clean_data(value, seen)
        
        seen.remove(obj_id)
        return cleaned
    
    elif isinstance(obj, list):
        return [deep_clean_data(item, seen) for item in obj]
    
    else:
        # For primitive types, return as-is
        return obj

def get_ordinal(num):
    """Get ordinal suffix for a number (1st, 2nd, 3rd, etc.)"""
    if 11 <= num % 100 <= 13:
        return f"{num}th"
    return f"{num}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(num % 10, 'th') }"

def format_discord_timestamp(unix_time, style="f"):
    """Creates a Discord timestamp string."""
    return f"<t:{int(unix_time)}:{style}>"

def parse_number_shorthand(input_str):
    """
    Parse number shorthand like 10k, 5m, 1.5b into actual numbers
    Returns the parsed number or None if invalid
    
    Examples:
    - "1000" -> 1000
    - "10k" -> 10000
    - "1.5k" -> 1500
    - "5m" -> 5000000
    - "2.3b" -> 2300000000
    """
    if not input_str:
        return None
    
    # Convert to string and clean up
    input_str = str(input_str).lower().strip()
    
    # If it's already a plain number, return it
    try:
        return int(float(input_str))
    except ValueError:
        pass
    
    # Define multipliers
    multipliers = {
        'k': 1_000,
        'm': 1_000_000,
        'b': 1_000_000_000,
        't': 1_000_000_000_000
    }
    
    # Check if it ends with a valid suffix
    if input_str[-1] in multipliers:
        suffix = input_str[-1]
        number_part = input_str[:-1]
        
        try:
            base_number = float(number_part)
            result = int(base_number * multipliers[suffix])
            return result
        except ValueError:
            return None
    
    return None

def format_number_short(number):
    """
    Format a number with shorthand notation for display
    
    Examples:
    - 1000 -> "1K"
    - 1500 -> "1.5K" 
    - 1000000 -> "1M"
    - 2300000000 -> "2.3B"
    """
    if number < 1000:
        return str(number)
    
    units = [
        (1_000_000_000_000, 'T'),
        (1_000_000_000, 'B'),
        (1_000_000, 'M'),
        (1_000, 'K')
    ]
    
    for threshold, unit in units:
        if number >= threshold:
            result = number / threshold
            if result == int(result):
                return f"{int(result)}{unit}"
            else:
                return f"{result:.1f}{unit}"
    
    return str(number)

def get_next_birthday_datetime(month, day, birth_year=None):
    now = datetime.now(timezone.utc)
    try:
        bday_this_year = datetime(now.year, month, day, tzinfo=timezone.utc)
    except ValueError:
        if month == 2 and day == 29:
            bday_this_year = datetime(now.year, 3, 1, tzinfo=timezone.utc)
        else:
            raise
    if bday_this_year < now:
        try:
            bday_next_year = datetime(now.year + 1, month, day, tzinfo=timezone.utc)
        except ValueError:
            if month == 2 and day == 29:
                bday_next_year = datetime(now.year + 1, 3, 1, tzinfo=timezone.utc)
            else:
                raise
        return bday_next_year
    return bday_this_year

def is_birthday_today_extended(month, day, birth_year=None):
    """Check if it's someone's birthday considering a 24-hour period from the birthday."""
    now = datetime.now(timezone.utc)
    try:
        bday_this_year = datetime(now.year, month, day, tzinfo=timezone.utc)
    except ValueError:
        if month == 2 and day == 29:
            bday_this_year = datetime(now.year, 3, 1, tzinfo=timezone.utc)
        else:
            raise
    
    # Check if we're within 24 hours after the birthday has started
    time_since_birthday = now - bday_this_year
    if 0 <= time_since_birthday.total_seconds() < 86400:  # 24 hours = 86400 seconds
        return True
    
    # Also check last year's birthday in case we're in early January and birthday was late December
    try:
        bday_last_year = datetime(now.year - 1, month, day, tzinfo=timezone.utc)
    except ValueError:
        if month == 2 and day == 29:
            bday_last_year = datetime(now.year - 1, 3, 1, tzinfo=timezone.utc)
        else:
            raise
    
    time_since_last_year_birthday = now - bday_last_year
    if 0 <= time_since_last_year_birthday.total_seconds() < 86400:
        return True
    
    return False

def get_guild_xp_data(xp_data_dict, guild_id):
    guild_id_str = str(guild_id)
    if guild_id_str not in xp_data_dict:
        xp_data_dict[guild_id_str] = {}
    return xp_data_dict[guild_id_str]

def get_user_xp_entry(guild_xp_data, user_id):
    user_id_str = str(user_id)
    if user_id_str not in guild_xp_data:
        guild_xp_data[user_id_str] = {"xp": 0, "level": 0, "last_message_timestamp": 0}
    return guild_xp_data[user_id_str]

def calculate_level_info(xp):
    current_level = 0
    for i, threshold in enumerate(LEVEL_XP_THRESHOLDS):
        if xp >= threshold:
            current_level = i
        else:
            break
    
    xp_for_current_level = LEVEL_XP_THRESHOLDS[current_level]
    xp_for_next_level = LEVEL_XP_THRESHOLDS[current_level + 1] if current_level + 1 < len(LEVEL_XP_THRESHOLDS) else float('inf')
    
    if xp_for_next_level == float('inf'):
        progress_percentage = 100
        xp_to_next = 0
        current_xp_in_level = xp - xp_for_current_level
    else:
        xp_needed_for_level_span = xp_for_next_level - xp_for_current_level
        current_xp_in_level = xp - xp_for_current_level
        progress_percentage = (current_xp_in_level / xp_needed_for_level_span) * 100 if xp_needed_for_level_span > 0 else 100
        xp_to_next = xp_for_next_level - xp

    return {
        "level": current_level,
        "xp_for_current_level": xp_for_current_level,
        "xp_for_next_level": xp_for_next_level,
        "current_xp_in_level": current_xp_in_level,
        "xp_to_next_level_total_span": xp_for_next_level - xp_for_current_level if xp_for_next_level != float('inf') else 0,
        "progress_percentage": round(progress_percentage, 2)
    }

def get_guild_level_roles(level_roles_dict, guild_id):
    """Get level roles data for a guild, creating if needed."""
    guild_id_str = str(guild_id)
    if guild_id_str not in level_roles_dict:
        level_roles_dict[guild_id_str] = {}
    return level_roles_dict[guild_id_str]

async def assign_level_roles(member, new_level, bot):
    """Assign roles based on user's new level."""
    if member.bot:
        return
    
    guild_id_str = str(member.guild.id)
    guild_level_roles = get_guild_level_roles(bot.level_roles, guild_id_str)
    
    if not guild_level_roles:
        return
    
    try:
        roles_to_add = []
        roles_to_remove = []
        
        for level_threshold, role_id in guild_level_roles.items():
            level_threshold = int(level_threshold)
            role = member.guild.get_role(int(role_id))
            
            if not role:
                continue
            
            if new_level >= level_threshold:
                if role not in member.roles:
                    roles_to_add.append(role)
            else:
                if role in member.roles:
                    roles_to_remove.append(role)
        
        if roles_to_add:
            await member.add_roles(*roles_to_add, reason=f"Level {new_level} role assignment")
        
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=f"Level {new_level} role adjustment")
            
    except Exception as e:
        print(f"Error assigning level roles to {member}: {e}")

class PaginationView(discord.ui.View):
    def __init__(self, total_pages, embed_builder, interaction_user_id, initial_page=0):
        super().__init__(timeout=180.0)
        self.current_page = initial_page
        self.total_pages = total_pages
        self.embed_builder = embed_builder
        self.interaction_user_id = interaction_user_id
        self.message = None  # Will store the message this view is attached to
        self.update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.interaction_user_id:
            await interaction.response.send_message("You cannot control this pagination.", ephemeral=True)
            return False
        return True

    def update_buttons(self):
        self.clear_items()
        
        # Only add navigation buttons if there's more than one page
        if self.total_pages > 1:
            prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.blurple, disabled=(self.current_page == 0))
            prev_button.callback = self.prev_page
            self.add_item(prev_button)

            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.blurple, disabled=(self.current_page == self.total_pages - 1))
            next_button.callback = self.next_page
            self.add_item(next_button)
            
            page_indicator = discord.ui.Button(label=f"Page {self.current_page + 1}/{self.total_pages}", style=discord.ButtonStyle.secondary, disabled=True)
            self.add_item(page_indicator)

    async def update_message(self, interaction: discord.Interaction):
        try:
            self.update_buttons()
            embed = await self.embed_builder(self.current_page)
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            print(f"Error updating pagination message: {e}")
            # Fallback: just update with no view if there's an error
            try:
                embed = await self.embed_builder(self.current_page)
                await interaction.response.edit_message(embed=embed, view=None)
            except Exception as fallback_error:
                print(f"Fallback pagination update also failed: {fallback_error}")

    async def prev_page(self, interaction: discord.Interaction):
        try:
            if self.current_page > 0:
                self.current_page -= 1
            await self.update_message(interaction)
        except Exception as e:
            print(f"Error in prev_page: {e}")

    async def next_page(self, interaction: discord.Interaction):
        try:
            if self.current_page < self.total_pages - 1:
                self.current_page += 1
            await self.update_message(interaction)
        except Exception as e:
            print(f"Error in next_page: {e}")

    async def on_timeout(self):
        """Called when the view times out"""
        try:
            # Disable all items when the view times out
            for item in self.children:
                item.disabled = True
            
            # Try to update the message to show disabled buttons
            if self.message:
                try:
                    await self.message.edit(view=self)
                except discord.NotFound:
                    # Message was deleted, nothing to update
                    pass
                except discord.HTTPException:
                    # Other HTTP error, try without view
                    try:
                        await self.message.edit(view=None)
                    except:
                        pass
        except Exception as e:
            print(f"Error in pagination timeout handler: {e}")
            # Stop the view to prevent further issues
            self.stop()