import os
from datetime import datetime, timezone

# Configurable command prefix
COMMAND_PREFIX = "!"

XP_PER_MESSAGE = 15
MESSAGE_COOLDOWN_SECONDS = 30

# Generate level XP thresholds using a cubic formula. Adjust LEVEL_CURVE_SCALER to
# make leveling easier/harder while preserving that higher levels require more XP.
#
# Old formula multiplied the polynomial by 2 which produced a fairly steep curve.
# To make leveling easier (so someone who was ~level 35 becomes ~level 60+ with
# the same XP), we scale the whole curve down by a factor. Tweak LEVEL_CURVE_SCALER
# if you want a different compression (smaller -> easier to level up).
LEVEL_CURVE_SCALER = 0.50
LEVEL_XP_THRESHOLDS = [
    round(LEVEL_CURVE_SCALER * ((5 * (i ** 3)) / 3 + (45 * (i ** 2)) / 2 + (455 * i) / 6))
    for i in range(201)
]

DATA_FOLDER = "data"
WARNINGS_FILE = os.path.join(DATA_FOLDER, "warnings.json")
BIRTHDAYS_FILE = os.path.join(DATA_FOLDER, "birthdays.json")
XP_DATA_FILE = os.path.join(DATA_FOLDER, "xp_data.json")
BIRTHDAY_NOTIFICATIONS_FILE = os.path.join(DATA_FOLDER, "birthday_notifications.json")
LEVEL_ROLES_FILE = os.path.join(DATA_FOLDER, "level_roles.json")
REMINDERS_FILE = os.path.join(DATA_FOLDER, "reminders.json")
IZUMI_MEMORIES_FILE = os.path.join(DATA_FOLDER, "izumi_memories.json")
IZUMI_SELF_FILE = os.path.join(DATA_FOLDER, "izumi_self.json")

ITEMS_PER_PAGE = 10

# YouTube video analysis settings
YOUTUBE_ANALYSIS_ENABLED = True  # Set to False to disable YouTube analysis
YOUTUBE_DOWNLOAD_MODE = "audio"  # "audio" (default, faster/cheaper) or "video" (full analysis)
YOUTUBE_MAX_SIZE_MB = 100  # Maximum file size in MB (for video mode)
YOUTUBE_MAX_DURATION_SECONDS = 1800  # Maximum duration (30 minutes default)
YOUTUBE_TEMP_DIR = os.path.join(DATA_FOLDER, "youtube_temp")  # Temp download folder

# Create data folder if it doesn't exist
if not os.path.exists(DATA_FOLDER):
    try:
        os.makedirs(DATA_FOLDER)
        print(f"Successfully created data folder: {DATA_FOLDER}")
    except OSError as e:
        print(f"Error creating data folder {DATA_FOLDER}: {e}. Please check script permissions for this location.")

# Create YouTube temp folder if it doesn't exist
if YOUTUBE_ANALYSIS_ENABLED and not os.path.exists(YOUTUBE_TEMP_DIR):
    try:
        os.makedirs(YOUTUBE_TEMP_DIR)
        print(f"Successfully created YouTube temp folder: {YOUTUBE_TEMP_DIR}")
    except OSError as e:
        print(f"Error creating YouTube temp folder {YOUTUBE_TEMP_DIR}: {e}")