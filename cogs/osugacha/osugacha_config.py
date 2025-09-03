"""
osu!gacha Configuration File
All game settings, crate configurations, mutations, and static data
"""

# Enhanced mutations with unique emojis and effects
MUTATIONS = {
    "shiny": {
        "name": "SHINY",
        "emoji": "✨",
        "rarity": 0.05,
        "multiplier": 2.0,
        "color": "#FFD700",
        "description": "A golden shimmer emanates from this card",
        "effect": "golden_glow"
    },
    "holographic": {
        "name": "HOLOGRAPHIC", 
        "emoji": "🌈",
        "rarity": 0.005,
        "multiplier": 25,
        "color": "#FF69B4",
        "description": "A dazzling spectrum flickers with every angle",
        "effect": "rainbow_border"
    },
    "crystalline": {
        "name": "CRYSTALLINE",
        "emoji": "💎",
        "rarity": 0.02,
        "multiplier": 3.0,
        "color": "#00FFFF",
        "description": "Forged in pressure and perfected by time",
        "effect": "crystal_border"
    },
    "shadow": {
        "name": "SHADOW",
        "emoji": "🌑",
        "rarity": 0.08,
        "multiplier": 1.8,
        "color": "#2F2F2F", 
        "description": "Darkness envelops the edges with mysterious energy",
        "effect": "shadow_aura"
    },
    "golden": {
        "name": "GOLDEN",
        "emoji": "👑",
        "rarity": 0.01,
        "multiplier": 5.0,
        "color": "#FFD700",
        "description": "Infused with the essence of pure gold",
        "effect": "gold_flame"
    },
    "prismatic": {
        "name": "PRISMATIC",
        "emoji": "🔮",
        "rarity": 0.03,
        "multiplier": 2.5,
        "color": "#40E0D0", 
        "description": "Light refracts into brilliant geometric patterns",
        "effect": "prismatic_refraction"
    },
    "cosmic": {
        "name": "COSMIC",
        "emoji": "🌌",
        "rarity": 0.015,
        "multiplier": 3.5,
        "color": "#483D8B",
        "description": "Stars and galaxies spiral within",
        "effect": "cosmic_swirl"
    },
    "shocked": {
        "name": "SHOCKED",
        "emoji": "⚡",
        "rarity": 0.04,
        "multiplier": 2.2,
        "color": "#FBFF00",
        "description": "Electricity pulses through the card",
        "effect": "electric_pulse"
    },
    "spectral": {
        "name": "SPECTRAL",
        "emoji": "👻",
        "rarity": 0.025,
        "multiplier": 2.8,
        "color": "#9370DB", 
        "description": "Ethereal energy flows with ghostly power",
        "effect": "spectral_fade"
    },
    "immortal": {
        "name": "IMMORTAL",
        "emoji": "🔥",
        "rarity": 0.002,
        "multiplier": 50.0,
        "color": "#FF4500",
        "description": "Ancient power burns with immortal flame",
        "effect": "immortal_flame"
    },
    "flashback": {
        "name": "FLASHBACK",
        "emoji": "⬅️",
        "rarity": 0.0025,  # Very rare - only from rainbow/diamond
        "multiplier": 0.8,  # High value for 6-star cards
        "color": "#FFD700",  # Gold color
        "description": "Legendary player from a past era",
        "effect": "flashback_icon"
    }
}

