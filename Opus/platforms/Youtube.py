import asyncio
import os
import re
import json
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

from Opus import LOGGER

# Ensuring logger is an instance, not a function
logger = LOGGER if not callable(LOGGER) else LOGGER()

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
        logger.error(f"Error downloading cookies: {str(e)}")
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
        logger.debug(f"Remote cookies loaded from {remote_url}")
        return local_path
    
    folder_path = f"{os.getcwd()}/cookies"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        error_msg = "No .txt files found in the specified folder and remote download failed."
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    cookie_txt_file = random.choice(txt_files)
    with open(filename, 'a') as file:
        file.write(f'Fallback to local file: {cookie_txt_file}\n')
    _cookie_cache = f"cookies/{str(cookie_txt_file).split('/')[-1]}"
    logger.debug(f"Fallback to local cookie file: {_cookie_cache}")
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
        logger.warning("No info found when checking file size.")
        return None
    
    formats = info.get('formats', [])
    if not formats:
        logger.warning("No formats found during file size check.")
        return None
    
    total_size = parse_size(formats)
    logger.debug(f"Total size of media formats: {total_size} bytes")
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
        err_msg = errorz.decode("utf-8")
        if "unavailable videos are hidden" in err_msg.lower():
            logger.debug(f"Shell command returned specific error but continuing: {err_msg}")
            return out.decode("utf-8")
        else:
            logger.error(f"Shell command error: {err_msg}")
            return err_msg
    logger.debug("Shell command executed successfully")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        exists = bool(re.search(self.regex, link))
        logger.debug(f"Checked existence for link {link}: {exists}")
        return exists

    async def url(self, message_1: Message) -> Union[str, None]:
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
                        logger.debug(f"Found TEXT_LINK URL: {entity.url}")
                        return entity.url
        if offset in (None,):
            logger.debug("No URL entity found in messages")
            return None
        extracted_url = text[offset : offset + length]
        logger.debug(f"Extracted URL: {extracted_url}")
        return extracted_url

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"]["url"].split("?")
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min != "None" else 0
        logger.debug(f"Fetched details: {title}, duration: {duration_min}, id: {vidid}")
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        logger.debug(f"Fetched title: {title}")
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        logger.debug(f"Fetched duration: {duration}")
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"]["url"].split("?")
        logger.debug(f"Fetched thumbnail url")
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        logger.debug(f"Starting video URL extraction for {link}")
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", await cookie_txt_file(),
            "-g",
            "-f", "bestvideo[height<=480]+bestaudio/best/best[height<=480]/best[height<=720]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            logger.debug("Video URL extraction successful")
            return 1, stdout.decode().split("\n")
        else:
            err = stderr.decode()
            logger.error(f"Video URL extraction failed: {err}")
            return 0, err

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        logger.debug(f"Fetching playlist items for {link} with limit {limit}")
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {await cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        result = [x for x in playlist.split("\n") if x]
        logger.debug(f"Playlist fetched with {len(result)} items")
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            track_details = {
                "title": result["title"],
                "link": result["link"],
                "vidid": result["id"],
                "duration_min": result["duration"],
                "thumb": result["thumbnails"]["url"].split("?"),
            }
        logger.debug(f"Track details fetched for {link}")
        return track_details, result["id"]

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ydl = yt_dlp.YoutubeDL({"quiet": True, "cookiefile": await cookie_txt_file()})
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                if "dash" in str(format["format"]).lower():
                    continue
                try:
                    formats_available.append({
                        "format": format["format"],
                        "filesize": format.get("filesize"),
                        "format_id": format.get("format_id"),
                        "ext": format.get("ext"),
                        "format_note": format.get("format_note"),
                        "yturl": link,
                    })
                except Exception:
                    continue
        logger.debug(f"Fetched {len(formats_available)} formats for {link}")
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"]["url"].split("?")
        logger.debug(f"Slider query fetched: {title}")
        return title, duration_min, thumbnail, vidid

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
        loop = asyncio.get_running_loop()
        logger.debug(f"Starting download for link: {link} with options video={video}, songaudio={songaudio}, songvideo={songvideo}")

        def audio_dl():
            logger.debug("Starting audio download")
            ydl_optssx = {
                "format": "bestaudio[ext=webm]/bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                logger.debug(f"Audio file already exists: {xyz}")
                return xyz
            x.download([link])
            logger.debug(f"Audio download completed: {xyz}")
            return xyz

        def video_dl():
            logger.debug("Starting video download")
            ydl_optssx = {
                "format": "bestvideo[height<=480]+bestaudio/best/best[height<=480]/best[height<=720]",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                logger.debug(f"Video file already exists: {xyz}")
                return xyz
            x.download([link])
            logger.debug(f"Video download completed: {xyz}")
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            logger.debug(f"Starting song + video download with format {formats} to {fpath}")
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            logger.debug("Song + video download completed")

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
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])
            logger.debug("Song audio download completed")

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            logger.debug(f"Song video download finished: {fpath}")
            return fpath
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            logger.debug(f"Song audio download finished: {fpath}")
            return fpath
        elif video:
            if await is_on_off(1):
                direct = True
                logger.debug("Direct video download enabled")
                downloaded_file = await loop.run_in_executor(None, video_dl)
            else:
                logger.debug("Direct video download disabled, fetching URLs")
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies", await cookie_txt_file(),
                    "-g",
                    "-f", "bestvideo[height<=480]+bestaudio/best/best[height<=480]/best[height<=720]",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")
                    direct = False
                    logger.debug("Fetched download URLs directly")
                else:
                    file_size = await check_file_size(link)
                    if not file_size:
                        logger.warning("File size unknown, aborting download")
                        return None
                    total_size_mb = file_size / (1024 * 1024)
                    if total_size_mb > 500:
                        logger.warning(f"File size {total_size_mb:.2f} MB exceeds limit, skipping download")
                        return None
                    direct = True
                    logger.debug("File size within limit, proceeding with direct video download")
                    downloaded_file = await loop.run_in_executor(None, video_dl)
        else:
            direct = True
            logger.debug("Downloading audio only")
            downloaded_file = await loop.run_in_executor(None, audio_dl)
        logger.debug(f"Download finished: {downloaded_file}, direct={direct}")
        return downloaded_file, direct
