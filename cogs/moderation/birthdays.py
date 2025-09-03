import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import math
import random
from utils.helpers import *
from utils.config import *

class BirthdaysCog(commands.Cog, name="Birthdays"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setbirthday", description="Sets your birthday. Format: MM-DD or YYYY-MM-DD.")
    @app_commands.describe(birthday_str="Your birthday (e.g., 12-25 or 1990-12-25).")
    async def setbirthday_slash(self, interaction: discord.Interaction, birthday_str: str):
        parts = birthday_str.split('-')
        year, month, day = None, None, None

        try:
            if len(parts) == 2:
                month, day = int(parts[0]), int(parts[1])
                datetime(2020, month, day)
            elif len(parts) == 3:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                if not (1900 <= year <= datetime.now().year):
                    raise ValueError("Invalid year. Must be between 1900 and current year.")
                datetime(year, month, day)
            else:
                raise ValueError("Invalid format.")

            user_id_str = str(interaction.user.id)
            self.bot.birthdays[user_id_str] = {"month": month, "day": day}
            if year:
                self.bot.birthdays[user_id_str]["year"] = year
            
            next_bday_dt = get_next_birthday_datetime(month, day, year)
            
            embed = discord.Embed(title="Birthday Set!", color=discord.Color.green())
            bday_display = f"{month:02d}-{day:02d}"
            if year: bday_display = f"{year}-{bday_display}"
            embed.description = f"Your birthday is set to **{bday_display}**."
            
            date_str = f"**{next_bday_dt.strftime('%B %d, %Y')}**"
            embed.add_field(name="Next Birthday", value=f"{date_str} ({format_discord_timestamp(next_bday_dt.timestamp(), 'R')})")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await self.bot.save_immediately()

        except ValueError as e:
            await interaction.response.send_message(f"Invalid birthday: {e}. Use MM-DD or YYYY-MM-DD.", ephemeral=True)

    @app_commands.command(name="birthday", description="Shows birthday information for a user.")
    @app_commands.describe(member="The member to check (defaults to yourself).")
    async def get_birthday_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user
        
        user_id_str = str(member.id)
        bday_data = self.bot.birthdays.get(user_id_str)

        if not bday_data:
            await interaction.response.send_message(f"{member.mention} hasn't set their birthday. They can use /setbirthday.", ephemeral=True)
            return

        month, day = bday_data["month"], bday_data["day"]
        year = bday_data.get("year")
        
        next_bday_dt = get_next_birthday_datetime(month, day, year)
        
        embed = discord.Embed(color=discord.Color.blue())
        
        # Format the date in bold text instead of Discord timestamp
        date_str = f"**{next_bday_dt.strftime('%B %d, %Y')}**"
        
        bday_date_str = f"{datetime(2000, month, day).strftime('%B')} {get_ordinal(day)}"
        if year:
            bday_date_str = f"{datetime(year, month, day).strftime('%B')} {get_ordinal(day)}, {year}"
            now = datetime.now(timezone.utc)
            age = now.year - year - ((now.month, now.day) < (month, day))
            next_age = next_bday_dt.year - year - ((next_bday_dt.month, next_bday_dt.day) < (month, day))
            
            # Use extended 24-hour birthday check
            if is_birthday_today_extended(month, day, year):
                description = f"{member.mention}'s **{get_ordinal(next_age)} birthday** is **today**, on {date_str}. 🎂"
            else:
                description = f"{member.mention}'s **{get_ordinal(next_age)} birthday** is **{format_discord_timestamp(next_bday_dt.timestamp(), 'R')}**, on {date_str}."
        else:
            now = datetime.now(timezone.utc)
            # Use extended 24-hour birthday check
            if is_birthday_today_extended(month, day):
                description = f"{member.mention}'s **birthday** is **today**, on {date_str}. 🎂"
            else:
                description = f"{member.mention}'s **birthday** is **{format_discord_timestamp(next_bday_dt.timestamp(), 'R')}**, on {date_str}."

        embed.description = description
        
        # Update the notification message based on extended check
        if is_birthday_today_extended(month, day, year):
            embed.description += f"\n\nUse `/notifybirthday` to be notified when it's their birthday!"

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="birthdaycountdown", description="Shows a countdown to a user's next birthday.")
    @app_commands.describe(member="The member to check (defaults to yourself).")
    async def birthdaycountdown_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user

        user_id_str = str(member.id)
        bday_data = self.bot.birthdays.get(user_id_str)

        if not bday_data:
            await interaction.response.send_message(f"{member.mention} hasn't set their birthday yet.", ephemeral=True)
            return

        month, day = bday_data["month"], bday_data["day"]
        year = bday_data.get("year")
        next_bday_dt = get_next_birthday_datetime(month, day, year)
        now = datetime.now(timezone.utc)
        delta = next_bday_dt - now

        # Check if it's the extended birthday period (24 hours)
        if is_birthday_today_extended(month, day, year):
             await interaction.response.send_message(embed=discord.Embed(title="It's Today!", description=f"Happy Birthday to {member.mention}!", color=discord.Color.gold()))
             return

        if delta.total_seconds() <= 0:
             await interaction.response.send_message(embed=discord.Embed(title="It's Today!", description=f"Happy Birthday to {member.mention}!", color=discord.Color.gold()))
             return

        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        embed = discord.Embed(title=f"Countdown for {member.display_name}", color=discord.Color.gold())
        description_parts = [f"{days} days", f"{hours} hours", f"{minutes} minutes"]
        description = ", ".join(filter(None, description_parts))
        
        if year:
            next_age = next_bday_dt.year - year - ((next_bday_dt.month, next_bday_dt.day) < (month, day))
            description += f"\nuntil they turn **{next_age}**!"
        else:
            description += "\nuntil their birthday!"
        embed.description = description
        
        # Use bold text for date instead of Discord timestamp
        date_str = f"**{next_bday_dt.strftime('%B %d, %Y')}**"
        embed.add_field(name="Next Birthday Date", value=date_str, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="birthdays", description="Lists upcoming birthdays in this server.")
    async def list_birthdays_slash(self, interaction: discord.Interaction):
        try:
            if not self.bot.birthdays:
                await interaction.response.send_message("No birthdays have been set by anyone yet.", ephemeral=True)
                return

            now = datetime.now(timezone.utc)
            upcoming = []

            for user_id_str, data in self.bot.birthdays.items():
                member = interaction.guild.get_member(int(user_id_str))
                if not member: continue 

                month, day = data["month"], data["day"]
                year = data.get("year")
                
                next_bday_dt = get_next_birthday_datetime(month, day, year)
                days_until = (next_bday_dt.date() - now.date()).days
                
                age_info = ""
                if year:
                    next_age = next_bday_dt.year - year - ((next_bday_dt.month, next_bday_dt.day) < (month, day))
                    # Use extended birthday check for age display
                    if is_birthday_today_extended(month, day, year):
                        age_info = f" (is {next_age}!)"
                    elif days_until > 0:
                        age_info = f" (turning {next_age})"
                    else:
                        age_info = f" (turned {next_age})"

                # For sorting purposes, if it's the extended birthday today, treat as 0 days
                effective_days_until = 0 if is_birthday_today_extended(month, day, year) else days_until

                upcoming.append({
                    "days_until": effective_days_until,
                    "member": member,
                    "next_bday_dt": next_bday_dt,
                    "age_info": age_info,
                    "month": month,
                    "day": day
                })

            upcoming.sort(key=lambda x: (x["days_until"], x["month"], x["day"]))
            
            if not upcoming:
                await interaction.response.send_message("No users in this server have set their birthdays.", ephemeral=True)
                return

            async def birthdays_embed_builder(page_num):
                embed = discord.Embed(title=f"Upcoming Birthdays in {interaction.guild.name}", color=discord.Color.purple())
                start_index = page_num * ITEMS_PER_PAGE
                end_index = start_index + ITEMS_PER_PAGE
                
                page_birthdays = upcoming[start_index:end_index]
                
                description_lines = []
                current_header = None

                for entry in page_birthdays:
                    days_until = entry["days_until"]
                    header = ""
                    if days_until == 0: header = "Today"
                    elif days_until == 1: header = "Tomorrow"
                    else: header = f"**{entry['next_bday_dt'].strftime('%B %d, %Y')}**"

                    if header != current_header:
                        if description_lines: description_lines.append("") 
                        description_lines.append(f"**{header}**")
                        current_header = header
                    
                    description_lines.append(f"{entry['member'].mention}{entry['age_info']} {format_discord_timestamp(entry['next_bday_dt'].timestamp(), 'R')}")

                if not description_lines:
                    embed.description = "No birthdays on this page."
                else:
                    embed.description = "\n".join(description_lines)
                    
                embed.set_footer(text=f"Page {page_num + 1}/{math.ceil(len(upcoming) / ITEMS_PER_PAGE)}. Showing {len(page_birthdays)} of {len(upcoming)} total.")
                return embed

            total_pages = math.ceil(len(upcoming) / ITEMS_PER_PAGE)
            if total_pages == 0: 
                await interaction.response.send_message("No upcoming birthdays to display.", ephemeral=True)
                return
                
            initial_embed = await birthdays_embed_builder(0)
            if total_pages > 1:
                view = PaginationView(total_pages, birthdays_embed_builder, interaction.user.id)
                await interaction.response.send_message(embed=initial_embed, view=view)
                # Store message reference for timeout handling
                try:
                    view.message = await interaction.original_response()
                except Exception as e:
                    print(f"Could not store message reference for pagination: {e}")
            else:
                await interaction.response.send_message(embed=initial_embed)
                
        except Exception as e:
            print(f"Error in list_birthdays_slash: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("An error occurred while fetching birthdays.", ephemeral=True)
                else:
                    await interaction.followup.send("An error occurred while fetching birthdays.", ephemeral=True)
            except Exception as followup_error:
                print(f"Could not send error message: {followup_error}")

    @app_commands.command(name="notifybirthday", description="Toggle birthday notifications for a user.")
    @app_commands.describe(member="The member to toggle notifications for.")
    async def notifybirthday_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.bot:
            await interaction.response.send_message("You cannot set notifications for bots.", ephemeral=True)
            return
        
        target_user_id_str = str(member.id)
        if target_user_id_str not in self.bot.birthdays:
            await interaction.response.send_message(f"{member.mention} hasn't set their birthday yet. They need to use `/setbirthday` first.", ephemeral=True)
            return
        
        guild_id_str = str(interaction.guild.id)
        user_id_str = str(interaction.user.id)
        
        if guild_id_str not in self.bot.birthday_notifications:
            self.bot.birthday_notifications[guild_id_str] = {}
        if user_id_str not in self.bot.birthday_notifications[guild_id_str]:
            self.bot.birthday_notifications[guild_id_str][user_id_str] = []
        
        notifications_list = self.bot.birthday_notifications[guild_id_str][user_id_str]
        
        if target_user_id_str in notifications_list:
            notifications_list.remove(target_user_id_str)
            embed = discord.Embed(
                title="Birthday Notification Disabled",
                description=f"You will no longer be notified when it's {member.mention}'s birthday.",
                color=discord.Color.red()
            )
        else:
            notifications_list.append(target_user_id_str)
            embed = discord.Embed(
                title="Birthday Notification Enabled",
                description=f"You will now be notified when it's {member.mention}'s birthday! 🎉",
                color=discord.Color.green()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.bot.save_immediately()

    @app_commands.command(name="randombdfact", description="Get a random fun fact about birthdays.")
    async def randombdfact_slash(self, interaction: discord.Interaction):
        facts = [
            "The tradition of birthday cakes began in Ancient Greece.",
            "The 'Happy Birthday' song is the most recognized song in the English language.",
            "In 1962, Marilyn Monroe sang 'Happy Birthday, Mr. President' to President Kennedy.",
            "Ancient Romans were the first to celebrate birthdays for non-religious figures.",
            "Your birthday is shared with approximately 21 million other people worldwide.",
            "Queen Elizabeth II had two birthdays: her actual birthday and her 'official' one.",
            "The odds of being born on February 29th are 1 in 1,461."
        ]
        embed = discord.Embed(title="Random Birthday Fact", description=random.choice(facts), color=discord.Color.purple())
        await interaction.response.send_message(embed=embed)

    # Prefix command versions
    @commands.command(name="setbirthday", aliases=["setbday", "setbd", "birthday_set", "bday_set", "bd_set"])
    async def setbirthday_prefix(self, ctx: commands.Context, *, birthday_str: str = None):
        if birthday_str is None:
            await ctx.send("Please provide your birthday. Usage: `!setbirthday MM-DD` or `!setbirthday YYYY-MM-DD`")
            return
        
        parts = birthday_str.split('-')
        year, month, day = None, None, None

        try:
            if len(parts) == 2:
                month, day = int(parts[0]), int(parts[1])
                datetime(2020, month, day)
            elif len(parts) == 3:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                if not (1900 <= year <= datetime.now().year):
                    raise ValueError("Invalid year. Must be between 1900 and current year.")
                datetime(year, month, day)
            else:
                raise ValueError("Invalid format.")

            user_id_str = str(ctx.author.id)
            self.bot.birthdays[user_id_str] = {"month": month, "day": day}
            if year:
                self.bot.birthdays[user_id_str]["year"] = year
            
            next_bday_dt = get_next_birthday_datetime(month, day, year)
            
            embed = discord.Embed(title="Birthday Set!", color=discord.Color.green())
            bday_display = f"{month:02d}-{day:02d}"
            if year: bday_display = f"{year}-{bday_display}"
            embed.description = f"Your birthday is set to **{bday_display}**."
            
            # Use bold text for date instead of Discord timestamp
            date_str = f"**{next_bday_dt.strftime('%B %d, %Y')}**"
            embed.add_field(name="Next Birthday", value=f"{date_str} ({format_discord_timestamp(next_bday_dt.timestamp(), 'R')})")
            await ctx.send(embed=embed)
            await self.bot.save_immediately()

        except ValueError as e:
            await ctx.send(f"Invalid birthday: {e}. Use MM-DD or YYYY-MM-DD.")

    @commands.command(name="birthday", aliases=["bday", "bd", "getbirthday", "checkbirthday"])
    async def birthday_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Shows birthday information for a user."""
        if member is None:
            member = ctx.author
        
        user_id_str = str(member.id)
        bday_data = self.bot.birthdays.get(user_id_str)

        if not bday_data:
            await ctx.send(f"{member.mention} hasn't set their birthday. They can use `!setbirthday`.")
            return

        month, day = bday_data["month"], bday_data["day"]
        year = bday_data.get("year")
        
        next_bday_dt = get_next_birthday_datetime(month, day, year)
        
        embed = discord.Embed(color=discord.Color.blue())
        
        # Format the date in bold text instead of Discord timestamp
        date_str = f"**{next_bday_dt.strftime('%B %d, %Y')}**"
        
        bday_date_str = f"{datetime(2000, month, day).strftime('%B')} {get_ordinal(day)}"
        if year:
            bday_date_str = f"{datetime(year, month, day).strftime('%B')} {get_ordinal(day)}, {year}"
            now = datetime.now(timezone.utc)
            age = now.year - year - ((now.month, now.day) < (month, day))
            next_age = next_bday_dt.year - year - ((next_bday_dt.month, next_bday_dt.day) < (month, day))
            
            # Use extended 24-hour birthday check
            if is_birthday_today_extended(month, day, year):
                description = f"{member.mention}'s **{get_ordinal(next_age)} birthday** is **today**, on {date_str}. 🎂"
            else:
                description = f"{member.mention}'s **{get_ordinal(next_age)} birthday** is **{format_discord_timestamp(next_bday_dt.timestamp(), 'R')}**, on {date_str}."
        else:
            now = datetime.now(timezone.utc)
            # Use extended 24-hour birthday check
            if is_birthday_today_extended(month, day):
                description = f"{member.mention}'s **birthday** is **today**, on {date_str}. 🎂"
            else:
                description = f"{member.mention}'s **birthday** is **{format_discord_timestamp(next_bday_dt.timestamp(), 'R')}**, on {date_str}."

        embed.description = description
        
        # Update the notification message based on extended check
        if is_birthday_today_extended(month, day, year):
            embed.description += f"\n\nUse `{COMMAND_PREFIX}notifybirthday` to be notified when it's their birthday!"

        await ctx.send(embed=embed)

    @commands.command(name="birthdays", aliases=["bdays", "birthdaylist", "listbirthdays", "upcomingbirthdays"])
    async def birthdays_prefix(self, ctx: commands.Context):
        """Lists upcoming birthdays in this server."""
        if not self.bot.birthdays:
            await ctx.send("No birthdays have been set by anyone yet.")
            return

        now = datetime.now(timezone.utc)
        upcoming = []

        for user_id_str, data in self.bot.birthdays.items():
            member = ctx.guild.get_member(int(user_id_str))
            if not member: continue 

            month, day = data["month"], data["day"]
            year = data.get("year")
            
            next_bday_dt = get_next_birthday_datetime(month, day, year)
            days_until = (next_bday_dt.date() - now.date()).days
            
            age_info = ""
            if year:
                next_age = next_bday_dt.year - year - ((next_bday_dt.month, next_bday_dt.day) < (month, day))
                # Use extended birthday check for age display
                if is_birthday_today_extended(month, day, year):
                    age_info = f" (is {next_age}!)"
                elif days_until > 0:
                    age_info = f" (turning {next_age})"
                else:
                    age_info = f" (turned {next_age})"

            # For sorting purposes, if it's the extended birthday today, treat as 0 days
            effective_days_until = 0 if is_birthday_today_extended(month, day, year) else days_until

            upcoming.append({
                "days_until": effective_days_until,
                "member": member,
                "next_bday_dt": next_bday_dt,
                "age_info": age_info,
                "month": month,
                "day": day
            })

        upcoming.sort(key=lambda x: (x["days_until"], x["month"], x["day"]))
        
        if not upcoming:
            await ctx.send("No users in this server have set their birthdays.")
            return

        embed = discord.Embed(title=f"Upcoming Birthdays in {ctx.guild.name}", color=discord.Color.purple())
        
        description_lines = []
        current_header = None

        for i, entry in enumerate(upcoming[:15]):  # Show top 15
            days_until = entry["days_until"]
            header = ""
            if days_until == 0: header = "Today"
            elif days_until == 1: header = "Tomorrow"
            else: header = f"**{entry['next_bday_dt'].strftime('%B %d, %Y')}**"

            if header != current_header:
                if description_lines: description_lines.append("") 
                description_lines.append(f"**{header}**")
                current_header = header
            
            description_lines.append(f"{entry['member'].mention}{entry['age_info']} {format_discord_timestamp(entry['next_bday_dt'].timestamp(), 'R')}")

        embed.description = "\n".join(description_lines)
        
        if len(upcoming) > 15:
            embed.set_footer(text=f"Showing 15 of {len(upcoming)} birthdays. Use /birthdays for full list with pagination.")
        else:
            embed.set_footer(text=f"Showing all {len(upcoming)} birthdays.")
        
        await ctx.send(embed=embed)

    @commands.command(name="birthdaycountdown", aliases=["bdcountdown", "countdown", "timeuntilbirthday"])
    async def birthdaycountdown_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Shows a countdown to a user's next birthday."""
        if member is None:
            member = ctx.author

        user_id_str = str(member.id)
        bday_data = self.bot.birthdays.get(user_id_str)

        if not bday_data:
            await ctx.send(f"{member.mention} hasn't set their birthday yet.")
            return

        month, day = bday_data["month"], bday_data["day"]
        year = bday_data.get("year")
        next_bday_dt = get_next_birthday_datetime(month, day, year)
        now = datetime.now(timezone.utc)
        delta = next_bday_dt - now

        # Check if it's the extended birthday period (24 hours)
        if is_birthday_today_extended(month, day, year):
             await ctx.send(embed=discord.Embed(title="It's Today!", description=f"Happy Birthday to {member.mention}!", color=discord.Color.gold()))
             return

        if delta.total_seconds() <= 0:
             await ctx.send(embed=discord.Embed(title="It's Today!", description=f"Happy Birthday to {member.mention}!", color=discord.Color.gold()))
             return

        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        embed = discord.Embed(title=f"Countdown for {member.display_name}", color=discord.Color.gold())
        description_parts = [f"{days} days", f"{hours} hours", f"{minutes} minutes"]
        description = ", ".join(filter(None, description_parts))
        
        if year:
            next_age = next_bday_dt.year - year - ((next_bday_dt.month, next_bday_dt.day) < (month, day))
            description += f"\nuntil they turn **{next_age}**!"
        else:
            description += "\nuntil their birthday!"
        embed.description = description
        
        # Use bold text for date instead of Discord timestamp
        date_str = f"**{next_bday_dt.strftime('%B %d, %Y')}**"
        embed.add_field(name="Next Birthday Date", value=date_str, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="notifybirthday", aliases=["notifybday", "bdnotify", "birthdaynotify", "togglenotify"])
    async def notifybirthday_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Toggle birthday notifications for a user."""
        if member is None:
            await ctx.send("Please specify a member. Usage: `!notifybirthday @user`")
            return
            
        if member.bot:
            await ctx.send("You cannot set notifications for bots.")
            return
        
        target_user_id_str = str(member.id)
        if target_user_id_str not in self.bot.birthdays:
            await ctx.send(f"{member.mention} hasn't set their birthday yet. They need to use `{COMMAND_PREFIX}setbirthday` first.")
            return
        
        guild_id_str = str(ctx.guild.id)
        user_id_str = str(ctx.author.id)
        
        if guild_id_str not in self.bot.birthday_notifications:
            self.bot.birthday_notifications[guild_id_str] = {}
        if user_id_str not in self.bot.birthday_notifications[guild_id_str]:
            self.bot.birthday_notifications[guild_id_str][user_id_str] = []
        
        notifications_list = self.bot.birthday_notifications[guild_id_str][user_id_str]
        
        if target_user_id_str in notifications_list:
            notifications_list.remove(target_user_id_str)
            embed = discord.Embed(
                title="Birthday Notification Disabled",
                description=f"You will no longer be notified when it's {member.mention}'s birthday.",
                color=discord.Color.red()
            )
        else:
            notifications_list.append(target_user_id_str)
            embed = discord.Embed(
                title="Birthday Notification Enabled",
                description=f"You will now be notified when it's {member.mention}'s birthday! 🎉",
                color=discord.Color.green()
            )

        await ctx.send(embed=embed)
        await self.bot.save_immediately()

    @commands.command(name="randombdfact", aliases=["bdfact", "birthdayfact", "randomfact"])
    async def randombdfact_prefix(self, ctx: commands.Context):
        """Get a random fun fact about birthdays."""
        facts = [
            "The tradition of birthday cakes began in Ancient Greece.",
            "The 'Happy Birthday' song is the most recognized song in the English language.",
            "In 1962, Marilyn Monroe sang 'Happy Birthday, Mr. President' to President Kennedy.",
            "Ancient Romans were the first to celebrate birthdays for non-religious figures.",
            "Your birthday is shared with approximately 21 million other people worldwide.",
            "Queen Elizabeth II had two birthdays: her actual birthday and her 'official' one.",
            "The odds of being born on February 29th are 1 in 1,461."
        ]
        embed = discord.Embed(title="Random Birthday Fact", description=random.choice(facts), color=discord.Color.purple())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(BirthdaysCog(bot))