FLASHBACK_CARDS = {
    "cookiezi": {
        "player_data": {
            "user_id": "124493",
            "username": "Cookiezi",
            "rank": 1,  # They were #1
            "pp": 12866,  # Their peak PP
            "accuracy": 99.04,
            "play_count": 6132,
            "country": "KR",
            "level": 100,
            "profile_picture": "https://external-preview.redd.it/jQ4E_aHehXvBtZD40xxo5AkdCVuDJpfMc1Voer4ywUY.jpg?auto=webp&s=37c223e9b60519a613337998d75eae42e38835b9"
        },
        "flashback_year": "2016",
        "flashback_era": "The Jesus of osu!",
        "price_multiplier": 2.1  # Extra valuable because it's historical
    },
    "hvick225": {
        "player_data": {
            "user_id": "50265",
            "username": "hvick225", 
            "rank": 1,
            "pp": 11361,
            "accuracy": 98.79,
            "play_count": 89542,
            "country": "TW",
            "level": 102.0,
            "profile_picture": "https://a.ppy.sh/50265?1234567890.jpeg"
        },
        "flashback_year": "2015",
        "flashback_era": "The Original DT Demon",
        "price_multiplier": 1.75
    },
    "rafis": {
        "player_data": {
            "user_id": "2558286",
            "username": "Rafis",
            "rank": 1,
            "pp": 14187,
            "accuracy": 99.01,
            "play_count": 203177,
            "country": "PL",
            "level": 104,
            "profile_picture": "https://pbs.twimg.com/profile_images/1268931922819977216/dD4AOS34_200x200.jpg"
        },
        "flashback_year": "2016",
        "flashback_era": "The Polish powerhouse who dominated the scene",
        "price_multiplier": 1.75
    },
    "angelsim": {
        "player_data": {
            "user_id": "1777162",
            "username": "Angelsim",
            "rank": 1,
            "pp": 12840,
            "accuracy": 98.89,
            "play_count": 120075,
            "country": "KR",
            "level": 102.0,
            "profile_picture": "https://a.ppy.sh/1777162?1234567890.jpeg"
        },
        "flashback_year": "2016",
        "flashback_era": "Mouse master who dominated with insane precision",
        "price_multiplier": 0.9
    },
    "flyingtuna": {
        "player_data": {
            "user_id": "2831793",
            "username": "FlyingTuna",
            "rank": 1,
            "pp": 15690,
            "accuracy": 98.54,
            "play_count": 123241,
            "country": "KR",
            "level": 103.0,
            "profile_picture": "https://a.ppy.sh/2831793?1234567890.jpeg"
        },
        "flashback_year": "2018",
        "flashback_era": "The tuna that learned to fly to #1",
        "price_multiplier": 1.5
    },
    "vaxei": {
    "player_data": {
        "user_id": "4787150",
        "username": "Vaxei",
        "rank": 1,
        "pp": 17235,
        "accuracy": 99.12,
        "play_count": 145821,
        "country": "US",
        "level": 105,
        "profile_picture": "https://a.ppy.sh/4787150?1234567890.jpeg"
    },
    "flashback_year": "2019",
    "flashback_era": "Bacon boi",
    "price_multiplier": 2
    },
    "idke": {
        "player_data": {
            "user_id": "4650315",
            "username": "idke",
            "rank": 1,
            "pp": 16829,
            "accuracy": 99.41,
            "play_count": 83488,
            "country": "US",
            "level": 108,
            "profile_picture": "https://a.ppy.sh/4650315?1234567890.jpeg"
        },
        "flashback_year": "2019",
        "flashback_era": "HR master and accuracy god",
        "price_multiplier": 1.5
    },
    "freddiebenson": {
        "player_data": {
            "user_id": "7342622",
            "username": "Freddie Benson",
            "rank": 1,
            "pp": 15892,
            "accuracy": 98.95,
            "play_count": 125673,
            "country": "US",
            "level": 104,
            "profile_picture": "https://a.ppy.sh/7342622?1234567890.jpeg"
        },
        "flashback_year": "2019",
        "flashback_era": "DT Farmer",
        "price_multiplier": 0.8
    },
    "mathi": {
        "player_data": {
            "user_id": "5339515",
            "username": "Mathi",
            "rank": 1,
            "pp": 17156,
            "accuracy": 99.05,
            "play_count": 257778,
            "country": "CL",
            "level": 112,
            "profile_picture": "https://a.ppy.sh/5339515?1234567890.jpeg"
        },
        "flashback_year": "2018",
        "flashback_era": "Chilean legend who brought South America to #1",
        "price_multiplier": 1.25
    },
    "wubwoofwolf": {
        "player_data": {
            "user_id": "39828",
            "username": "WubWoofWolf",
            "rank": 1,
            "pp": 10567,
            "accuracy": 98.87,
            "play_count": 356219,
            "country": "PL",
            "level": 109,
            "profile_picture": "https://a.ppy.sh/39828?1234567890.jpeg"
        },
        "flashback_year": "2014",
        "flashback_era": "Awooooooo!",
        "price_multiplier": 0.9
    },
    "sayonara-bye": {
        "player_data": {
            "user_id": "14457",
            "username": "Sayonara-bye",
            "rank": 1,
            "pp": 8963,
            "accuracy": 98.45,
            "play_count": 198567,
            "country": "JP",
            "level": 106,
            "profile_picture": "https://a.ppy.sh/14457?1234567890.jpeg"
        },
        "flashback_year": "2013",
        "flashback_era": "dragonhuman",
        "price_multiplier": 0.75
    },
    "rrtyui": {
        "player_data": {
            "user_id": "352328",
            "username": "rrtyui",
            "rank": 1,
            "pp": 9845,
            "accuracy": 99.23,
            "play_count": 145892,
            "country": "JP",
            "level": 103,
            "profile_picture": "https://a.ppy.sh/352328?1234567890.jpeg"
        },
        "flashback_year": "2014",
        "flashback_era": "Who's afraid of the big black..?",
        "price_multiplier": 0.8
    },
    "whitecat": {
        "player_data": {
            "user_id": "4504101",
            "username": "WhiteCat",
            "rank": 1,
            "pp": 19555,
            "accuracy": 99.23,
            "play_count": 145892,
            "country": "DE",
            "level": 103,
            "profile_picture": "https://i.redd.it/b1i9bgwms5d71.jpg"
    },
    "flashback_year": "2020",
    "flashback_era": "You just got unbanned...",
    "price_multiplier": 2.2
}
    # Add more historical #1 players here as you discover them
}

