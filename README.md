# 🌸 Izumi Bot 

hey there! welcome to my lil discord bot project~ this is izumi, and she's honestly pretty awesome if i do say so myself 😎

## ✨ what she does

izumi is basically ur new bestie who lives in discord and does tons of cool stuff:

- **💬 ai chat** - she's got gemini ai powering her brain so she can have actual convos with u and remember stuff about everyone
- **🎮 osu! gacha** - collect trading cards of top osu! players, open crates, daily rewards, the whole shebang
- **📊 leveling system** - gain xp from chatting, level up, get roles automatically  
- **🎂 birthday tracking** - she'll remember when it's ur bday and wish u happy birthday!
- **⚖️ moderation tools** - warnings, timeouts, all that mod stuff
- **🎉 social commands** - hugs, headpats, all the wholesome interaction commands
- **📝 reminders** - set reminders and she'll ping u later

## 🚀 getting started

### what u need first:
- python 3.8+ (i use 3.12 but anything recent should work)
- a discord bot token from [discord developer portal](https://discord.com/developers/applications)
- gemini ai api key from [google ai studio](https://aistudio.google.com/) 
- osu! api credentials from [osu! settings](https://osu.ppy.sh/home/account/edit) (optional, only if u want gacha features)

### quick setup:

1. **clone this bad boy:**
   ```bash
   git clone https://github.com/dinonuwg/izumi.git
   cd izumi
   ```

2. **install the requirements:**
   ```bash
   pip install -r requirements.txt
   ```

3. **setup ur environment:**
   - copy `.env.template` to `.env`
   - fill in all ur api keys and tokens
   - make sure to set BOT_OWNER_ID to ur discord user id for admin commands

4. **run it:**
   ```bash
   python bot.py
   ```

that's it! she should boot up and be ready to go ✨

## 🔧 configuration 

everything important goes in the `.env` file:

```env
# required stuff
DISCORD_TOKEN=ur_bot_token_here
GEMINI_API_KEY=ur_gemini_key_here  
BOT_OWNER_ID=ur_discord_user_id

# optional osu! features
OSU_CLIENT_ID=ur_osu_client_id
OSU_CLIENT_SECRET=ur_osu_secret

# other optional stuff
LOG_LEVEL=INFO
COMMAND_PREFIX=!
```

## 📁 how it's organized

```
├── bot.py                 # main bot file, where the magic happens
├── cogs/                  # all the feature modules
│   ├── ai/               # ai chat system and memory management  
│   ├── moderation/       # mod tools, leveling, birthdays, etc
│   └── osugacha/         # osu! gacha card collection system
├── data/                 # json files where everything gets saved
├── utils/                # helper functions and config stuff
└── requirements.txt      # all the python packages u need
```

## 🌟 cool features

### ai system
izumi uses google's gemini ai and has a pretty sophisticated memory system. she remembers conversations, learns about server members, and builds up her own personality over time. it's honestly kinda wild how natural she feels to talk to

### osu! gacha  
this is probably the most complex part - it's a full trading card game using the osu! api. collect cards of top players, open different crate types, complete achievements, daily rewards, the whole mobile game experience but in discord lol

### leveling & roles
automatic xp from chatting, configurable level roles, birthday notifications - all the community building stuff u want in a server

## 🛠️ development

the code is pretty modular so adding new features is ez. each major system is its own cog, and there's a unified memory system that lets different parts of the bot share data about users.

if u wanna contribute or modify stuff, the main areas are:
- `bot.py` - core bot logic and startup
- `cogs/ai/` - ai personality and memory system  
- `cogs/osugacha/` - gacha game logic
- `utils/` - shared helper functions

## 🌐 server deployment

included are some scripts for easy deployment:

**Windows Scripts:**
- `win_setup.bat` - quick setup for Windows development
- `win_run_bot.bat` - run the bot on Windows
- `win_transfer_helper.bat` - help transfer files to Linux server

**Linux Server Scripts:**
- `linux_server_setup.sh` - complete Ubuntu server setup with systemd service
- `linux_manage_bot.sh` - easy service management commands  
- `win_to_linux_transfer.sh` - transfer from Windows/Mac to Linux server
- automatic startup, logging, and error recovery

## 💝 credits & thanks

shoutout to the discord.py team for the amazing library, google for gemini ai, and peppy for the osu! api. also thanks to everyone who helped test this thing and gave feedback !
