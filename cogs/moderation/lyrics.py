"""
Lyrics System - Allows Izumi to continue song lyrics
"""

import discord
from discord.ext import commands
from discord import app_commands
from difflib import SequenceMatcher
from utils.helpers import load_json, save_json
import re

class LyricsCog(commands.Cog, name="Lyrics"):
    def __init__(self, bot):
        self.bot = bot
        self.lyrics_database = self._load_lyrics()
        
    def _load_lyrics(self):
        """Load lyrics database"""
        try:
            return load_json('data/lyrics_database.json')
        except:
            return {"songs": []}
    
    def _save_lyrics(self):
        """Save lyrics database"""
        save_json('data/lyrics_database.json', self.lyrics_database)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (lowercase, remove punctuation)"""
        text = text.lower()
        # Remove punctuation except apostrophes
        text = re.sub(r"[^\w\s']", '', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text
    
    def _similarity_score(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0-1)"""
        return SequenceMatcher(None, str1, str2).ratio()
    
    def find_matching_lyric(self, user_message: str):
        """Find if user message matches any song lyrics"""
        normalized_message = self._normalize_text(user_message)
        
        # Minimum message length to consider as lyrics (avoid false positives)
        if len(normalized_message.split()) < 3:
            return None
        
        best_match = None
        best_score = 0
        best_line_index = -1
        
        for song in self.lyrics_database.get('songs', []):
            lyrics = song.get('lyrics', [])
            
            for i, line in enumerate(lyrics):
                normalized_line = self._normalize_text(line)
                
                # Check for exact match or high similarity
                if normalized_message in normalized_line or normalized_line in normalized_message:
                    score = self._similarity_score(normalized_message, normalized_line)
                    
                    if score > best_score and score >= 0.7:  # At least 70% similarity
                        best_score = score
                        best_match = song
                        best_line_index = i
        
        if best_match and best_line_index >= 0:
            lyrics = best_match['lyrics']
            # Get next line if available
            if best_line_index + 1 < len(lyrics):
                next_line = lyrics[best_line_index + 1]
                return {
                    'song': best_match['title'],
                    'artist': best_match['artist'],
                    'current_line': lyrics[best_line_index],
                    'next_line': next_line,
                    'confidence': best_score
                }
        
        return None
    
    @commands.command(name="addsong", aliases=["addlyrics", "newsong"])
    @commands.has_permissions(administrator=True)
    async def add_song_prefix(self, ctx: commands.Context, artist: str, title: str, *, lyrics: str):
        """Add a song to the lyrics database - Usage: !addsong "Artist Name" "Song Title" [paste lyrics here]"""
        
        # Split lyrics by newlines
        lyric_lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
        
        if len(lyric_lines) < 2:
            await ctx.send(
                "❌ Please provide at least 2 lines of lyrics!\n"
                "**Usage:** `!addsong \"Artist\" \"Song Title\" [paste full lyrics]`\n"
                "**Example:**\n```\n!addsong \"Yael Naim\" \"New Soul\"\n"
                "I'm a new soul, I came to this strange world\n"
                "Hoping I could learn a bit 'bout how to give and take\n"
                "But since I came here, felt the joy and the fear\n```"
            )
            return
        
        # Check if song already exists
        for song in self.lyrics_database.get('songs', []):
            if song['title'].lower() == title.lower() and song['artist'].lower() == artist.lower():
                await ctx.send(f"❌ Song **{title}** by **{artist}** already exists in the database!")
                return
        
        # Add new song
        new_song = {
            "title": title,
            "artist": artist,
            "lyrics": lyric_lines
        }
        
        if 'songs' not in self.lyrics_database:
            self.lyrics_database['songs'] = []
        
        self.lyrics_database['songs'].append(new_song)
        self._save_lyrics()
        
        embed = discord.Embed(
            title="✅ Song Added to Database",
            description=f"**{title}** by **{artist}**",
            color=discord.Color.green()
        )
        embed.add_field(name="📝 Total Lines", value=str(len(lyric_lines)), inline=True)
        embed.add_field(name="🎵 Preview", value=f"*{lyric_lines[0][:100]}...*", inline=False)
        
        if len(lyric_lines) > 1:
            embed.add_field(name="Next Line", value=f"*{lyric_lines[1][:100]}...*", inline=False)
        
        embed.set_footer(text="Izumi can now continue this song when people sing it!")
        
        await ctx.send(embed=embed)
    
    @app_commands.command(name="addsong", description="Add a song to the lyrics database (Admin only)")
    @app_commands.describe(
        title="Song title",
        artist="Artist name",
        lyrics="Song lyrics (paste each line separated by newlines)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def add_song(self, interaction: discord.Interaction, title: str, artist: str, lyrics: str):
        """Add a new song to the lyrics database (slash command version)"""
        
        # Split lyrics by newlines
        lyric_lines = [line.strip() for line in lyrics.split('\n') if line.strip()]
        
        if len(lyric_lines) < 2:
            await interaction.response.send_message(
                "❌ Please provide at least 2 lines of lyrics separated by newlines\n"
                "**Tip:** Use the prefix command `!addsong` for easier pasting of multi-line lyrics!",
                ephemeral=True
            )
            return
        
        # Check if song already exists
        for song in self.lyrics_database.get('songs', []):
            if song['title'].lower() == title.lower() and song['artist'].lower() == artist.lower():
                await interaction.response.send_message(
                    f"❌ Song **{title}** by **{artist}** already exists in the database!",
                    ephemeral=True
                )
                return
        
        # Add new song
        new_song = {
            "title": title,
            "artist": artist,
            "lyrics": lyric_lines
        }
        
        if 'songs' not in self.lyrics_database:
            self.lyrics_database['songs'] = []
        
        self.lyrics_database['songs'].append(new_song)
        self._save_lyrics()
        
        embed = discord.Embed(
            title="✅ Song Added",
            description=f"Added **{title}** by **{artist}** to the lyrics database!",
            color=discord.Color.green()
        )
        embed.add_field(name="Lines Added", value=str(len(lyric_lines)), inline=True)
        embed.add_field(name="Preview", value=lyric_lines[0][:100], inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="removesong", description="Remove a song from the lyrics database (Admin only)")
    @app_commands.describe(
        title="Song title to remove",
        artist="Artist name (optional, for disambiguation)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_song(self, interaction: discord.Interaction, title: str, artist: str = None):
        """Remove a song from the lyrics database"""
        
        songs = self.lyrics_database.get('songs', [])
        found_songs = []
        
        # Find matching songs
        for i, song in enumerate(songs):
            title_match = song['title'].lower() == title.lower()
            artist_match = artist is None or song['artist'].lower() == artist.lower()
            
            if title_match and artist_match:
                found_songs.append((i, song))
        
        if not found_songs:
            await interaction.response.send_message(
                f"❌ No song found matching **{title}**" + (f" by **{artist}**" if artist else ""),
                ephemeral=True
            )
            return
        
        if len(found_songs) > 1 and artist is None:
            song_list = "\n".join([f"• {s['title']} by {s['artist']}" for _, s in found_songs])
            await interaction.response.send_message(
                f"❌ Multiple songs found with title **{title}**:\n{song_list}\n\nPlease specify the artist.",
                ephemeral=True
            )
            return
        
        # Remove the song
        index, removed_song = found_songs[0]
        self.lyrics_database['songs'].pop(index)
        self._save_lyrics()
        
        embed = discord.Embed(
            title="✅ Song Removed",
            description=f"Removed **{removed_song['title']}** by **{removed_song['artist']}** from the database.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="listsongs", description="List all songs in the lyrics database")
    async def list_songs(self, interaction: discord.Interaction):
        """List all songs in the database"""
        
        songs = self.lyrics_database.get('songs', [])
        
        if not songs:
            await interaction.response.send_message("❌ No songs in the database yet!", ephemeral=True)
            return
        
        # Create paginated list
        songs_per_page = 10
        total_pages = (len(songs) + songs_per_page - 1) // songs_per_page
        
        embed = discord.Embed(
            title="🎵 Lyrics Database",
            description=f"Total songs: **{len(songs)}**",
            color=discord.Color.blue()
        )
        
        # Show first page
        page_songs = songs[:songs_per_page]
        song_list = "\n".join([f"{i+1}. **{s['title']}** - {s['artist']} ({len(s['lyrics'])} lines)" 
                               for i, s in enumerate(page_songs)])
        
        embed.add_field(name=f"Songs (Page 1/{total_pages})", value=song_list, inline=False)
        
        if total_pages > 1:
            embed.set_footer(text=f"Showing 1-{len(page_songs)} of {len(songs)} songs")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="searchsong", description="Search for a song in the database")
    @app_commands.describe(query="Song title or artist to search for")
    async def search_song(self, interaction: discord.Interaction, query: str):
        """Search for songs in the database"""
        
        query_lower = query.lower()
        matching_songs = []
        
        for song in self.lyrics_database.get('songs', []):
            if query_lower in song['title'].lower() or query_lower in song['artist'].lower():
                matching_songs.append(song)
        
        if not matching_songs:
            await interaction.response.send_message(
                f"❌ No songs found matching: **{query}**",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"🔍 Search Results for \"{query}\"",
            description=f"Found **{len(matching_songs)}** song(s)",
            color=discord.Color.blue()
        )
        
        for song in matching_songs[:5]:  # Show first 5 results
            preview = song['lyrics'][0] if song['lyrics'] else "No lyrics"
            embed.add_field(
                name=f"🎵 {song['title']} - {song['artist']}",
                value=f"*{preview[:100]}...*\n({len(song['lyrics'])} lines)",
                inline=False
            )
        
        if len(matching_songs) > 5:
            embed.set_footer(text=f"Showing 5 of {len(matching_songs)} results")
        
        await interaction.response.send_message(embed=embed)
    
    @commands.command(name="lyricshelp", aliases=["songhelp"])
    async def lyrics_help(self, ctx: commands.Context):
        """Show how to use the lyrics system"""
        embed = discord.Embed(
            title="🎵 Lyrics System Guide",
            description="Teach Izumi songs so she can continue them when people sing!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📝 Adding Songs (Easy Method)",
            value=(
                "```\n"
                "!addsong \"Artist\" \"Song Title\"\n"
                "[paste full lyrics here]\n"
                "```\n"
                "**Example:**\n"
                "```\n"
                "!addsong \"Rick Astley\" \"Never Gonna Give You Up\"\n"
                "Never gonna give you up\n"
                "Never gonna let you down\n"
                "Never gonna run around and desert you\n"
                "```"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎤 How It Works",
            value=(
                "Once a song is added:\n"
                "• Users sing a line from the song\n"
                "• Izumi detects it (70% match accuracy)\n"
                "• She continues with the next line naturally!\n"
                "• Sometimes adds fun comments about the song"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 Other Commands",
            value=(
                "`!listsongs` - View all songs\n"
                "`/searchsong [query]` - Find a song\n"
                "`/removesong [title]` - Remove a song\n"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: Just copy-paste lyrics from any lyrics site!")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LyricsCog(bot))