# Store system configuration (easily changeable)
STORE_CONFIG = {
    "refresh_interval_minutes": 10,  # Store refreshes every 10 minutes
    "stock_ranges": {
        # [min_stock, max_stock] for each crate type
        "copper": [5, 15],
        "tin": [4, 10],
        "common": [2, 5],
        "uncommon": [2, 5], 
        "rare": [1, 5],
        "epic": [1, 5],
        "legendary": [1, 5]
    },
    
    # Keep existing appearance_weights for backward compatibility
    "appearance_weights": {
        # For simple mode: just the base probability
        "copper": 1.0,       # 100% chance (always available)
        "tin": 0.95,         # 95% chance
        "common": 0.90,      # 90% chance
        "uncommon": 0.70,    # 70% chance
        "rare": 0.35,        # 35% chance
        "epic": 0.30,        # 30% chance
        "legendary": 0.25    # 20% chance
    },
    
    # NEW: Advanced appearance system configuration
    "advanced_appearance": {
        "enabled": True,  # Set to False to use simple appearance_weights above
        "mode": "decay",  # Options: "decay", "fixed", "simple"
        
        # Decay system: base_chance * (1 - decay_rate) ** (quantity - 1)
        "decay_rates": {
            "copper": {"base": 1.0, "decay_rate": 0.10},      # Always appears, no decay
            "tin": {"base": 0.95, "decay_rate": 0.10},        # 95% for 1, 85% for 2, etc.
            "common": {"base": 0.90, "decay_rate": 0.10},     # 90% for 1, 81% for 2, etc.
            "uncommon": {"base": 0.70, "decay_rate": 0.15},   # 70% for 1, 59.5% for 2, etc.
            "rare": {"base": 0.35, "decay_rate": 0.20},       # 35% for 1, 26.25% for 2, etc.
            "epic": {"base": 0.30, "decay_rate": 0.20},       # 30% for 1, 22.5% for 2, etc.
            "legendary": {"base": 0.25, "decay_rate": 0.20}   # 25% for 1, 17.5% for 2, 12.25% for 3, etc.
        },
        
        # Fixed rates system: exact percentages per quantity
        "fixed_rates": {
            "legendary": {
                1: 0.25,  # 20% chance for exactly 1 rainbow crate
                2: 0.15,  # 10% chance for exactly 2 rainbow crates
                3: 0.10   # 5% chance for exactly 3 rainbow crates
            },
            "epic": {
                1: 0.30,
                2: 0.15,
                3: 0.08,
                4: 0.04
            },
            "rare": {
                1: 0.35,
                2: 0.20,
                3: 0.12,
                4: 0.07
            }
            # Add more crate types as needed
        }
    }
}

