import asyncio
import os
import re
import glob
import random
import logging
import aiohttp
from typing import Union
import yt_dlp
import config
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from Opus.utils.database import is_on_off
from Opus.utils.formatters import time_to_seconds

# Set up logger for this module
logger = logging.getLogger("YouTubeAPI")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.DEBUG)

_cookie_cache = None

async def download_cookies_from_url(url):
    logger.debug(f"Attempting to download cookies from URL: {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    os.makedirs("cookies", exist_ok=True)
                    temp_path = "cookies/cookies.txt"
                    with open(temp_path, 'wb') as f:
                        f.write(await response.read())
                    logger.debug(f"Cookies downloaded and saved to {temp_path}")
                    return temp_path
                else:
                    logger.error(f"Failed to download cookies: HTTP {response.status}")
                    return None
    except Exception as e:
        logger.error(f"Exception while downloading cookies: {e}")
        return None

async def cookie_txt_file():
    global _cookie_cache
    if _cookie_cache:
        logger.debug("Using cached cookie file path")
        return _cookie_cache

    remote_url = config.API
    local_path = await download_cookies_from_url(remote_url)

    if local_path:
        filename = f"{os.getcwd()}/cookies/logs.csv"
        with open(filename, 'a') as file:
            file.write(f'Using remote cookies from: {remote_url}\n')
        _cookie_cache = local_path
        logger.debug(f"Using remote cookies: {local_path}")
        return local_path

    folder_path = f"{os.getcwd()}/cookies"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        logger.error("No .txt cookie files found locally and remote download failed.")
        raise FileNotFoundError("No .txt files found in the specified folder and remote download failed.")
    cookie_txt_file = random.choice(txt_files)
    with open(filename, 'a') as file:
        file.write(f'Fallback to local file: {cookie_txt_file}\n')
    _cookie_cache = f"cookies/{str(cookie_txt_file).split('/')[-1]}"
    logger.debug(f"Using local cookie file: {_cookie_cache}")
    return _cookie_cache

async def check_file_size(link):
    logger.debug(f"Checking file size for link: {link}")

    async def get_format_info(link, cookie_file):
        ydl_opts = {"quiet": True, "cookiefile": cookie_file}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
        return info

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format and format['filesize']:
                total_size += format['filesize']
        return total_size

    cookie_file = await cookie_txt_file()
    info = await get_format_info(link, cookie_file)
    if not info:
        logger.warning("No video info found for file size check.")
        return None

    formats = info.get('formats', [])
    if not formats:
        logger.warning("No formats found for file size check.")
        return None

    total_size = parse_size(formats)
    logger.debug(f"Total file size: {total_size} bytes")
    return total_size

async def shell_cmd(cmd):
    logger.debug(f"Executing shell command: {cmd}")
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        error_msg = errorz.decode("utf-8")
        if "unavailable videos are hidden" in error_msg.lower():
            logger.debug(f"Shell command partial error but continuing: {error_msg}")
            return out.decode("utf-8")
        else:
            logger.error(f"Shell command error: {error_msg}")
            return error_msg
    logger.debug(f"Shell command succeeded with output size: {len(out)}")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.url_regex = re.compile(self.regex)

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        exists = bool(self.url_regex.search(link))
        logger.debug(f"URL existence check for {link}: {exists}")
        return exists

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        url = (message.text or message.caption)[entity.offset:entity.offset + entity.length]
                        logger.debug(f"Found URL in message: {url}")
                        return url
            if message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        logger.debug(f"Found TEXT_LINK URL: {entity.url}")
                        return entity.url
        logger.debug("No URL found in the message or reply")
        return None

    async def _fetch_video_info(self, link: str, limit: int = 1):
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=limit)
        return (await results.next())["result"]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = 0 if duration_min == "None" else int(time_to_seconds(duration_min))
            logger.debug(f"Video details: title={title}, duration={duration_min}, id={vidid}")
            return title, duration_min, duration_sec, thumbnail, vidid
        return None, None, None, None, None

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            logger.debug(f"Fetched title: {result['title']}")
            return result["title"]
        return None

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            logger.debug(f"Fetched duration: {result['duration']}")
            return result["duration"]
        return None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            logger.debug(f"Fetched thumbnail url")
            return result["thumbnails"][0]["url"].split("?")[0]
        return None

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = await cookie_txt_file()
        ydl_opts = {
            "format": "best[height<=?720][width<=?1280]",
            "quiet": True,
            "cookiefile": cookie_file,
            "no_warnings": True,
        }
        logger.debug(f"Starting video info extraction for link: {link}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            url = info.get("url") if info else None
            if url:
                logger.debug(f"Extracted video url successfully")
                return 1, url
            else:
                logger.error(f"Failed to extract video url")
                return 0, "Failed to extract video URL"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = await cookie_txt_file()
        cmd = f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_file} --playlist-end {limit} --skip-download {link}"
        result = await shell_cmd(cmd)
        try:
            playlist_ids = [key for key in result.split("\n") if key]
            logger.debug(f"Fetched playlist with {len(playlist_ids)} items")
            return playlist_ids
        except Exception as e:
            logger.error(f"Failed to parse playlist result: {e}")
            return []

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        for result in await self._fetch_video_info(link):
            track_details = {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result["duration"],
                "thumb": result["thumbnails"][0]["url"].split("?")[0],
            }
            logger.debug(f"Fetched track details for link")
            return track_details, result["id"]
        return {}, None

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = await cookie_txt_file()
        ydl_opts = {"quiet": True, "cookiefile": cookie_file}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            r = ydl.extract_info(link, download=False)
            formats_available = []
            for format in r["formats"]:
                if "dash" in str(format.get("format", "")).lower():
                    continue
                if all(key in format for key in ["format", "filesize", "format_id", "ext", "format_note"]):
                    formats_available.append({
                        "format": format["format"],
                        "filesize": format["filesize"],
                        "format_id": format["format_id"],
                        "ext": format["ext"],
                        "format_note": format["format_note"],
                        "yturl": link,
                    })
            logger.debug(f"Found {len(formats_available)} suitable formats")
            return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        result = await self._fetch_video_info(link, limit=10)
        if query_type < len(result):
            r = result[query_type]
            logger.debug(f"Slider query result: {r['title']}")
            return r["title"], r["duration"], r["thumbnails"][0]["url"].split("?")[0], r["id"]
        else:
            logger.warning("Slider query type exceeds available results")
        return None, None, None, None

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        cookie_file = await cookie_txt_file()
        loop = asyncio.get_running_loop()

        def audio_dl():
            logger.debug("Starting audio download")
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as ydl:
                info = ydl.extract_info(link, download=False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    logger.debug(f"Audio file already exists: {xyz}")
                    return xyz
                ydl.download([link])
                logger.debug(f"Audio download downloaded file: {xyz}")
                return xyz

        def video_dl():
            logger.debug("Starting video download")
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_file,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_optssx) as ydl:
                info = ydl.extract_info(link, download=False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    logger.debug(f"Video file already exists: {xyz}")
                    return xyz
                ydl.download([link])
                logger.debug(f"Video download finished file: {xyz}")
                return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            logger.debug(f"Starting song+video download for format {formats} to {fpath}")
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
            with yt_dlp.YoutubeDL(ydl_optssx) as ydl:
                ydl.download([link])
            logger.debug("Song+video download completed")
            return f"downloads/{title}.mp4"

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            logger.debug(f"Starting song audio download to {fpath}")
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
            with yt_dlp.YoutubeDL(ydl_optssx) as ydl:
                ydl.download([link])
            logger.debug("Song audio download completed")
            return f"downloads/{title}.mp3"

        if songvideo:
            return await loop.run_in_executor(None, song_video_dl)
        elif songaudio:
            return await loop.run_in_executor(None, song_audio_dl)
        elif video:
            if await is_on_off(1):
                logger.debug("Direct video download mode enabled")
                return await loop.run_in_executor(None, video_dl)
            file_size = await check_file_size(link)
            if not file_size:
                logger.warning("File size check failed, aborting video download.")
                return None
            total_size_mb = file_size / (1024 * 1024)
            if total_size_mb > 500:
                logger.warning(f"File size {total_size_mb:.2f} MB exceeds 500MB limit. Download aborted.")
                return None
            logger.debug("File size within limit, starting video download")
            return await loop.run_in_executor(None, video_dl)
        else:
            logger.debug("Starting audio-only download")
            return await loop.run_in_executor(None, audio_dl), True
