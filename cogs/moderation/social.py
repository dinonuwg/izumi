import discord
from discord.ext import commands
from discord import app_commands
import random
import aiohttp
from utils.config import *

class SocialCog(commands.Cog, name="Social"):
    def __init__(self, bot):
        self.bot = bot

    async def get_anime_gif(self, action: str):
        """Get an anime GIF for the specified action using Tenor API"""
        # You can get a free API key from https://developers.google.com/tenor/guides/quickstart
        # For now, we'll use some fallback GIFs
        fallback_gifs = {
            "kiss": [
                "https://media.discordapp.net/attachments/1348703706295832728/1379165760676430018/image0.gif?ex=683f3fb5&is=683dee35&hm=894cc1330cbb8280f2466a0cc3c7c284ea0207f80b9f77ce47419e38fdb2aa8a&=",
                "https://i.redd.it/ktcpp3apkx5d1.gif",
                "https://i.redd.it/6dp9vhfb57nc1.gif",
                "https://media.discordapp.net/attachments/1348703706295832728/1379169949079310500/image0.gif?ex=683f439b&is=683df21b&hm=33d557dcd2553d36f467545df901f31ea1b08fdb7048a01c1c1ed7f4f8da82e5&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379169949490348176/image1.gif?ex=683f439b&is=683df21b&hm=61a89862fc2281ab6da9470dd52e458af5122bbea0390b8161d30137ca2f3726&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379169951100698826/image2.gif?ex=683f439c&is=683df21c&hm=c235afc0a305ef9cb21f292058f12df6e0604c590eade5c622d56df919cc03da&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379169951721459783/image3.gif?ex=683f439c&is=683df21c&hm=19d2ec51aa03fdc6f6ccb25c7a761c6a0b82c55b5372a148a93eb6577d54c173&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379169952006668388/image4.gif?ex=683f439c&is=683df21c&hm=324681e8cbc43baf38ac9e4719f6a8a6d029eee8cafce91763e04144dc0c8acc&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379169952413646848/image5.gif?ex=683f439c&is=683df21c&hm=0cde4c2c212041ca0ee2b32c008dd281129197150423173fa8356a232d50a9c0&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379170132877901927/image0.gif?ex=683f43c7&is=683df247&hm=37509b30714e9bda65e37943c6fb7348cda6134361e55b42695fb346d961067b&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379170133322235954/image1.gif?ex=683f43c7&is=683df247&hm=e48008a77b84aea94be47c81906469bd24c5bc2020dca5eba4e6434aa9a09850&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379170188368281743/image0.gif?ex=683f43d4&is=683df254&hm=4d5edbfb1f83947e97789284d357ff86fe76f989f5e52b9346dd213fa969ea5f&=",
            ],
            "hug": [
                "https://media.discordapp.net/attachments/1348703706295832728/1379165876447739924/image0.gif?ex=683f3fd0&is=683dee50&hm=bcbab43507ecaee178cca2c856ba10f5038ec2698f5ddec1f6f9e311bfa772ea&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379165896655769782/image0.gif?ex=683f3fd5&is=683dee55&hm=1ea61b781cb5ba273da64004292fd94f9d26dc180ee498bc87437db739c475b3&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379171294548852937/image0.gif?ex=683f44dc&is=683df35c&hm=7f228f58269441208b772c881ffdcbe99e66818a05b831638ac18033836fd133&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379171295442374676/image1.gif?ex=683f44dc&is=683df35c&hm=a3a2090823cf0209ba573b133bd0e1d61f4324907d41749230a335b7a2cb2b5e&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379171295782109384/image2.gif?ex=683f44dc&is=683df35c&hm=517f83d687f08b7dabb7a676b96fe5fb6b4578962e381d052bbcaa86cc7408a5&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379171296151076985/image3.gif?ex=683f44dc&is=683df35c&hm=5560f471a0c0a6cc665add7c1b1231876ec2956c53518d82a9d40504890d82cb&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379171296474042481/image4.gif?ex=683f44dc&is=683df35c&hm=b12f47257da6cec06d6e4ad5cda50481f99772f5b8457ab8428bf5c29e63615e&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379171296784683038/image5.gif?ex=683f44dc&is=683df35c&hm=b219d04890df53ee06d56f14c357dadd8205edade9569cdfc901f6af8da21085&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379171302916624495/image6.gif?ex=683f44de&is=683df35e&hm=7a981fc355da093ec65a3200d75cfd072f23dd20f5c73a2d3db3e081d2158764&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379171303344439366/image7.gif?ex=683f44de&is=683df35e&hm=300e5a1d77cfba1be96e06f08d5f923c1d47cd2531bdf94103787d1f38ebbc20&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379171303701086218/image8.gif?ex=683f44de&is=683df35e&hm=40a42c08d455df00fd1adfa6fb679db2d138eedaf97696f91b638a653922edb2&=",
            
            ],
            "slap": [
                "https://media.discordapp.net/attachments/1348703706295832728/1379167801146867802/image0.gif?ex=683f419b&is=683df01b&hm=44cd113b6f07f24913bee666d3c50d2c78227204cd9b985ef84a56ee7ca6b64f&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379167821057097968/image0.gif?ex=683f41a0&is=683df020&hm=14aaf611d2b207c1fe99371cdead58222251526a44a2afaee754860aa3c46217&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379167859665666168/image0.gif?ex=683f41a9&is=683df029&hm=5473b197e79de0ea49da34275741987ee9334505b01c5639df6c4c2bdba3fcb5&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379167961348313098/image0.gif?ex=683f41c1&is=683df041&hm=9f80eebab75c3e43bc84a2797cf415a29fde1e3530f1dcdad6706f215da45b63&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379168193616023643/image6.gif?ex=683f41f9&is=683df079&hm=bdc618a1d02c3569d2de3b8430ae2e62f74ce94ebbe6d13d0dbd20d04de445c4&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379168190223093830/image1.gif?ex=683f41f8&is=683df078&hm=3a2a11953af7766f230d91a391c84c45aeff62c9068c03a1b8c56ca44a4185d7&="
            ],
            "handhold": [
                "https://media.discordapp.net/attachments/1348703706295832728/1379172021925056552/image0.gif?ex=683f4589&is=683df409&hm=1d6b11fbc197e23561a7cbe11d9a349150b2091eaf1f12143b6494caeb9f1988&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379172022269120512/image1.gif?ex=683f4589&is=683df409&hm=3d897516a4f80a684344c5122eca87c573527f318c9c7fb28c4273091fb5dcb1&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379172022629699584/image2.gif?ex=683f4589&is=683df409&hm=3a6a58b0ca121408204f4b47363d26ba9e69aa24105ff0785d88dbeb0551cb8b&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379172023040737371/image3.gif?ex=683f458a&is=683df40a&hm=da2781ce3b919e7ba55d6a4ebede7590aa15e75a216bccc3549a3538f011df4e&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379172023732797491/image5.gif?ex=683f458a&is=683df40a&hm=fa8b72550c82c07a6f1d185d9f308963c614bc503723c31be1ef5181319e02de&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379172024043180112/image6.gif?ex=683f458a&is=683df40a&hm=23e05dfef638ee5989091a8d6f57b61be6b57f2bae781e24761a43e53632b51c&=",
                "https://media.discordapp.net/attachments/1348703706295832728/1379172024370462720/image7.gif?ex=683f458a&is=683df40a&hm=41ca157e8cc234074115c86c43adce886fb5366552ad0d357ffcb6d10ddf5fbb&="
            ]
        }
        
        return random.choice(fallback_gifs.get(action, fallback_gifs["hug"]))

    @app_commands.command(name="kiss", description="Kiss someone! 💋")
    @app_commands.describe(member="The person to kiss")
    async def kiss_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.bot:
            await interaction.response.send_message("You can't kiss bots! 🤖", ephemeral=True)
            return
        
        if member == interaction.user:
            await interaction.response.send_message("You can't kiss yourself! Try finding someone else 😅", ephemeral=True)
            return
        
        gif_url = await self.get_anime_gif("kiss")
        
        embed = discord.Embed(
            description=f"💋 **{interaction.user.mention} kissed {member.mention}!** 💋",
            color=discord.Color.pink()
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text="Aww, how sweet! 💕")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hug", description="Give someone a warm hug! 🤗")
    @app_commands.describe(member="The person to hug")
    async def hug_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.bot:
            await interaction.response.send_message("Bots don't need hugs! 🤖", ephemeral=True)
            return
        
        if member == interaction.user:
            embed = discord.Embed(
                description=f"🤗 **{interaction.user.mention} hugged themselves!** 🤗",
                color=discord.Color.green()
            )
            embed.set_image(url=await self.get_anime_gif("hug"))
            embed.set_footer(text="Sometimes we all need self-love! 💚")
        else:
            embed = discord.Embed(
                description=f"🤗 **{interaction.user.mention} hugged {member.mention}!** 🤗",
                color=discord.Color.green()
            )
            embed.set_image(url=await self.get_anime_gif("hug"))
            embed.set_footer(text="So wholesome! 💚")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="slap", description="Slap someone! ✋")
    @app_commands.describe(member="The person to slap")
    async def slap_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.bot:
            await interaction.response.send_message("You can't slap bots! They're made of metal! 🤖", ephemeral=True)
            return
        
        if member == interaction.user:
            await interaction.response.send_message("Why would you slap yourself? That's just... sad 😅", ephemeral=True)
            return
        
        gif_url = await self.get_anime_gif("slap")
        
        embed = discord.Embed(
            description=f"✋ **{interaction.user.mention} slapped {member.mention}!** ✋",
            color=discord.Color.red()
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text="Ouch! That's gotta hurt! 😵")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sex", description="Hold hands with someone! 😳👫")
    @app_commands.describe(member="The person to hold hands with")
    async def sex_slash(self, interaction: discord.Interaction, member: discord.Member):
        if member.bot:
            await interaction.response.send_message("Bots don't have hands to hold! 🤖", ephemeral=True)
            return
        
        if member == interaction.user:
            await interaction.response.send_message("You can't hold your own hand... that's just sad 😅", ephemeral=True)
            return
        
        gif_url = await self.get_anime_gif("handhold")
        
        embed = discord.Embed(
            description=f"😳 **{interaction.user.mention} is holding hands with {member.mention}!** 👫",
            color=discord.Color.from_rgb(255, 182, 193)  # Light pink
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text="How lewd! 😳💕")
        
        await interaction.response.send_message(embed=embed)

    # Prefix command versions
    @commands.command(name="kiss", aliases=["smooch", "💋"])
    async def kiss_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Kiss someone! 💋"""
        if member is None:
            await ctx.send(f"You need to mention someone to kiss! Usage: `{COMMAND_PREFIX}kiss @user`")
            return
        
        if member.bot:
            await ctx.send("You can't kiss bots! 🤖")
            return
        
        if member == ctx.author:
            await ctx.send("You can't kiss yourself! Try finding someone else 😅")
            return
        
        gif_url = await self.get_anime_gif("kiss")
        
        embed = discord.Embed(
            description=f"💋 **{ctx.author.mention} kissed {member.mention}!** 💋",
            color=discord.Color.pink()
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text="Aww, how sweet! 💕")
        
        await ctx.send(embed=embed)

    @commands.command(name="hug", aliases=["cuddle", "embrace", "🤗", "warm"])
    async def hug_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Give someone a warm hug! 🤗"""
        if member is None:
            await ctx.send(f"You need to mention someone to hug! Usage: `{COMMAND_PREFIX}hug @user`")
            return
        
        if member.bot:
            await ctx.send("Bots don't need hugs! 🤖")
            return
        
        if member == ctx.author:
            embed = discord.Embed(
                description=f"🤗 **{ctx.author.mention} hugged themselves!** 🤗",
                color=discord.Color.green()
            )
            embed.set_image(url=await self.get_anime_gif("hug"))
            embed.set_footer(text="Sometimes we all need self-love! 💚")
        else:
            embed = discord.Embed(
                description=f"🤗 **{ctx.author.mention} hugged {member.mention}!** 🤗",
                color=discord.Color.green()
            )
            embed.set_image(url=await self.get_anime_gif("hug"))
            embed.set_footer(text="So wholesome! 💚")
        
        await ctx.send(embed=embed)

    @commands.command(name="slap", aliases=["smack", "hit", "✋"])
    async def slap_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Slap someone! ✋"""
        if member is None:
            await ctx.send(f"You need to mention someone to slap! Usage: `{COMMAND_PREFIX}slap @user`")
            return
        
        if member.bot:
            await ctx.send("You can't slap bots! They're made of metal! 🤖")
            return
        
        if member == ctx.author:
            await ctx.send("Why would you slap yourself? That's just... sad 😅")
            return
        
        gif_url = await self.get_anime_gif("slap")
        
        embed = discord.Embed(
            description=f"✋ **{ctx.author.mention} slapped {member.mention}!** ✋",
            color=discord.Color.red()
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text="Ouch! That's gotta hurt! 😵")
        
        await ctx.send(embed=embed)

    @commands.command(name="sex", aliases=["handhold", "hold", "👫", "lewd", "🍇"])
    async def sex_prefix(self, ctx: commands.Context, member: discord.Member = None):
        """Hold hands with someone! 😳👫"""
        if member is None:
            await ctx.send(f"You need to mention someone to hold hands with! Usage: `{COMMAND_PREFIX}sex @user`")
            return
        
        if member.bot:
            await ctx.send("Bots don't have hands to hold! 🤖")
            return
        
        if member == ctx.author:
            await ctx.send("You can't hold your own hand... that's just sad 😅")
            return
        
        gif_url = await self.get_anime_gif("handhold")
        
        embed = discord.Embed(
            description=f"😳 **{ctx.author.mention} is holding hands with {member.mention}!** 👫",
            color=discord.Color.from_rgb(255, 182, 193)  # Light pink
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text="How lewd! 😳💕")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SocialCog(bot))