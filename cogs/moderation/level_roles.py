import discord
from discord.ext import commands
from discord import app_commands
from utils.helpers import *
from utils.config import *

class LevelRolesCog(commands.Cog, name="Level Roles"):
    def __init__(self, bot):
        self.bot = bot

    # Add auto-assign role commands
    @app_commands.command(name="setautorole", description="Set a role to be automatically assigned to new members (Admin only).")
    @app_commands.describe(role="The role to automatically assign to new members")
    @app_commands.checks.has_permissions(administrator=True)
    async def setautorole_slash(self, interaction: discord.Interaction, role: discord.Role):
        guild_id_str = str(interaction.guild.id)
        
        # Check if bot can assign the role
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(f"❌ I cannot assign {role.mention} - it's higher than my highest role!", ephemeral=True)
            return
        
        # Initialize auto roles data if needed
        if not hasattr(self.bot, 'auto_roles'):
            self.bot.auto_roles = {}
        
        if guild_id_str not in self.bot.auto_roles:
            self.bot.auto_roles[guild_id_str] = []
        
        # Check if role is already in auto-assign list
        if str(role.id) in self.bot.auto_roles[guild_id_str]:
            embed = discord.Embed(
                title="Role Already Added",
                description=f"{role.mention} is already set to be auto-assigned to new members.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Add role to auto-assign list
        self.bot.auto_roles[guild_id_str].append(str(role.id))
        await self.bot.save_immediately()
        
        embed = discord.Embed(
            title="Auto Role Added",
            description=f"{role.mention} will now be automatically assigned to new members.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="removeautorole", description="Remove a role from auto-assignment (Admin only).")
    @app_commands.describe(role="The role to remove from auto-assignment")
    @app_commands.checks.has_permissions(administrator=True)
    async def removeautorole_slash(self, interaction: discord.Interaction, role: discord.Role):
        guild_id_str = str(interaction.guild.id)
        
        if not hasattr(self.bot, 'auto_roles') or guild_id_str not in self.bot.auto_roles:
            embed = discord.Embed(
                title="No Auto Roles",
                description="No auto-assign roles are configured for this server.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        role_id_str = str(role.id)
        if role_id_str not in self.bot.auto_roles[guild_id_str]:
            embed = discord.Embed(
                title="Role Not Found",
                description=f"{role.mention} is not set for auto-assignment.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Remove role from auto-assign list
        self.bot.auto_roles[guild_id_str].remove(role_id_str)
        
        # Clean up empty lists
        if not self.bot.auto_roles[guild_id_str]:
            del self.bot.auto_roles[guild_id_str]
        
        await self.bot.save_immediately()
        
        embed = discord.Embed(
            title="Auto Role Removed",
            description=f"{role.mention} will no longer be automatically assigned to new members.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="autoroles", description="View all auto-assign roles for this server.")
    async def autoroles_slash(self, interaction: discord.Interaction):
        guild_id_str = str(interaction.guild.id)
        
        if not hasattr(self.bot, 'auto_roles') or guild_id_str not in self.bot.auto_roles or not self.bot.auto_roles[guild_id_str]:
            embed = discord.Embed(
                title="No Auto Roles",
                description="No roles are set to be automatically assigned to new members.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"Auto-Assign Roles for {interaction.guild.name}",
            color=discord.Color.purple()
        )
        
        role_mentions = []
        for role_id in self.bot.auto_roles[guild_id_str]:
            role = interaction.guild.get_role(int(role_id))
            if role:
                role_mentions.append(role.mention)
            else:
                role_mentions.append(f"<@&{role_id}> *(role deleted)*")
        
        embed.description = "\n".join([f"• {role}" for role in role_mentions])
        embed.set_footer(text="These roles will be assigned to all new members automatically.")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setlevelrole", description="Set a role to be assigned at a specific level (Admin only).")
    @app_commands.describe(
        level="The level required to get this role",
        role="The role to assign at this level"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setlevelrole_slash(self, interaction: discord.Interaction, level: int, role: discord.Role):
        if level < 1:
            await interaction.response.send_message("Level must be 1 or higher.", ephemeral=True)
            return
        
        if level > 200:
            await interaction.response.send_message("Level must be 200 or lower.", ephemeral=True)
            return
        
        guild_id_str = str(interaction.guild.id)
        guild_level_roles = get_guild_level_roles(self.bot.level_roles, guild_id_str)
        
        # Check if role is already assigned to another level
        existing_level = None
        for lvl, role_id in guild_level_roles.items():
            if int(role_id) == role.id:
                existing_level = int(lvl)
                break
        
        if existing_level:
            embed = discord.Embed(
                title="Role Already Assigned",
                description=f"{role.mention} is already assigned to level {existing_level}. Remove it first if you want to reassign it.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        guild_level_roles[str(level)] = str(role.id)
        
        embed = discord.Embed(
            title="Level Role Set",
            description=f"{role.mention} will now be assigned to users who reach **Level {level}**.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
        await self.bot.save_immediately()

    @app_commands.command(name="removelevelrole", description="Remove a role assignment from a specific level (Admin only).")
    @app_commands.describe(level="The level to remove the role assignment from")
    @app_commands.checks.has_permissions(administrator=True)
    async def removelevelrole_slash(self, interaction: discord.Interaction, level: int):
        guild_id_str = str(interaction.guild.id)
        guild_level_roles = get_guild_level_roles(self.bot.level_roles, guild_id_str)
        
        level_str = str(level)
        if level_str not in guild_level_roles:
            embed = discord.Embed(
                title="No Role Assignment",
                description=f"No role is assigned to level {level}.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        role_id = guild_level_roles[level_str]
        role = interaction.guild.get_role(int(role_id))
        role_mention = role.mention if role else f"<@&{role_id}> (deleted role)"
        
        del guild_level_roles[level_str]
        
        embed = discord.Embed(
            title="Level Role Removed",
            description=f"Removed {role_mention} from level {level}.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
        await self.bot.save_immediately()

    @app_commands.command(name="levelroles", description="View all level role assignments for this server.")
    async def levelroles_slash(self, interaction: discord.Interaction):
        guild_id_str = str(interaction.guild.id)
        guild_level_roles = get_guild_level_roles(self.bot.level_roles, guild_id_str)
        
        if not guild_level_roles:
            embed = discord.Embed(
                title="No Level Roles",
                description="No roles have been assigned to levels in this server.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"Level Roles for {interaction.guild.name}",
            color=discord.Color.purple()
        )
        
        # Sort by level
        sorted_roles = sorted(guild_level_roles.items(), key=lambda x: int(x[0]))
        
        description_lines = []
        for level_str, role_id in sorted_roles:
            role = interaction.guild.get_role(int(role_id))
            if role:
                description_lines.append(f"**Level {level_str}:** {role.mention}")
            else:
                description_lines.append(f"**Level {level_str}:** <@&{role_id}> *(role deleted)*")
        
        embed.description = "\n".join(description_lines)
        embed.set_footer(text="Use /setlevelrole to add new assignments or /removelevelrole to remove them.")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="syncuserroles", description="Sync a user's roles based on their current level (Admin only).")
    @app_commands.describe(member="The member to sync roles for (defaults to everyone if not specified)")
    @app_commands.checks.has_permissions(administrator=True)
    async def syncuserroles_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        
        guild_id_str = str(interaction.guild.id)
        guild_level_roles = get_guild_level_roles(self.bot.level_roles, guild_id_str)
        
        if not guild_level_roles:
            embed = discord.Embed(
                title="No Level Roles",
                description="No level roles are configured for this server.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return
        
        if member:
            # Sync specific member
            if member.bot:
                await interaction.followup.send("Cannot sync roles for bots.", ephemeral=True)
                return
            
            user_id_str = str(member.id)
            guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
            user_entry = get_user_xp_entry(guild_xp_data, user_id_str)
            level_info = calculate_level_info(user_entry["xp"])
            
            await assign_level_roles(member, level_info["level"], self.bot)
            
            embed = discord.Embed(
                title="Roles Synced",
                description=f"Synced level roles for {member.mention} (Level {level_info['level']}).",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        else:
            # Sync all members
            guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
            synced_count = 0
            
            for user_id_str, user_data in guild_xp_data.items():
                member_obj = interaction.guild.get_member(int(user_id_str))
                if member_obj and not member_obj.bot:
                    level_info = calculate_level_info(user_data.get("xp", 0))
                    await assign_level_roles(member_obj, level_info["level"], self.bot)
                    synced_count += 1
            
            embed = discord.Embed(
                title="Roles Synced",
                description=f"Synced level roles for {synced_count} members.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)

    # Prefix command versions
    # Prefix command versions
    @commands.command(name="setautorole", aliases=["autorole", "addrole"])
    @commands.has_permissions(administrator=True)
    async def setautorole_prefix(self, ctx: commands.Context, role: discord.Role = None):
        """Set a role to be automatically assigned to new members (Admin only)."""
        if role is None:
            await ctx.send("Usage: `!setautorole <@role>`")
            return
        
        guild_id_str = str(ctx.guild.id)
        
        # Check if bot can assign the role
        if role >= ctx.guild.me.top_role:
            await ctx.send(f"❌ I cannot assign {role.mention} - it's higher than my highest role!")
            return
        
        # Initialize auto roles data if needed
        if not hasattr(self.bot, 'auto_roles'):
            self.bot.auto_roles = {}
        
        if guild_id_str not in self.bot.auto_roles:
            self.bot.auto_roles[guild_id_str] = []
        
        # Check if role is already in auto-assign list
        if str(role.id) in self.bot.auto_roles[guild_id_str]:
            embed = discord.Embed(
                title="Role Already Added",
                description=f"{role.mention} is already set to be auto-assigned to new members.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        # Add role to auto-assign list
        self.bot.auto_roles[guild_id_str].append(str(role.id))
        await self.bot.save_immediately()
        
        embed = discord.Embed(
            title="Auto Role Added",
            description=f"{role.mention} will now be automatically assigned to new members.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="removeautorole", aliases=["delautorole", "removerole"])
    @commands.has_permissions(administrator=True)
    async def removeautorole_prefix(self, ctx: commands.Context, role: discord.Role = None):
        """Remove a role from auto-assignment (Admin only)."""
        if role is None:
            await ctx.send("Usage: `!removeautorole <@role>`")
            return
        
        guild_id_str = str(ctx.guild.id)
        
        if not hasattr(self.bot, 'auto_roles') or guild_id_str not in self.bot.auto_roles:
            embed = discord.Embed(
                title="No Auto Roles",
                description="No auto-assign roles are configured for this server.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        role_id_str = str(role.id)
        if role_id_str not in self.bot.auto_roles[guild_id_str]:
            embed = discord.Embed(
                title="Role Not Found",
                description=f"{role.mention} is not set for auto-assignment.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        # Remove role from auto-assign list
        self.bot.auto_roles[guild_id_str].remove(role_id_str)
        
        # Clean up empty lists
        if not self.bot.auto_roles[guild_id_str]:
            del self.bot.auto_roles[guild_id_str]
        
        await self.bot.save_immediately()
        
        embed = discord.Embed(
            title="Auto Role Removed",
            description=f"{role.mention} will no longer be automatically assigned to new members.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="autoroles", aliases=["listautoroles", "showautoroles"])
    async def autoroles_prefix(self, ctx: commands.Context):
        """View all auto-assign roles for this server."""
        guild_id_str = str(ctx.guild.id)
        
        if not hasattr(self.bot, 'auto_roles') or guild_id_str not in self.bot.auto_roles or not self.bot.auto_roles[guild_id_str]:
            embed = discord.Embed(
                title="No Auto Roles",
                description="No roles are set to be automatically assigned to new members.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"Auto-Assign Roles for {ctx.guild.name}",
            color=discord.Color.purple()
        )
        
        role_mentions = []
        for role_id in self.bot.auto_roles[guild_id_str]:
            role = ctx.guild.get_role(int(role_id))
            if role:
                role_mentions.append(role.mention)
            else:
                role_mentions.append(f"<@&{role_id}> *(role deleted)*")
        
        embed.description = "\n".join([f"• {role}" for role in role_mentions])
        embed.set_footer(text=f"These roles will be assigned to all new members automatically. Use {COMMAND_PREFIX}setautorole to add more.")
        
        await ctx.send(embed=embed)

    @commands.command(name="setlevelrole", aliases=["setlvlrole", "levelrole", "lvlrole"])
    @commands.has_permissions(administrator=True)
    async def setlevelrole_prefix(self, ctx: commands.Context, level: int = None, role: discord.Role = None):
        """Set a role to be assigned at a specific level (Admin only)."""
        if level is None or role is None:
            await ctx.send("Usage: `!setlevelrole <level> <@role>`")
            return
        
        if level < 1:
            await ctx.send("Level must be 1 or higher.")
            return
        
        if level > 200:
            await ctx.send("Level must be 200 or lower.")
            return
        
        guild_id_str = str(ctx.guild.id)
        guild_level_roles = get_guild_level_roles(self.bot.level_roles, guild_id_str)
        
        # Check if role is already assigned to another level
        existing_level = None
        for lvl, role_id in guild_level_roles.items():
            if int(role_id) == role.id:
                existing_level = int(lvl)
                break
        
        if existing_level:
            embed = discord.Embed(
                title="Role Already Assigned",
                description=f"{role.mention} is already assigned to level {existing_level}. Remove it first if you want to reassign it.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        guild_level_roles[str(level)] = str(role.id)
        
        embed = discord.Embed(
            title="Level Role Set",
            description=f"{role.mention} will now be assigned to users who reach **Level {level}**.",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
        await self.bot.save_immediately()

    @commands.command(name="removelevelrole", aliases=["removelvlrole", "dellevelrole", "deletelevelrole"])
    @commands.has_permissions(administrator=True)
    async def removelevelrole_prefix(self, ctx: commands.Context, level: int = None):
        """Remove a role assignment from a specific level (Admin only)."""
        if level is None:
            await ctx.send("Usage: `!removelevelrole <level>`")
            return
        
        guild_id_str = str(ctx.guild.id)
        guild_level_roles = get_guild_level_roles(self.bot.level_roles, guild_id_str)
        
        level_str = str(level)
        if level_str not in guild_level_roles:
            embed = discord.Embed(
                title="No Role Assignment",
                description=f"No role is assigned to level {level}.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        role_id = guild_level_roles[level_str]
        role = ctx.guild.get_role(int(role_id))
        role_mention = role.mention if role else f"<@&{role_id}> (deleted role)"
        
        del guild_level_roles[level_str]
        
        embed = discord.Embed(
            title="Level Role Removed",
            description=f"Removed {role_mention} from level {level}.",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
        await self.bot.save_immediately()

    @commands.command(name="levelroles", aliases=["lvlroles", "listroles", "showroles"])
    async def levelroles_prefix(self, ctx: commands.Context):
        """View all level role assignments for this server."""
        guild_id_str = str(ctx.guild.id)
        guild_level_roles = get_guild_level_roles(self.bot.level_roles, guild_id_str)
        
        if not guild_level_roles:
            embed = discord.Embed(
                title="No Level Roles",
                description="No roles have been assigned to levels in this server.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"Level Roles for {ctx.guild.name}",
            color=discord.Color.purple()
        )
        
        # Sort by level
        sorted_roles = sorted(guild_level_roles.items(), key=lambda x: int(x[0]))
        
        description_lines = []
        for level_str, role_id in sorted_roles:
            role = ctx.guild.get_role(int(role_id))
            if role:
                description_lines.append(f"**Level {level_str}:** {role.mention}")
            else:
                description_lines.append(f"**Level {level_str}:** <@&{role_id}> *(role deleted)*")
        
        embed.description = "\n".join(description_lines)
        embed.set_footer(text=f"Use {COMMAND_PREFIX}setlevelrole to add new assignments.")
        
        await ctx.send(embed=embed)

    @commands.command(name="syncuserroles", aliases=["syncroles", "syncmember", "fixroles"])
    @commands.has_permissions(administrator=True)
    async def syncuserroles_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Sync a user's roles based on their current level (Admin only)."""
        guild_id_str = str(ctx.guild.id)
        guild_level_roles = get_guild_level_roles(self.bot.level_roles, guild_id_str)
        
        if not guild_level_roles:
            embed = discord.Embed(
                title="No Level Roles",
                description="No level roles are configured for this server.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        
        if member:
            # Sync specific member
            if member.bot:
                await ctx.send("Cannot sync roles for bots.")
                return
            
            user_id_str = str(member.id)
            guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
            user_entry = get_user_xp_entry(guild_xp_data, user_id_str)
            level_info = calculate_level_info(user_entry["xp"])
            
            await assign_level_roles(member, level_info["level"], self.bot)
            
            embed = discord.Embed(
                title="Roles Synced",
                description=f"Synced level roles for {member.mention} (Level {level_info['level']}).",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            # Sync all members
            guild_xp_data = get_guild_xp_data(self.bot.xp_data, guild_id_str)
            synced_count = 0
            
            progress_msg = await ctx.send("Syncing roles for all members...")
            
            for user_id_str, user_data in guild_xp_data.items():
                member_obj = ctx.guild.get_member(int(user_id_str))
                if member_obj and not member_obj.bot:
                    level_info = calculate_level_info(user_data.get("xp", 0))
                    await assign_level_roles(member_obj, level_info["level"], self.bot)
                    synced_count += 1
            
            embed = discord.Embed(
                title="Roles Synced",
                description=f"Synced level roles for {synced_count} members.",
                color=discord.Color.green()
            )
            await progress_msg.edit(content=None, embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Automatically assign auto-roles when a new member joins"""
        try:
            # Don't assign roles to bots
            if member.bot:
                return
                
            guild_id_str = str(member.guild.id)
            
            # Check if there are any auto-roles configured for this guild
            if not hasattr(self.bot, 'auto_roles') or guild_id_str not in self.bot.auto_roles:
                return
            
            if not self.bot.auto_roles[guild_id_str]:
                return
            
            # Get all auto-roles for this guild
            roles_to_assign = []
            for role_id_str in self.bot.auto_roles[guild_id_str]:
                role = member.guild.get_role(int(role_id_str))
                if role and role < member.guild.me.top_role:  # Make sure bot can assign the role
                    roles_to_assign.append(role)
            
            # Assign roles if any are found
            if roles_to_assign:
                await member.add_roles(*roles_to_assign, reason="Auto-role assignment for new member")
                print(f"✅ Auto-assigned {len(roles_to_assign)} role(s) to {member.display_name}: {[role.name for role in roles_to_assign]}")
            else:
                print(f"⚠️ No valid auto-roles found to assign to {member.display_name}")
                
        except Exception as e:
            print(f"❌ Error auto-assigning roles to {member.display_name}: {e}")

async def setup(bot):
    await bot.add_cog(LevelRolesCog(bot))