import discord
from discord.ext import commands
from discord import app_commands
import math
import time
from utils.helpers import *
from utils.config import *

class LevelingCog(commands.Cog, name="Leveling"):
    def __init__(self, bot):
        self.bot = bot

    async def safe_edit_progress(self, message, embed=None, content=None):
        """Safely edit progress message with 401 webhook error handling"""
        try:
            if embed:
                await message.edit(embed=embed)
            elif content:
                await message.edit(content=content)
            return True
        except discord.HTTPException as e:
            # Check for 401 unauthorized (invalid webhook token)
            if e.status == 401 or "401" in str(e) or "unauthorized" in str(e).lower() or "invalid webhook token" in str(e).lower():
                print(f"Progress update failed due to invalid webhook token (401). This is normal for long-running commands.")
                # Try to send a new message instead
                try:
                    if embed:
                        await message.channel.send(embed=embed)
                    elif content:
                        await message.channel.send(content=content)
                    return True
                except Exception as fallback_error:
                    print(f"Fallback progress update also failed: {fallback_error}")
                    return False
            else:
                print(f"Progress update failed with error: {e}")
                return False
        except Exception as e:
            print(f"Unexpected error during progress update: {e}")
            return False

    @app_commands.command(name="level", description="Shows XP and level for a user (or yourself).")
    @app_commands.describe(member="The member to check (defaults to yourself).")
    async def level_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user
        
        if member.bot:
            await interaction.response.send_message("Bots don't have levels.", ephemeral=True)
            return

        guild_id_str = str(interaction.guild.id)
        user_id_str = str(member.id)

        guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
        user_entry = get_user_xp_entry(guild_xp_data, user_id_str)
        
        level_info = calculate_level_info(user_entry["xp"])

        sorted_users = sorted(
            [(uid, udata) for uid, udata in guild_xp_data.items() if interaction.guild.get_member(int(uid)) and not interaction.guild.get_member(int(uid)).bot],
            key=lambda item: item[1].get('xp', 0), 
            reverse=True
        )
        rank = "N/A"
        for i, (uid, udata) in enumerate(sorted_users):
            if uid == user_id_str:
                rank = i + 1
                break
                
        embed = discord.Embed(title=f"{member.display_name} — Rank #{rank}", color=member.color or discord.Color.blue())
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="Level", value=str(level_info["level"]))
        embed.add_field(name="Total XP", value=str(user_entry["xp"]))
        
        messages_approx = user_entry["xp"] // XP_PER_MESSAGE if XP_PER_MESSAGE > 0 else 0
        embed.add_field(name="Messages", value=str(messages_approx))

        if level_info["xp_for_next_level"] == float('inf'): 
            embed.add_field(name="XP Progress", value="🌟 **Max Level Reached!**", inline=False)
        else:
            progress_bar_length = 20
            filled_length = int(progress_bar_length * level_info["progress_percentage"] / 100)
            
            full_block = "█"
            empty_block = "░"
            
            progress_bar = full_block * filled_length + empty_block * (progress_bar_length - filled_length)
            
            xp_progress_str = f"{progress_bar}\n**{level_info['current_xp_in_level']}** / **{level_info['xp_to_next_level_total_span']}** XP"
            embed.add_field(name="XP Progress", value=xp_progress_str, inline=False)

        embed.set_footer(text="Use /levels to see the rankings.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="levels", description="Shows the server's XP leaderboard.")
    async def levels_slash(self, interaction: discord.Interaction):
        guild_id_str = str(interaction.guild.id)
        guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)

        if not guild_xp_data:
            await interaction.response.send_message("No one has earned any XP in this server yet.", ephemeral=True)
            return

        valid_user_entries = []
        for user_id_str, data in guild_xp_data.items():
            member = interaction.guild.get_member(int(user_id_str))
            if member and not member.bot : 
                valid_user_entries.append({"id": user_id_str, "data": data, "member_obj":member})
        
        if not valid_user_entries:
            await interaction.response.send_message("No users with XP found (bots are excluded).", ephemeral=True)
            return

        sorted_users = sorted(valid_user_entries, key=lambda x: x["data"].get("xp", 0), reverse=True)

        async def leaderboard_embed_builder(page_num):
            embed = discord.Embed(title=f"XP Leaderboard for {interaction.guild.name}", color=discord.Color.gold())
            start_index = page_num * ITEMS_PER_PAGE
            end_index = start_index + ITEMS_PER_PAGE
            
            description_lines = []
            for i, user_entry_obj in enumerate(sorted_users[start_index:end_index], start=start_index + 1):
                member = user_entry_obj["member_obj"]
                data = user_entry_obj["data"]
                level_info = calculate_level_info(data.get("xp", 0))
                
                prog_percent_str = ""
                if level_info["xp_for_next_level"] != float('inf'): 
                     prog_percent_str = f" ({level_info['progress_percentage']}%)"

                description_lines.append(f"**{i}.** {member.mention} - Level: {level_info['level']}, XP: {data.get('xp', 0)}{prog_percent_str}")

            if not description_lines:
                embed.description = "No users on this page."
            else:
                embed.description = "\n".join(description_lines)
            
            embed.set_footer(text=f"Page {page_num + 1}/{math.ceil(len(sorted_users) / ITEMS_PER_PAGE)}. Showing {len(description_lines)} of {len(sorted_users)} users.")
            return embed

        total_pages = math.ceil(len(sorted_users) / ITEMS_PER_PAGE)
        if total_pages == 0:
            await interaction.response.send_message("No users to display on the leaderboard.", ephemeral=True)
            return
            
        initial_embed = await leaderboard_embed_builder(0)
        view = PaginationView(total_pages, leaderboard_embed_builder, interaction.user.id) if total_pages > 1 else None
        await interaction.response.send_message(embed=initial_embed, view=view)

    @app_commands.command(name="calculatexp", description="Calculate and assign XP based on all messages (Admin only).")
    @app_commands.describe(
        member="The member to calculate XP for (leave empty to calculate for ALL users).",
        all_users="Set to True to calculate XP for all users at once (much faster)."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def calculatexp_slash(self, interaction: discord.Interaction, member: discord.Member = None, all_users: bool = False):
        if member and member.bot:
            await interaction.response.send_message("Bots don't have XP.", ephemeral=True)
            return

        if not member and not all_users:
            await interaction.response.send_message("Please specify a member or set `all_users` to True to calculate for everyone.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        
        channels = [channel for channel in interaction.guild.text_channels if channel.permissions_for(interaction.guild.me).read_message_history]
        
        if not channels:
            await interaction.followup.send("I don't have permission to read message history in any channels.", ephemeral=True)
            return

        # Single user calculation (existing method)
        if member and not all_users:
            await self._calculate_single_user_slash(interaction, member, channels)
            return

        # All users calculation (new efficient method)
        await self._calculate_all_users_slash(interaction, channels)

    async def _calculate_single_user_slash(self, interaction, member, channels):
        """Original single-user calculation method for slash commands"""
        total_messages = 0
        eligible_messages = 0
        messages_with_timestamps = []
        processed_channels = 0
        
        # Track timing
        start_time = time.time()
        last_update_time = start_time

        progress_embed = discord.Embed(
            title="📊 Calculating XP Progress", 
            description=f"Processing {member.mention}'s message history...",
            color=discord.Color.orange()
        )
        progress_embed.add_field(name="Progress", value=f"0/{len(channels)} channels processed", inline=True)
        progress_embed.add_field(name="Messages Found", value="0", inline=True)
        progress_embed.add_field(name="Status", value="🔍 Scanning channels...", inline=False)
        progress_embed.set_footer(text="⏱️ Just started...")
        
        progress_msg = await interaction.followup.send(embed=progress_embed)

        for channel in channels:
            try:
                channel_messages = 0
                async for message in channel.history(limit=None):
                    if message.author == member:
                        total_messages += 1
                        channel_messages += 1
                        messages_with_timestamps.append(message.created_at.timestamp())
                        
                        if total_messages % 100 == 0:
                            current_time = time.time()
                            time_since_last = int(current_time - last_update_time)
                            total_elapsed = int(current_time - start_time)
                            
                            progress_embed.set_field_at(1, name="Messages Found", value=str(total_messages), inline=True)
                            progress_embed.set_field_at(2, name="Status", value=f"🔍 Scanning #{channel.name}... ({channel_messages} found)", inline=False)
                            progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                            await self.safe_edit_progress(progress_msg, embed=progress_embed)
                            last_update_time = current_time
                            
                processed_channels += 1
                current_time = time.time()
                time_since_last = int(current_time - last_update_time)
                total_elapsed = int(current_time - start_time)
                
                progress_embed.set_field_at(0, name="Progress", value=f"{processed_channels}/{len(channels)} channels processed", inline=True)
                progress_embed.set_field_at(1, name="Messages Found", value=str(total_messages), inline=True)
                
                if processed_channels < len(channels):
                    progress_embed.set_field_at(2, name="Status", value=f"✅ Completed #{channel.name} ({channel_messages} messages)", inline=False)
                else:
                    progress_embed.set_field_at(2, name="Status", value="🧮 Calculating XP based on cooldowns...", inline=False)
                
                progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                await self.safe_edit_progress(progress_msg, embed=progress_embed)
                last_update_time = current_time
                            
            except Exception as e:
                print(f"Error reading history in {channel.name}: {e}")
                continue

        if total_messages == 0:
            error_embed = discord.Embed(
                title="❌ No Messages Found",
                description=f"{member.mention} has no messages in this server.",
                color=discord.Color.red()
            )
            total_elapsed = int(time.time() - start_time)
            error_embed.set_footer(text=f"⏱️ Completed in {total_elapsed}s")
            await self.safe_edit_progress(progress_msg, embed=error_embed)
            return

        current_time = time.time()
        time_since_last = int(current_time - last_update_time)
        total_elapsed = int(current_time - start_time)
        
        progress_embed.set_field_at(2, name="Status", value="🧮 Applying 30-second cooldown rules...", inline=False)
        progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
        await self.safe_edit_progress(progress_msg, embed=progress_embed)
        last_update_time = current_time

        messages_with_timestamps.sort()
        
        last_xp_time = 0
        for i, timestamp in enumerate(messages_with_timestamps):
            if timestamp - last_xp_time >= MESSAGE_COOLDOWN_SECONDS:
                eligible_messages += 1
                last_xp_time = timestamp
                
            if i % 1000 == 0 and i > 0:
                current_time = time.time()
                time_since_last = int(current_time - last_update_time)
                total_elapsed = int(current_time - start_time)
                progress_percent = (i / len(messages_with_timestamps)) * 100
                
                progress_embed.set_field_at(2, name="Status", value=f"🧮 Processing messages... ({progress_percent:.1f}% complete)", inline=False)
                progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                await self.safe_edit_progress(progress_msg, embed=progress_embed)
                last_update_time = current_time

        calculated_xp = eligible_messages * XP_PER_MESSAGE
        
        guild_id_str = str(interaction.guild.id)
        user_id_str = str(member.id)
        
        guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
        user_entry = get_user_xp_entry(guild_xp_data, user_id_str)
        
        old_xp = user_entry["xp"]
        user_entry["xp"] = calculated_xp
        user_entry["last_message_timestamp"] = messages_with_timestamps[-1] if messages_with_timestamps else 0
        
        level_info = calculate_level_info(calculated_xp)
        user_entry["level"] = level_info["level"]
        
        total_elapsed = int(time.time() - start_time)
        
        embed = discord.Embed(title="✅ XP Calculation Complete", color=discord.Color.green())
        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Total Messages", value=f"{total_messages:,}", inline=True)
        embed.add_field(name="Eligible Messages", value=f"{eligible_messages:,} (after {MESSAGE_COOLDOWN_SECONDS}s cooldown)", inline=True)
        embed.add_field(name="Previous XP", value=f"{old_xp:,}", inline=True)
        embed.add_field(name="Calculated XP", value=f"{calculated_xp:,}", inline=True)
        embed.add_field(name="XP Difference", value=f"{calculated_xp - old_xp:+,}", inline=True)
        embed.add_field(name="New Level", value=str(level_info["level"]), inline=True)
        
        if len(channels) > 1:
            embed.set_footer(text=f"Processed {len(channels)} channels in {total_elapsed}s total.")
        else:
            embed.set_footer(text=f"Completed in {total_elapsed}s.")
        
        await self.safe_edit_progress(progress_msg, embed=embed)
        await self.bot.save_immediately()

    async def _calculate_all_users_slash(self, interaction, channels):
        """Efficient all-users calculation method for slash commands"""
        user_messages = {}  # {user_id: [timestamps]}
        total_messages_processed = 0
        processed_channels = 0

        # Track timing
        start_time = time.time()
        last_update_time = start_time

        progress_embed = discord.Embed(
            title="🚀 Calculating XP for ALL Users", 
            description=f"Processing entire server message history (much faster!)...",
            color=discord.Color.orange()
        )
        progress_embed.add_field(name="Progress", value=f"0/{len(channels)} channels processed", inline=True)
        progress_embed.add_field(name="Messages Processed", value="0", inline=True)
        progress_embed.add_field(name="Users Found", value="0", inline=True)
        progress_embed.add_field(name="Status", value="🔍 Scanning channels...", inline=False)
        progress_embed.set_footer(text="⏱️ Just started...")
        
        progress_msg = await interaction.followup.send(embed=progress_embed)

        # Collect all messages from all users in one pass
        for channel in channels:
            try:
                channel_messages = 0
                async for message in channel.history(limit=None):
                    if not message.author.bot:  # Skip bots
                        user_id = str(message.author.id)
                        if user_id not in user_messages:
                            user_messages[user_id] = []
                        
                        user_messages[user_id].append(message.created_at.timestamp())
                        total_messages_processed += 1
                        channel_messages += 1
                        
                        if total_messages_processed % 500 == 0:
                            current_time = time.time()
                            time_since_last = int(current_time - last_update_time)
                            total_elapsed = int(current_time - start_time)
                            
                            progress_embed.set_field_at(1, name="Messages Processed", value=f"{total_messages_processed:,}", inline=True)
                            progress_embed.set_field_at(2, name="Users Found", value=str(len(user_messages)), inline=True)
                            progress_embed.set_field_at(3, name="Status", value=f"🔍 Scanning #{channel.name}... ({channel_messages:,} found)", inline=False)
                            progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                            await self.safe_edit_progress(progress_msg, embed=progress_embed)
                            last_update_time = current_time
                            
                processed_channels += 1
                current_time = time.time()
                time_since_last = int(current_time - last_update_time)
                total_elapsed = int(current_time - start_time)
                
                progress_embed.set_field_at(0, name="Progress", value=f"{processed_channels}/{len(channels)} channels processed", inline=True)
                progress_embed.set_field_at(1, name="Messages Processed", value=f"{total_messages_processed:,}", inline=True)
                progress_embed.set_field_at(2, name="Users Found", value=str(len(user_messages)), inline=True)
                
                if processed_channels < len(channels):
                    progress_embed.set_field_at(3, name="Status", value=f"✅ Completed #{channel.name} ({channel_messages:,} messages)", inline=False)
                else:
                    progress_embed.set_field_at(3, name="Status", value="🧮 Calculating XP for all users...", inline=False)
                
                progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                await self.safe_edit_progress(progress_msg, embed=progress_embed)
                last_update_time = current_time
                            
            except Exception as e:
                print(f"Error reading history in {channel.name}: {e}")
                continue

        if not user_messages:
            error_embed = discord.Embed(
                title="❌ No Messages Found",
                description="No user messages found in this server.",
                color=discord.Color.red()
            )
            total_elapsed = int(time.time() - start_time)
            error_embed.set_footer(text=f"⏱️ Completed in {total_elapsed}s")
            await self.safe_edit_progress(progress_msg, embed=error_embed)
            return

        # Calculate XP for each user
        guild_id_str = str(interaction.guild.id)
        guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
        
        users_updated = 0
        total_eligible_messages = 0
        users_processed = 0
        
        for user_id, timestamps in user_messages.items():
            # Sort timestamps for this user
            timestamps.sort()
            
            # Apply cooldown rules
            eligible_messages = 0
            last_xp_time = 0
            
            for timestamp in timestamps:
                if timestamp - last_xp_time >= MESSAGE_COOLDOWN_SECONDS:
                    eligible_messages += 1
                    last_xp_time = timestamp
            
            if eligible_messages > 0:
                calculated_xp = eligible_messages * XP_PER_MESSAGE
                user_entry = get_user_xp_entry(guild_xp_data, user_id)
                
                user_entry["xp"] = calculated_xp
                user_entry["last_message_timestamp"] = timestamps[-1]
                
                level_info = calculate_level_info(calculated_xp)
                user_entry["level"] = level_info["level"]
                
                users_updated += 1
                total_eligible_messages += eligible_messages
            
            users_processed += 1
            
            # Update progress every 10 users
            if users_processed % 10 == 0:
                current_time = time.time()
                time_since_last = int(current_time - last_update_time)
                total_elapsed = int(current_time - start_time)
                progress_percent = (users_processed / len(user_messages)) * 100
                
                progress_embed.set_field_at(3, name="Status", value=f"🧮 Calculating XP... ({progress_percent:.1f}% complete, {users_updated} users updated)", inline=False)
                progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                await self.safe_edit_progress(progress_msg, embed=progress_embed)
                last_update_time = current_time

        # Final results
        total_elapsed = int(time.time() - start_time)
        
        embed = discord.Embed(title="🎉 Mass XP Calculation Complete", color=discord.Color.green())
        embed.add_field(name="📊 Results", value=f"**{users_updated:,}** users updated", inline=False)
        embed.add_field(name="📝 Total Messages", value=f"{total_messages_processed:,}", inline=True)
        embed.add_field(name="✅ Eligible Messages", value=f"{total_eligible_messages:,}", inline=True)
        embed.add_field(name="⏱️ Cooldown Applied", value=f"{MESSAGE_COOLDOWN_SECONDS}s between messages", inline=True)
        embed.add_field(name="📁 Channels Processed", value=f"{len(channels)}", inline=True)
        embed.add_field(name="🚀 Efficiency", value="All users calculated in single pass!", inline=True)
        
        embed.set_footer(text=f"Completed in {total_elapsed}s total. Much faster than individual calculations!")
        
        await self.safe_edit_progress(progress_msg, embed=embed)
        await self.bot.save_immediately()

    # Prefix command versions
    @commands.command(name="level", aliases=["lvl", "xp", "rank", "getlevel", "getxp", "stats"])
    async def level_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Shows XP and level for a user (or yourself)."""
        if member is None:
            member = ctx.author
        
        if member.bot:
            await ctx.send("Bots don't have levels.")
            return

        guild_id_str = str(ctx.guild.id)
        user_id_str = str(member.id)

        guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
        user_entry = get_user_xp_entry(guild_xp_data, user_id_str)
        
        level_info = calculate_level_info(user_entry["xp"])

        sorted_users = sorted(
            [(uid, udata) for uid, udata in guild_xp_data.items() if ctx.guild.get_member(int(uid)) and not ctx.guild.get_member(int(uid)).bot],
            key=lambda item: item[1].get('xp', 0), 
            reverse=True
        )
        rank = "N/A"
        for i, (uid, udata) in enumerate(sorted_users):
            if uid == user_id_str:
                rank = i + 1
                break
                
        embed = discord.Embed(title=f"{member.display_name} — Rank #{rank}", color=member.color or discord.Color.blue())
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(name="Level", value=str(level_info["level"]))
        embed.add_field(name="Total XP", value=str(user_entry["xp"]))
        
        messages_approx = user_entry["xp"] // XP_PER_MESSAGE if XP_PER_MESSAGE > 0 else 0
        embed.add_field(name="Messages", value=str(messages_approx))

        if level_info["xp_for_next_level"] == float('inf'): 
            embed.add_field(name="XP Progress", value="🌟 **Max Level Reached!**", inline=False)
        else:
            progress_bar_length = 20
            filled_length = int(progress_bar_length * level_info["progress_percentage"] / 100)
            
            full_block = "█"
            empty_block = "░"
            
            progress_bar = full_block * filled_length + empty_block * (progress_bar_length - filled_length)
            
            xp_progress_str = f"{progress_bar}\n**{level_info['current_xp_in_level']}** / **{level_info['xp_to_next_level_total_span']}** XP"
            embed.add_field(name="XP Progress", value=xp_progress_str, inline=False)

        embed.set_footer(text=f"Use {COMMAND_PREFIX}levels to see the rankings.")
        await ctx.send(embed=embed)

    @commands.command(name="levels", aliases=["leaderboard", "lb", "top", "rankings", "leveltop", "xptop", "ranks"])
    async def levels_prefix(self, ctx: commands.Context):
        """Shows the server's XP leaderboard."""
        guild_id_str = str(ctx.guild.id)
        guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)

        if not guild_xp_data:
            await ctx.send("No one has earned any XP in this server yet.")
            return

        valid_user_entries = []
        for user_id_str, data in guild_xp_data.items():
            member = ctx.guild.get_member(int(user_id_str))
            if member and not member.bot : 
                valid_user_entries.append({"id": user_id_str, "data": data, "member_obj":member})
        
        if not valid_user_entries:
            await ctx.send("No users with XP found (bots are excluded).")
            return

        sorted_users = sorted(valid_user_entries, key=lambda x: x["data"].get("xp", 0), reverse=True)

        embed = discord.Embed(title=f"XP Leaderboard for {ctx.guild.name}", color=discord.Color.gold())
        
        description_lines = []
        for i, user_entry_obj in enumerate(sorted_users[:10], start=1):
            member = user_entry_obj["member_obj"]
            data = user_entry_obj["data"]
            level_info = calculate_level_info(data.get("xp", 0))
            
            prog_percent_str = ""
            if level_info["xp_for_next_level"] != float('inf'): 
                 prog_percent_str = f" ({level_info['progress_percentage']}%)"

            description_lines.append(f"**{i}.** {member.mention} - Level: {level_info['level']}, XP: {data.get('xp', 0)}{prog_percent_str}")

        embed.description = "\n".join(description_lines)
        if len(sorted_users) > 10:
            embed.set_footer(text=f"Showing top 10 of {len(sorted_users)} users. Use /levels for full leaderboard with pagination.")
        else:
            embed.set_footer(text=f"Showing all {len(sorted_users)} users.")
        
        await ctx.send(embed=embed)

    @commands.command(name="calculatexp", aliases=["calcxp", "historicalxp", "retroxp", "calcall", "massxp"])
    @commands.has_permissions(administrator=True)
    async def calculatexp_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Calculate and assign XP based on all messages. Use 'all' instead of @user to calculate for everyone."""
        # Check if user wants to calculate for everyone
        message_parts = ctx.message.content.lower().split()
        
        # Check if 'all', 'everyone', '*', or 'mass' appears as a separate word/argument
        all_users = False
        if any(keyword in message_parts for keyword in ['all', 'everyone', '*', 'mass']):
            member = None
            all_users = True
        elif member is None:
            await ctx.send("Please specify a member or use `!calculatexp all` to calculate for everyone.\n**Usage:**\n• `!calculatexp @user` - Calculate for one user\n• `!calculatexp all` - Calculate for everyone")
            return
        else:
            all_users = False
            
        if member and member.bot:
            await ctx.send("Bots don't have XP.")
            return

        channels = [channel for channel in ctx.guild.text_channels if channel.permissions_for(ctx.guild.me).read_message_history]
        
        if not channels:
            await ctx.send("I don't have permission to read message history in any channels.")
            return

        # Use the appropriate method
        if all_users:
            await self._calculate_all_users_prefix(ctx, channels)
        else:
            await self._calculate_single_user_prefix(ctx, member, channels)

    async def _calculate_all_users_prefix(self, ctx, channels):
        """All users calculation for prefix command"""
        user_messages = {}
        total_messages_processed = 0
        processed_channels = 0

        # Track timing
        start_time = time.time()
        last_update_time = start_time

        progress_embed = discord.Embed(
            title="🚀 Calculating XP for ALL Users", 
            description=f"Processing entire server message history...",
            color=discord.Color.orange()
        )
        progress_embed.add_field(name="Progress", value=f"0/{len(channels)} channels", inline=True)
        progress_embed.add_field(name="Messages", value="0", inline=True)
        progress_embed.add_field(name="Users", value="0", inline=True)
        progress_embed.set_footer(text="⏱️ Just started...")
        
        progress_msg = await ctx.send(embed=progress_embed)

        # Same logic as slash command but adapted for prefix
        for channel in channels:
            try:
                channel_messages = 0
                async for message in channel.history(limit=None):
                    if not message.author.bot:
                        user_id = str(message.author.id)
                        if user_id not in user_messages:
                            user_messages[user_id] = []
                        
                        user_messages[user_id].append(message.created_at.timestamp())
                        total_messages_processed += 1
                        channel_messages += 1
                        
                        if total_messages_processed % 500 == 0:
                            current_time = time.time()
                            time_since_last = int(current_time - last_update_time)
                            total_elapsed = int(current_time - start_time)
                            
                            progress_embed.set_field_at(1, name="Messages", value=f"{total_messages_processed:,}", inline=True)
                            progress_embed.set_field_at(2, name="Users", value=str(len(user_messages)), inline=True)
                            progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                            await self.safe_edit_progress(progress_msg, embed=progress_embed)
                            last_update_time = current_time
                            
                processed_channels += 1
                current_time = time.time()
                time_since_last = int(current_time - last_update_time)
                total_elapsed = int(current_time - start_time)
                
                progress_embed.set_field_at(0, name="Progress", value=f"{processed_channels}/{len(channels)} channels", inline=True)
                progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                await self.safe_edit_progress(progress_msg, embed=progress_embed)
                last_update_time = current_time
                            
            except Exception as e:
                print(f"Error reading history in {channel.name}: {e}")
                continue

        # Calculate XP for all users
        guild_id_str = str(ctx.guild.id)
        guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
        
        users_updated = 0
        total_eligible_messages = 0
        
        for user_id, timestamps in user_messages.items():
            timestamps.sort()
            eligible_messages = 0
            last_xp_time = 0
            
            for timestamp in timestamps:
                if timestamp - last_xp_time >= MESSAGE_COOLDOWN_SECONDS:
                    eligible_messages += 1
                    last_xp_time = timestamp
            
            if eligible_messages > 0:
                calculated_xp = eligible_messages * XP_PER_MESSAGE
                user_entry = get_user_xp_entry(guild_xp_data, user_id)
                
                user_entry["xp"] = calculated_xp
                user_entry["last_message_timestamp"] = timestamps[-1]
                
                level_info = calculate_level_info(calculated_xp)
                user_entry["level"] = level_info["level"]
                
                users_updated += 1
                total_eligible_messages += eligible_messages

        # Final results
        total_elapsed = int(time.time() - start_time)
        
        embed = discord.Embed(title="🎉 Mass XP Calculation Complete", color=discord.Color.green())
        embed.add_field(name="Users Updated", value=f"{users_updated:,}", inline=True)
        embed.add_field(name="Messages Processed", value=f"{total_messages_processed:,}", inline=True)
        embed.add_field(name="Eligible Messages", value=f"{total_eligible_messages:,}", inline=True)
        embed.set_footer(text=f"Completed in {total_elapsed}s. Much faster than individual calculations!")
        
        await self.safe_edit_progress(progress_msg, embed=embed)
        await self.bot.save_immediately()

    async def _calculate_single_user_prefix(self, ctx, member, channels):
        """Single user calculation for prefix command (existing logic)"""
        # Copy your existing calculatexp_prefix logic here
        # [The existing single user calculation code from your current prefix command]
        
        total_messages = 0
        eligible_messages = 0
        messages_with_timestamps = []
        processed_channels = 0
        
        # Track timing
        start_time = time.time()
        last_update_time = start_time

        progress_embed = discord.Embed(
            title="📊 Calculating XP Progress", 
            description=f"Processing {member.mention}'s message history...",
            color=discord.Color.orange()
        )
        progress_embed.add_field(name="Progress", value=f"0/{len(channels)} channels processed", inline=True)
        progress_embed.add_field(name="Messages Found", value="0", inline=True)
        progress_embed.add_field(name="Status", value="🔍 Starting scan...", inline=False)
        progress_embed.set_footer(text="⏱️ Just started...")
        
        progress_msg = await ctx.send(embed=progress_embed)

        for channel in channels:
            try:
                channel_messages = 0
                async for message in channel.history(limit=None):
                    if message.author == member:
                        total_messages += 1
                        channel_messages += 1
                        messages_with_timestamps.append(message.created_at.timestamp())
                        
                        if total_messages % 100 == 0:
                            current_time = time.time()
                            time_since_last = int(current_time - last_update_time)
                            total_elapsed = int(current_time - start_time)
                            
                            progress_embed.set_field_at(1, name="Messages Found", value=f"{total_messages:,}", inline=True)
                            progress_embed.set_field_at(2, name="Status", value=f"🔍 Scanning #{channel.name}... ({channel_messages} found)", inline=False)
                            progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                            await self.safe_edit_progress(progress_msg, embed=progress_embed)
                            last_update_time = current_time
                            
                processed_channels += 1
                current_time = time.time()
                time_since_last = int(current_time - last_update_time)
                total_elapsed = int(current_time - start_time)
                
                progress_embed.set_field_at(0, name="Progress", value=f"{processed_channels}/{len(channels)} channels processed", inline=True)
                progress_embed.set_field_at(1, name="Messages Found", value=f"{total_messages:,}", inline=True)
                
                if processed_channels < len(channels):
                    progress_embed.set_field_at(2, name="Status", value=f"✅ Completed #{channel.name} ({channel_messages} messages)", inline=False)
                else:
                    progress_embed.set_field_at(2, name="Status", value="🧮 Calculating XP based on cooldowns...", inline=False)
                
                progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                await self.safe_edit_progress(progress_msg, embed=progress_embed)
                last_update_time = current_time
                            
            except Exception as e:
                print(f"Error reading history in {channel.name}: {e}")
                continue

        if total_messages == 0:
            error_embed = discord.Embed(
                title="❌ No Messages Found",
                description=f"{member.mention} has no messages in this server.",
                color=discord.Color.red()
            )
            total_elapsed = int(time.time() - start_time)
            error_embed.set_footer(text=f"⏱️ Completed in {total_elapsed}s")
            await self.safe_edit_progress(progress_msg, embed=error_embed)
            return

        current_time = time.time()
        time_since_last = int(current_time - last_update_time)
        total_elapsed = int(current_time - start_time)
        
        progress_embed.set_field_at(2, name="Status", value="🧮 Applying 30-second cooldown rules...", inline=False)
        progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
        await self.safe_edit_progress(progress_msg, embed=progress_embed)
        last_update_time = current_time

        messages_with_timestamps.sort()
        
        last_xp_time = 0
        for i, timestamp in enumerate(messages_with_timestamps):
            if timestamp - last_xp_time >= MESSAGE_COOLDOWN_SECONDS:
                eligible_messages += 1
                last_xp_time = timestamp
                
            if i % 1000 == 0 and i > 0:
                current_time = time.time()
                time_since_last = int(current_time - last_update_time)
                total_elapsed = int(current_time - start_time)
                progress_percent = (i / len(messages_with_timestamps)) * 100
                
                progress_embed.set_field_at(2, name="Status", value=f"🧮 Processing messages... ({progress_percent:.1f}% complete)", inline=False)
                progress_embed.set_footer(text=f"⏱️ {time_since_last}s since last update • {total_elapsed}s total elapsed")
                await self.safe_edit_progress(progress_msg, embed=progress_embed)
                last_update_time = current_time

        calculated_xp = eligible_messages * XP_PER_MESSAGE
        
        guild_id_str = str(ctx.guild.id)
        user_id_str = str(member.id)
        
        guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
        user_entry = get_user_xp_entry(guild_xp_data, user_id_str)
        
        old_xp = user_entry["xp"]
        user_entry["xp"] = calculated_xp
        user_entry["last_message_timestamp"] = messages_with_timestamps[-1] if messages_with_timestamps else 0
        
        level_info = calculate_level_info(calculated_xp)
        user_entry["level"] = level_info["level"]
        
        total_elapsed = int(time.time() - start_time)
        
        embed = discord.Embed(title="✅ XP Calculation Complete", color=discord.Color.green())
        embed.add_field(name="Member", value=member.mention, inline=False)
        embed.add_field(name="Total Messages", value=f"{total_messages:,}", inline=True)
        embed.add_field(name="Eligible Messages", value=f"{eligible_messages:,} (after {MESSAGE_COOLDOWN_SECONDS}s cooldown)", inline=True)
        embed.add_field(name="Previous XP", value=f"{old_xp:,}", inline=True)
        embed.add_field(name="Calculated XP", value=f"{calculated_xp:,}", inline=True)
        embed.add_field(name="XP Difference", value=f"{calculated_xp - old_xp:+,}", inline=True)
        embed.add_field(name="New Level", value=str(level_info["level"]), inline=True)
        
        if len(channels) > 1:
            embed.set_footer(text=f"Processed {len(channels)} channels in {total_elapsed}s total.")
        else:
            embed.set_footer(text=f"Completed in {total_elapsed}s.")
        
        await self.safe_edit_progress(progress_msg, embed=progress_embed)
        await self.bot.save_immediately()

async def setup(bot):
    await bot.add_cog(LevelingCog(bot))