# Daily rewards configuration (easily changeable)
DAILY_CONFIG = {
    "coins": {"min": 1000, "max": 5000},
    "bonus_crate_chance": 1,  # 30% chance for bonus crate
    "bonus_crate_weights": {
        # Weights for bonus crate types (easily changeable)
        "copper": 20,
        "tin": 30,
        "common": 50,
        "uncommon": 10,
        "rare": 5,
        "epic": 1,
        "legendary": 0.5
    }
}

# Store announcement configuration
STORE_ANNOUNCEMENT_CONFIG = {
    "enabled": True,
    "channel_id": None,  # Set this to your desired channel ID
    "mention_role_id": None,  # Optional: role to mention when store refreshes
    "include_descriptions": True,
    "show_refresh_time": True
}

# Store descriptions
STORE_DESCRIPTIONS = {
    "copper": "Homeless players with no skills",
    "tin": "Starving players with basic skills", 
    "common": "Solid mid-tier players",
    "uncommon": "Skilled players with potential", 
    "rare": "Talented players with unique skills",
    "epic": "Exceptional players with mastery",
    "legendary": "The absolute best of the best"
}

# Complete crate configuration with 2 new lower tier crates
CRATE_CONFIG = {
    "copper": {
        "name": "Cardboard Box",
        "emoji": "📦",
        "color": 0xB87333,
        "price": 500,
        "aliases": ["card","cardboard", "box","copper", "beginner", "0"],
        "rank_ranges": [
            {"min": 9001, "max": 10000, "weight": 20},     # Keep 150% return
            {"min": 8001, "max": 9000, "weight": 50},
            {"min": 7001, "max": 8000, "weight": 25},       
            {"min": 5001, "max": 7000, "weight": 20},       
        ]
    },
    "tin": {
        "name": "Tin Can",
        "emoji": "🥫",
        "color": 0xA0A0A0,
        "price": 1000,
        "aliases": ["tin", "tincan", "can", "entry", "0.5"],
        "rank_ranges": [
            {"min": 8001, "max": 10000, "weight": 20},     # Keep 150% return
            {"min": 7001, "max": 8000, "weight": 35},      
            {"min": 6001, "max": 7000, "weight": 55},      
            {"min": 2001, "max": 6000, "weight": 10},       
        ]
    },
    "common": {
        "name": "Bronze Crate",
        "emoji": "🥉",
        "color": 0xCD7F32,
        "price": 5000,
        "aliases": ["bronze", "common", "1"],
        "rank_ranges": [
            {"min": 8001, "max": 10000, "weight": 5},     # Keep 125% return
            {"min": 6001, "max": 8000, "weight": 15},      
            {"min": 4001, "max": 6000, "weight": 30},      
            {"min": 2001, "max": 4000, "weight": 35},      
            {"min": 1001, "max": 2000, "weight": 2.5},     
            {"min": 501, "max": 1000, "weight": 1},      
            {"min": 301, "max": 500, "weight": 0.5},      
            {"min": 201, "max": 300, "weight": 0.1},      
            {"min": 101, "max": 200, "weight": 0.05},      
            {"min": 51, "max": 100, "weight": 0.02},       
            {"min": 26, "max": 50, "weight": 0.01},        
            {"min": 11, "max": 25, "weight": 0.005},       
            {"min": 6, "max": 10, "weight": 0.002},        
            {"min": 4, "max": 5, "weight": 0.001},         
            {"min": 2, "max": 3, "weight": 0.0005},       
            {"min": 1, "max": 1, "weight": 0.0002}         
        ]
    },
    "uncommon": {
        "name": "Silver Crate",
        "emoji": "🥈",
        "color": 0xC0C0C0,
        "price": 10000,
        "aliases": ["silver", "uncommon", "2"],
        "rank_ranges": [
            {"min": 5001, "max": 8000, "weight": 15},      # NERFED: from 30 to 45 (more low value)
            {"min": 4001, "max": 5000, "weight": 20},      
            {"min": 2001, "max": 4000, "weight": 40},      # NERFED: from 25 to 20
            {"min": 1001, "max": 2000, "weight": 20},       # NERFED: from 15 to 8
            {"min": 501, "max": 1000, "weight": 2},        # NERFED: from 4 to 2
            {"min": 301, "max": 500, "weight": 0.6},       # NERFED: from 0.8 to 0.5
            {"min": 201, "max": 300, "weight": 0.15},       # NERFED: from 0.15 to 0.1
            {"min": 101, "max": 200, "weight": 0.075},      # NERFED: from 0.08 to 0.05
            {"min": 51, "max": 100, "weight": 0.025},      # NERFED: from 0.02 to 0.015
            {"min": 26, "max": 50, "weight": 0.02},       # NERFED: from 0.012 to 0.008
            {"min": 11, "max": 25, "weight": 0.0075},       # NERFED: from 0.006 to 0.004
            {"min": 6, "max": 10, "weight": 0.005},        # NERFED: from 0.003 to 0.002
            {"min": 4, "max": 5, "weight": 0.0025},         # NERFED: from 0.002 to 0.001
            {"min": 2, "max": 3, "weight": 0.001},        # NERFED: from 0.001 to 0.0005
            {"min": 1, "max": 1, "weight": 0.0005}         # NERFED: from 0.0005 to 0.0003
        ]
    },
    "rare": {
        "name": "Gold Crate",
        "emoji": "🥇",
        "color": 0xFFD700,
        "price": 50000,
        "aliases": ["gold", "rare", "3"],
        "rank_ranges": [
            {"min": 2001, "max": 4000, "weight": 30},      # NERFED: from 25 to 45 (more low value)
            {"min": 1001, "max": 2000, "weight": 40},      # NERFED: from 35 to 30
            {"min": 501, "max": 1000, "weight": 30},       # NERFED: from 30 to 20
            {"min": 301, "max": 500, "weight": 4},         # NERFED: from 8 to 4
            {"min": 201, "max": 300, "weight": 0.8},       # NERFED: from 1.5 to 0.8
            {"min": 101, "max": 200, "weight": 0.2},      # NERFED: from 0.4 to 0.15
            {"min": 51, "max": 100, "weight": 0.06},       # NERFED: from 0.08 to 0.04
            {"min": 26, "max": 50, "weight": 0.03},       # NERFED: from 0.05 to 0.025
            {"min": 11, "max": 25, "weight": 0.015},       # NERFED: from 0.025 to 0.012
            {"min": 6, "max": 10, "weight": 0.006},        # NERFED: from 0.012 to 0.006
            {"min": 4, "max": 5, "weight": 0.004},         # NERFED: from 0.008 to 0.004
            {"min": 2, "max": 3, "weight": 0.002},         # NERFED: from 0.005 to 0.002
            {"min": 1, "max": 1, "weight": 0.001}          # NERFED: from 0.002 to 0.001
        ]
    },
    "epic": {
        "name": "Diamond Crate",
        "emoji": "💎",
        "color": 0x00FFFF,
        "price": 1000000,
        "aliases": ["diamond", "epic", "4"],
        "rank_ranges": [
            {"min": 501, "max": 1000, "weight": 70},       # NERFED: from 40 to 60 (more low value)
            {"min": 301, "max": 500, "weight": 35},        # NERFED: from 40 to 30
            {"min": 201, "max": 300, "weight": 25},         # NERFED: from 15 to 8
            {"min": 101, "max": 200, "weight": 1.5},       # NERFED: from 4 to 1.8
            {"min": 51, "max": 100, "weight": 0.10},       # NERFED: from 0.8 to 0.15
            {"min": 26, "max": 50, "weight": 0.04},        # NERFED: from 0.15 to 0.04
            {"min": 11, "max": 25, "weight": 0.02},        # NERFED: from 0.08 to 0.02
            {"min": 6, "max": 10, "weight": 0.008},        # NERFED: from 0.04 to 0.008
            {"min": 4, "max": 5, "weight": 0.005},         # NERFED: from 0.02 to 0.005
            {"min": 2, "max": 3, "weight": 0.003},         # NERFED: from 0.01 to 0.003
            {"min": 1, "max": 1, "weight": 0.001}          # NERFED: from 0.005 to 0.001
        ]
    },
    "legendary": {
        "name": "Rainbow Crate",
        "emoji": "🌈",
        "color": 0xFF00FF,
        "price": 5000000,  # Updated price
        "aliases": ["rainbow", "legendary", "5"],
        "rank_ranges": [
            {"min": 101, "max": 200, "weight": 60},        # NERFED: from 50 to 75 (more low value)
            {"min": 51, "max": 100, "weight": 35},         # NERFED: from 35 to 20
            {"min": 26, "max": 50, "weight": 5},           # NERFED: from 12 to 4
            {"min": 11, "max": 25, "weight": 2},         # NERFED: from 2.5 to 0.8
            {"min": 6, "max": 10, "weight": 1},         # NERFED: from 0.4 to 0.15
            {"min": 4, "max": 5, "weight": 0.75},          # NERFED: from 0.08 to 0.04
            {"min": 2, "max": 3, "weight": 0.5},         # NERFED: from 0.015 to 0.008
            {"min": 1, "max": 1, "weight": 0.25}          # NERFED: from 0.005 to 0.002
        ]
    }
}

