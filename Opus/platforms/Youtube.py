import asyncio
import os
import re
import json
import glob
import random
import logging
import aiohttp
from typing import Union, Optional, Tuple, List, Dict
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds

# Global variables for caching
SESSION = None
COOKIE_PATH = None
METADATA_CACHE = {}

async def initialize_session():
    """Initialize a single aiohttp ClientSession."""
    global SESSION
    if SESSION is None:
        SESSION = aiohttp.ClientSession()

async def download_cookies_from_url(url: str) -> Optional[str]:
    """Download cookies from a URL and save to a file."""
    await initialize_session()  # Ensure session is initialized
    try:
        async with SESSION.get(url) as response:
            if response.status == 200:
                os.makedirs("cookies", exist_ok=True)
                temp_path = "cookies/cookies.txt"
                with open(temp_path, 'wb') as f:
                    f.write(await response.read())
                with open("cookies/logs.csv", 'a') as f:
                    f.write(f'Using remote cookies from: {url}\n')
                return temp_path
            else:
                logging.error(f"Failed to download cookies: HTTP {response.status}")
                return None
    except Exception as e:
        logging.error(f"Error downloading cookies: {str(e)}")
        return None

async def cookie_txt_file() -> str:
    """Get or fetch cookie file path, caching the result."""
    global COOKIE_PATH
    if COOKIE_PATH:
        return COOKIE_PATH

    remote_url = config.API
    COOKIE_PATH = await download_cookies_from_url(remote_url)
    
    if not COOKIE_PATH:
        folder_path = f"{os.getcwd()}/cookies"
        txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
        if not txt_files:
            raise FileNotFoundError("No .txt files found in the specified folder and remote download failed.")
        COOKIE_PATH = random.choice(txt_files)
        with open("cookies/logs.csv", 'a') as f:
            f.write(f'Fallback to local file: {COOKIE_PATH}\n')
    
    return COOKIE_PATH

async def check_file_size(link: str) -> Optional[int]:
    """Check total file size of a YouTube video using yt_dlp."""
    ydl_opts = {
        "quiet": True,
        "cookiefile": await cookie_txt_file(),
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(link, download=False)
            total_size = sum(f['filesize'] for f in info.get('formats', []) if 'filesize' in f)
            return total_size
        except Exception as e:
            logging.error(f"Error checking file size: {str(e)}")
            return None

async def shell_cmd(cmd: str) -> str:
    """Execute a shell command asynchronously."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Optional[Union[bool, str]] = None) -> bool:
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Optional[str]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset is None:
            return None
        return text[offset:offset + length]

    async def _fetch_metadata(self, link: str) -> Dict:
        """Fetch and cache video metadata."""
        if link in METADATA_CACHE:
            return METADATA_CACHE[link]
        results = VideosSearch(link, limit=1)
        result = (await results.next())["result"][0]
        duration_min = result["duration"]
        duration_sec = 0 if duration_min == "None" else int(time_to_seconds(duration_min))
        metadata = {
            "title": result["title"],
            "duration_min": duration_min,
            "duration_sec": duration_sec,
            "thumbnail": result["thumbnails"][0]["url"].split("?")[0],
            "vidid": result["id"],
            "link": result["link"],
        }
        METADATA_CACHE[link] = metadata
        return metadata

    async def details(self, link: str, videoid: Optional[Union[bool, str]] = None) -> Tuple[str, str, int, str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        metadata = await self._fetch_metadata(link)
        return (
            metadata["title"],
            metadata["duration_min"],
            metadata["duration_sec"],
            metadata["thumbnail"],
            metadata["vidid"],
        )

    async def title(self, link: str, videoid: Optional[Union[bool, str]] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        return (await self._fetch_metadata(link))["title"]

    async def duration(self, link: str, videoid: Optional[Union[bool, str]] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        return (await self._fetch_metadata(link))["duration_min"]

    async def thumbnail(self, link: str, videoid: Optional[Union[bool, str]] = None) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        return (await self._fetch_metadata(link))["thumbnail"]

    async def video(self, link: str, videoid: Optional[Union[bool, str]] = None) -> Tuple[int, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ydl_opts = {
            "format": "best[height<=?720][width<=?1280]",
            "quiet": True,
            "cookiefile": await cookie_txt_file(),
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(link, download=False)
                return 1, info["url"]
            except Exception as e:
                logging.error(f"Error fetching video URL: {str(e)}")
                return 0, str(e)

    async def playlist(self, link: str, limit: int, user_id: int, videoid: Optional[Union[bool, str]] = None) -> List[str]:
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {await cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = [vid for vid in playlist.split("\n") if vid]
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Optional[Union[bool, str]] = None) -> Tuple[Dict, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        metadata = await self._fetch_metadata(link)
        track_details = {
            "title": metadata["title"],
            "link": metadata["link"],
            "vidid": metadata["vidid"],
            "duration_min": metadata["duration_min"],
            "thumb": metadata["thumbnail"],
        }
        return track_details, metadata["vidid"]

    async def formats(self, link: str, videoid: Optional[Union[bool, str]] = None) -> Tuple[List[Dict], str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ydl_opts = {"quiet": True, "cookiefile": await cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ydl_opts)
        with ydl:
            formats_available = []
            try:
                r = ydl.extract_info(link, download=False)
                for format in r["formats"]:
                    if "dash" in str(format.get("format", "")).lower():
                        continue
                    if all(key in format for key in ["format", "filesize", "format_id", "ext", "format_note"]):
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format["filesize"],
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
            except Exception as e:
                logging.error(f"Error fetching formats: {str(e)}")
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Optional[Union[bool, str]] = None,
    ) -> Tuple[str, str, str, str]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")[query_type]
        return (
            result["title"],
            result["duration"],
            result["thumbnails"][0]["url"].split("?")[0],
            result["id"],
        )

    async def download(
        self,
        link: str,
        mystic,
        video: Optional[Union[bool, str]] = None,
        videoid: Optional[Union[bool, str]] = None,
        songaudio: Optional[Union[bool, str]] = None,
        songvideo: Optional[Union[bool, str]] = None,
        format_id: Optional[Union[bool, str]] = None,
        title: Optional[Union[bool, str]] = None,
    ) -> Tuple[str, bool]:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        cookie_file = await cookie_txt_file()

        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, download=False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, download=False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_file,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            return f"downloads/{title}.mp4"

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_file,
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "320",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            return f"downloads/{title}.mp3"

        loop = asyncio.get_running_loop()
        if songvideo:
            return await loop.run_in_executor(None, song_video_dl), True
        elif songaudio:
            return await loop.run_in_executor(None, song_audio_dl), True
        elif video:
            if await is_on_off(1):
                return await loop.run_in_executor(None, video_dl), True
            else:
                total_size = await check_file_size(link)
                if total_size and total_size / (1024 * 1024) > 250:
                    logging.error(f"File size {total_size / (1024 * 1024):.2f} MB exceeds the 250MB limit.")
                    return None, False
                ydl_opts = {
                    "format": "best[height<=?720][width<=?1280]",
                    "quiet": True,
                    "cookiefile": cookie_file,
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        info = ydl.extract_info(link, download=False)
                        return info["url"], False
                    except Exception as e:
                        logging.error(f"Error streaming video: {str(e)}")
                        return None, False
        else:
            return await loop.run_in_executor(None, audio_dl), True
