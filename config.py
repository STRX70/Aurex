import re
from os import getenv

from dotenv import load_dotenv
from pyrogram import filters

load_dotenv()

API_ID = "27696582"
API_HASH = "45fccefb72a57ff1b858339774b6d005"

BOT_TOKEN = getenv("BOT_TOKEN")

MONGO_DB_URI = getenv("MONGO_DB_URI")

OWNER_ID = int(getenv("OWNER_ID", 1265397721))

LOGGER_ID = int(getenv("LOGGER_ID", None))

HEROKU_APP_NAME = getenv("HEROKU_APP_NAME")
HEROKU_API_KEY = getenv("HEROKU_API_KEY")

UPSTREAM_REPO = getenv("UPSTREAM_REPO", "https://github.com/KEXI01/TEST")
UPSTREAM_BRANCH = getenv("UPSTREAM_BRANCH", "main")
GIT_TOKEN = getenv("GIT_TOKEN", None) 

DURATION_LIMIT_MIN = int(getenv("DURATION_LIMIT", 9000))

def time_to_seconds(time: str) -> int:
    return sum(int(x) * 60**i for i, x in enumerate(reversed(time.split(":"))))

DURATION_LIMIT = time_to_seconds(f"{DURATION_LIMIT_MIN}:00")

PLAYLIST_FETCH_LIMIT = int(getenv("PLAYLIST_FETCH_LIMIT", 100))

TG_AUDIO_FILESIZE_LIMIT = int(getenv("TG_AUDIO_FILESIZE_LIMIT", 104857600))     # 100 MB
TG_VIDEO_FILESIZE_LIMIT = int(getenv("TG_VIDEO_FILESIZE_LIMIT", 1073741824))   # 1 GB

AUTO_LEAVING_ASSISTANT = bool(getenv("AUTO_LEAVING_ASSISTANT", False))

SPOTIFY_CLIENT_ID = getenv("SPOTIFY_CLIENT_ID", "2d3fd5ccdd3d43dda6f17864d8eb7281")
SPOTIFY_CLIENT_SECRET = getenv("SPOTIFY_CLIENT_SECRET", "48d311d8910a4531ae81205e1f754d27")
API = getenv("API", None)

STRING1 = getenv("STRING_SESSION", None)
STRING2 = getenv("STRING_SESSION2", None)
STRING3 = getenv("STRING_SESSION3", None)
STRING4 = getenv("STRING_SESSION4", None)
STRING5 = getenv("STRING_SESSION5", None)

SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/STORM_TECHH")
SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/STORM_CORE")

if SUPPORT_CHANNEL and not re.match(r"(?:http|https)://", SUPPORT_CHANNEL):
    raise SystemExit("[ERROR] - SUPPORT_CHANNEL url is invalid. Must start with https://")

if SUPPORT_CHAT and not re.match(r"(?:http|https)://", SUPPORT_CHAT):
    raise SystemExit("[ERROR] - SUPPORT_CHAT url is invalid. Must start with https://")

DEFAULT_IMG = "https://graph.org/file/97669c286e18c2eddc72d.jpg"

START_IMG_URL = getenv("START_IMG_URL", DEFAULT_IMG)
PING_IMG_URL = getenv("PING_IMG_URL", DEFAULT_IMG)
PLAYLIST_IMG_URL = DEFAULT_IMG
STATS_IMG_URL = DEFAULT_IMG
TELEGRAM_AUDIO_URL = DEFAULT_IMG
TELEGRAM_VIDEO_URL = DEFAULT_IMG
STREAM_IMG_URL = DEFAULT_IMG
SOUNCLOUD_IMG_URL = DEFAULT_IMG
YOUTUBE_IMG_URL = DEFAULT_IMG
SPOTIFY_ARTIST_IMG_URL = DEFAULT_IMG
SPOTIFY_ALBUM_IMG_URL = DEFAULT_IMG
SPOTIFY_PLAYLIST_IMG_URL = DEFAULT_IMG

BANNED_USERS = filters.user()
adminlist = {}
lyrical = {}
votemode = {}
autoclean = []
confirmer = {}