# Exponential rarity system
RARITY_CONFIG = {
    1: {"stars": 6, "color": 0xE91E63, "name": "Limit Breaker"},          
    (2, 5): {"stars": 6, "color": 0xFFFED6, "name": "Divine"},     
    (6, 10): {"stars": 5, "color": 0x8000FF, "name": "Transcendent"},
    (11, 50): {"stars": 4, "color": 0xFFB700, "name": "Mythical"},   
    (51, 100): {"stars": 4, "color": 0xFFD700, "name": "Legend"},  
    (101, 500): {"stars": 3, "color": 0x9C27B0, "name": "Epic"},      
    (501, 2500): {"stars": 3, "color": 0x00B6FF, "name": "Rare"},    
    (2501, 5000): {"stars": 2, "color": 0x00FF00, "name": "Uncommon"}, 
    (5001, 10000): {"stars": 1, "color": 0x404040, "name": "Common"} 
}

ACHIEVEMENT_DEFINITIONS = {
    # Existing achievements
    "first_card": {"name": "🎯 First Steps", "description": "Obtained your first card"},
    "collector_100": {"name": "📚 Collector", "description": "Obtained 100+ cards"},
    "master_collector_500": {"name": "🏆 Master Collector", "description": "Obtained 500+ cards"},
    "elite_club": {"name": "🗻 Approaching The Summit", "description": "Obtained a Top 10 player card"},
    "champion": {"name": "🥇 Limit Breaker", "description": "Obtained the #1 player card"},
    "six_star_collector": {"name": "✨ Above and Beyond", "description": "Obtained a 6 star card"},
    "wealthy_collector": {"name": "💰 Wealthy Collector", "description": "Collection worth 100,000+ coins"},
    "millionaire": {"name": "💸 Millionaire", "description": "Earned 1,000,000+ coins"},
    "mutation_master": {"name": "🧬 Mutation Master", "description": "Obtained 5+ different mutations"},
    "mutation_holographic": {"name": "🌈 Holographic Reflection", "description": "Obtained a Holographic mutation"},
    "mutation_immortal": {"name": "🔥 Immortal Flame", "description": "Obtained a Immortal mutation"},
    "daily_devotee": {"name": "📅 Daily Devotee", "description": "Claimed daily rewards 30+ times"},
    "legend_hunter": {"name": "🌤️ These Clarion Skies", "description": "Obtained a 5 star card"},
    "five_star_master": {"name": "🌟 Paradigm Shift", "description": "Obtained 10+ 5 star cards"},
    "four_star_expert": {"name": "⭐ Moving Forward", "description": "Obtained 25+ 4 star cards"},
    "crate_crusher": {"name": "📦 Crate Crusher", "description": "Opened 100+ crates"},
    "crate_master": {"name": "🎁 Crate Master", "description": "Opened 500+ crates"},
    "opening_legend": {"name": "🔥 Opening Legend", "description": "Opened 1,000+ crates"},
    "trading_partner": {"name": "🤝 Trading Partner", "description": "Completed 10+ trades"},
    "big_spender": {"name": "💳 Big Spender", "description": "Spent 500,000+ coins in store"},
    "lucky_streak": {"name": "🍀 Lucky Streak", "description": "Got 3+ mutations in a row"},
    "mutation_prismatic": {"name": "🔮 Prismatic Light", "description": "Obtained a Prismatic mutation"},
    "world_traveler": {"name": "🗺️ Tourist", "description": "Collected cards from 10+ countries"},
    "country_collector": {"name": "🌍 World Traveler", "description": "Collected cards from 25+ countries"},
    "pp_hunter": {"name": "💪 20K Club", "description": "Obtained a 20,000+ PP player card"},
    "accuracy_perfectionist": {"name": "🎯 Perfectionist", "description": "Obtained a 99%+ accuracy player card"},
    "collection_curator": {"name": "🎨 Collection Curator", "description": "Favorited 50+ cards"},
    "bargain_hunter": {"name": "💡 Bargain Hunter", "description": "Bought 100+ crates from store"},

    # Not implemented yet
    "gacha_guru": {"name": "🧙‍♂️ Gacha Guru", "description": "Opened 1000+ crates"},
    "card_flipper": {"name": "🔄 Card Flipper", "description": "Sold 100+ cards"},
    "high_roller": {"name": "🎰 High Roller", "description": "Won 10,000+ coins from gambling"},
    "dedication": {"name": "⏰ Dedication", "description": "Played for 100+ days"},
    "social_trader": {"name": "👥 Social Trader", "description": "Traded with 10+ different players"}
}

# Game mechanics configuration
GAME_CONFIG = {
    "mutation_chance": 0.10,  # 10% chance for any mutation
    "crate_cooldown": 12.5,      # 12.5 seconds between crate opens
    "cache_duration": 86400,  # 24 hours cache duration
    "max_rank_attempts": 10,  # Max attempts to find valid player
    "default_starting_coins": 2000,
    "default_daily_coins": 1000,
    "default_confirmations_enabled": True  # Default confirmation preference
}

# API configuration
import os
from dotenv import load_dotenv

# load environment variables
load_dotenv()

API_CONFIG = {
    "client_id": os.getenv("OSU_CLIENT_ID"),  # Required: Get from osu! settings
    "client_secret": os.getenv("OSU_CLIENT_SECRET"),  # Required: Get from osu! settings
    "token_buffer_seconds": 300,  # 5 minute buffer before token expiry
    "max_pages": 200,             # top 100k players (50 per page)
    "request_delay": 0.05,        # 20ms delay between api requests
    "max_rank_attempts": 10,  # max attempts to find valid player
    "retry_attempts": 3,          # number of retry attempts
    "retry_delays": [1, 2, 3]  # retry delays in seconds
}

# File paths
FILE_PATHS = {
    "cache_file": 'data/osu_leaderboard_cache.json',
    "gacha_data": 'data/osu_gacha.json'
}

