import asyncio
import os
from datetime import datetime, timedelta
from typing import Union, Optional

from ntgcalls import TelegramServerError
from pyrogram import Client
from pyrogram.errors import FloodWait, ChatAdminRequired
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, Update, VideoQuality

import config
from strings import get_string
from Opus import LOGGER, YouTube, app
from Opus.misc import db
from Opus.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from Opus.utils.exceptions import AssistantErr
from Opus.utils.formatters import check_duration, seconds_to_min, speed_converter
from Opus.utils.inline.play import stream_markup
from Opus.utils.stream.autoclear import auto_clean
from Opus.utils.thumbnails import get_thumb
from Opus.utils.errors import capture_internal_err, send_large_error

autoend = {}
counter = {}

def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    """Create MediaStream compatible with pytgcalls v2.2.5"""
    if video:
        return MediaStream(
            path,
            audio_parameters=AudioQuality.STUDIO,
            video_parameters=VideoQuality.UHD_4K,
            ffmpeg_parameters=ffmpeg_params,
        )
    else:
        return MediaStream(
            path,
            audio_parameters=AudioQuality.HIGH,
            ffmpeg_parameters=ffmpeg_params,
        )

async def _clear_(chat_id: int) -> None:
    """Clear chat data and reset state"""
    try:
        popped = db.pop(chat_id, None)
        if popped:
            await auto_clean(popped)
        db[chat_id] = []
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await set_loop(chat_id, 0)
    except Exception as e:
        LOGGER(__name__).warning(f"Error in _clear_: {e}")

class Call:
    def __init__(self):
        self.userbot1 = Client(
            "SpaceXAss1", config.API_ID, config.API_HASH, session_string=config.STRING1
        ) if config.STRING1 else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client(
            "SpaceXAss2", config.API_ID, config.API_HASH, session_string=config.STRING2
        ) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client(
            "SpaceXAss3", config.API_ID, config.API_HASH, session_string=config.STRING3
        ) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client(
            "SpaceXAss4", config.API_ID, config.API_HASH, session_string=config.STRING4
        ) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client(
            "SpaceXAss5", config.API_ID, config.API_HASH, session_string=config.STRING5
        ) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls: set[int] = set()
        self._ping_cache = {"value": 0.0, "last_update": 0}

    async def _get_assistant(self, chat_id: int):
        """Get assistant with better error handling"""
        try:
            return await group_assistant(self, chat_id)
        except (IndexError, ValueError, AttributeError) as e:
            LOGGER(__name__).warning(f"No assistant available for chat {chat_id}: {e}")
            raise AssistantErr("No assistant available")

    @capture_internal_err
    async def pause_stream(self, chat_id: int) -> None:
        assistant = await self._get_assistant(chat_id)
        await assistant.pause(chat_id)

    @capture_internal_err
    async def resume_stream(self, chat_id: int) -> None:
        assistant = await self._get_assistant(chat_id)
        await assistant.resume(chat_id)

    @capture_internal_err
    async def mute_stream(self, chat_id: int) -> None:
        assistant = await self._get_assistant(chat_id)
        await assistant.mute(chat_id)

    @capture_internal_err
    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await self._get_assistant(chat_id)
        await assistant.unmute(chat_id)

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        try:
            assistant = await self._get_assistant(chat_id)
        except AssistantErr:
            await _clear_(chat_id)
            self.active_calls.discard(chat_id)
            return

        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return

        try:
            await assistant.leave_call(chat_id)
        except (NoActiveGroupCall, Exception):
            pass
        finally:
            self.active_calls.discard(chat_id)

    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        try:
            assistant = await self._get_assistant(chat_id)
        except AssistantErr:
            await _clear_(chat_id)
            self.active_calls.discard(chat_id)
            return

        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except (IndexError, KeyError):
            pass

        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return

        try:
            await assistant.leave_call(chat_id)
        except (NoActiveGroupCall, Exception):
            pass
        finally:
            self.active_calls.discard(chat_id)

    @capture_internal_err
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        assistant = await self._get_assistant(chat_id)
        stream = dynamic_media_stream(path=link, video=bool(video))
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def vc_users(self, chat_id: int) -> list:
        try:
            assistant = await self._get_assistant(chat_id)
            participants = await assistant.get_participants(chat_id)
            return [p.user_id for p in participants if not getattr(p, 'muted_by_admin', False)]
        except Exception as e:
            LOGGER(__name__).warning(f"Error getting VC users: {e}")
            return []

    @capture_internal_err
    async def change_volume(self, chat_id: int, volume: int) -> None:
        assistant = await self._get_assistant(chat_id)
        volume = max(1, min(200, volume))

        try:
            await assistant.change_volume_call(chat_id, volume)
        except AttributeError:
            try:
                await assistant.set_call_property(chat_id, volume=volume)
            except Exception as e:
                LOGGER(__name__).warning(f"Volume change failed: {e}")
                raise AssistantErr("Volume change not supported")

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        assistant = await self._get_assistant(chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(path=file_path, video=is_video, ffmpeg_params=ffmpeg_params)
        await assistant.play(chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        """Unified speedup method with robust error handling"""
        # Validate input
        if not isinstance(playing, list) or not playing or not isinstance(playing[0], dict):
            raise AssistantErr("No active stream found for speedup")
        current_queue = db.get(chat_id, [])
        if not current_queue:
            raise AssistantErr("No active stream found for speedup")
        current_item = current_queue[0].copy()
        original_file_path = str(current_item.get("file", ""))
        if original_file_path != str(file_path):
            raise AssistantErr("File path mismatch - stream may have changed")
        try:
            speed = float(speed)
        except (ValueError, TypeError):
            raise AssistantErr("Invalid speed value")
        if speed <= 0 or speed > 3.0:
            raise AssistantErr("Speed must be between 0.1 and 3.0")
        assistant = await self._get_assistant(chat_id)
        if abs(speed - 1.0) < 0.01:
            out = file_path
        else:
            base = os.path.basename(file_path)
            clean_base = "".join(c for c in base if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            if not any(clean_base.endswith(ext) for ext in ['.mp3', '.mp4', '.wav', '.m4a', '.mkv', '.avi']):
                clean_base += '.mp3'
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            os.makedirs(chatdir, exist_ok=True)
            out = os.path.join(chatdir, clean_base)
            if not os.path.isfile(out):
                # Speed conversion mapping
                speed_map = {
                    "0.5": 2.0,
                    "0.75": 1.35,
                    "1.5": 0.68,
                    "2.0": 0.5
                }
                vs = speed_map.get(str(speed), 1.0 / speed)
                is_video = playing[0].get("streamtype") == "video"
                if is_video:
                    cmd = [
                        "ffmpeg", "-i", file_path,
                        "-filter:v", f"setpts={vs}*PTS",
                        "-filter:a", f"atempo={speed}",
                        "-c:v", "libx264", "-c:a", "aac",
                        "-preset", "ultrafast", "-crf", "28",
                        "-y", out
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-i", file_path,
                        "-filter:a", f"atempo={speed}",
                        "-c:a", "libmp3lame", "-b:a", "128k",
                        "-y", out
                    ]
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdin=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE
                    )
                    _, stderr = await proc.communicate()
                    if proc.returncode != 0:
                        LOGGER(__name__).warning(f"FFmpeg failed: {stderr.decode()}")
                        out = file_path
                except Exception as e:
                    LOGGER(__name__).error(f"FFmpeg execution failed: {e}")
                    out = file_path
        try:
            dur_str = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
            dur = int(float(dur_str))
        except (ValueError, TypeError):
            dur = int(playing[0].get("seconds", 180))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        is_video = playing[0].get("streamtype") == "video"
        if is_video:
            stream = MediaStream(
                out,
                audio_parameters=AudioQuality.STUDIO,
                video_parameters=VideoQuality.UHD_4K,
                ffmpeg_parameters=f"-ss {played} -to {duration}",
            )
        else:
            stream = MediaStream(
                out,
                audio_parameters=AudioQuality.HIGH,
                ffmpeg_parameters=f"-ss {played} -to {duration}",
            )
        await assistant.play(chat_id, stream)
        try:
            current_queue = db.get(chat_id, [])
            if (current_queue and len(current_queue) > 0 and
                str(current_queue[0].get("file", "")) == original_file_path):
                if not current_queue[0].get("old_dur"):
                    db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                    db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
                db[chat_id][0].update({
                    "played": con_seconds,
                    "dur": duration,
                    "seconds": dur,
                    "speed_path": out,
                    "speed": speed
                })
        except (IndexError, KeyError) as e:
            LOGGER(__name__).warning(f"Could not update database after speedup: {e}")

    @capture_internal_err
    async def stream_call(self, link: str) -> None:
        """Stream to logger chat"""
        try:
            assistant = await self._get_assistant(config.LOGGER_ID)
            stream = MediaStream(link, audio_parameters=AudioQuality.STUDIO)
            await assistant.play(config.LOGGER_ID, stream)
        except ChatAdminRequired:
            LOGGER(__name__).warning(f"Cannot stream - bot not admin in LOGGER_ID ({config.LOGGER_ID})")
            try:
                await app.send_message(
                    config.OWNER_ID,
                    "❌ <b>Failed to stream in LOGGER_ID</b>\n\n"
                    "Reason: Bot or Assistant is not admin in LOGGER chat.\n\n"
                    "Please promote the bot/all assistants or update LOGGER_ID."
                )
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to notify owner: {e}")
        except AssistantErr:
            LOGGER(__name__).warning("No assistant available for stream_call")
        except Exception as e:
            LOGGER(__name__).exception(f"stream_call failed: {e}")

    @capture_internal_err
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ) -> None:
        """Join voice/video call"""
        assistant = await self._get_assistant(chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)

        # Validate and convert link to string
        if link is None:
            raise AssistantErr("Invalid stream link")

        link = str(link)

        # Create stream
        if link.startswith(('http://', 'https://')) and 'index_' not in link:
            if video:
                stream = MediaStream(
                    link,
                    audio_parameters=AudioQuality.STUDIO,
                    video_parameters=VideoQuality.UHD_4K,
                )
            else:
                stream = MediaStream(link, audio_parameters=AudioQuality.HIGH)
        else:
            stream = dynamic_media_stream(path=link, video=bool(video))

        try:
            await assistant.play(chat_id, stream)
        except NoActiveGroupCall:
            try:
                await assistant.create_group_call(chat_id)
                await assistant.play(chat_id, stream)
            except ChatAdminRequired:
                raise AssistantErr(_["call_8"])
        except ChatAdminRequired:
            raise AssistantErr(_["call_8"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])
        except Exception as e:
            raise AssistantErr(f"Unable to join group call.\nReason: {e}")

        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)

        if video:
            await add_active_video_chat(chat_id)

        # Auto-end setup
        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except Exception:
                pass

    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                if chat_id in self.active_calls:
                    try:
                        await client.leave_call(chat_id)
                    except NoActiveGroupCall:
                        pass
                    except Exception:
                        pass
                    finally:
                        self.active_calls.discard(chat_id)
                return
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except:
                return
        else:
            try:
                queued = check[0]["file"]
            except (KeyError, IndexError):
                LOGGER(__name__).warning(f"Corrupted queue entry in {chat_id}")
                return await self.play(client, chat_id)

            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            videoid = check[0]["vidid"]
            db[chat_id][0]["played"] = 0

            exis = (check[0]).get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = check[0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0

            video = True if str(streamtype) == "video" else False

            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                stream = dynamic_media_stream(path=link, video=video)
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=True if str(streamtype) == "video" else False,
                    )
                except:
                    return await mystic.edit_text(
                        _["call_6"], disable_web_page_preview=True
                    )

                stream = dynamic_media_stream(path=file_path, video=video)
                try:
                    await client.play(chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                img = await get_thumb(videoid)
                button = stream_markup(_, chat_id)
                await mystic.delete()
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

            elif "index_" in queued:
                try:
                    if videoid.startswith(('http://', 'https://')):
                        if video:
                            stream = MediaStream(
                                videoid,
                                audio_parameters=AudioQuality.STUDIO,
                                video_parameters=VideoQuality.UHD_4K,
                            )
                        else:
                            stream = MediaStream(
                                videoid,
                                audio_parameters=AudioQuality.HIGH,
                            )
                    else:
                        stream = dynamic_media_stream(path=videoid, video=video)
                    
                    await client.play(chat_id, stream)
                except Exception as e:
                    LOGGER(__name__).error(f"Index streaming failed: {e}")
                    return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=config.STREAM_IMG_URL,
                    caption=_["stream_2"].format(user),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"

            else:
                stream = dynamic_media_stream(path=queued, video=video)
                try:
                    await client.play(chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
                        ),
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                elif videoid == "soundcloud":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                else:
                    img = await get_thumb(videoid)
                    button = stream_markup(_, chat_id)
                    try:
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                check[0]["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    except FloodWait as e:
                        LOGGER(__name__).warning(f"FloodWait: Sleeping for {e.value}")
                        await asyncio.sleep(e.value)
                        run = await app.send_photo(
                            chat_id=original_chat_id,
                            photo=img,
                            caption=_["stream_1"].format(
                                f"https://t.me/{app.username}?start=info_{videoid}",
                                title[:23],
                                check[0]["dur"],
                                user,
                            ),
                            reply_markup=InlineKeyboardMarkup(button),
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "stream"

    async def start(self) -> None:
        """Start all available clients"""
        LOGGER(__name__).info("⚙️ Pʏ-TɢCᴀʟʟs Eɴɢɪɴᴇ Wᴀʀᴍɪɴɢ ᴜᴘ...")
        
        clients = [
            (self.one, "STRING1"),
            (self.two, "STRING2"),
            (self.three, "STRING3"), 
            (self.four, "STRING4"),
            (self.five, "STRING5")
        ]
        
        for client, config_name in clients:
            if client and getattr(config, config_name, None):
                try:
                    await client.start()
                    LOGGER(__name__).info(f"✅ {config_name} client started successfully")
                except Exception as e:
                    LOGGER(__name__).error(f"❌ Failed to start Pytg Client {config_name}: {e}")

    @capture_internal_err
    async def ping(self) -> str:
        """Fixed ping method with caching"""
        current_time = asyncio.get_event_loop().time()
        
        # Use cached value if recent (within 30 seconds)
        if current_time - self._ping_cache["last_update"] < 30:
            return str(self._ping_cache["value"])
        
        pings = []
        assistants = [
            (self.one, "STRING1"),
            (self.two, "STRING2"), 
            (self.three, "STRING3"),
            (self.four, "STRING4"),
            (self.five, "STRING5")
        ]
        
        for assistant, config_name in assistants:
            if assistant and getattr(config, config_name, None):
                try:
                    # Fixed ping access - it's a property, not a coroutine
                    ping_value = assistant.ping
                    if isinstance(ping_value, (int, float)) and ping_value > 0:
                        pings.append(float(ping_value))
                except Exception as e:
                    LOGGER(__name__).warning(f"Ping failed for {config_name}: {e}")
                    continue
        
        if pings:
            avg_ping = round(sum(pings) / len(pings), 3)
        else:
            avg_ping = 0.0
            
        # Update cache
        self._ping_cache = {"value": avg_ping, "last_update": current_time}
        return str(avg_ping)

    @capture_internal_err
    async def decorators(self) -> None:
        """Setup event handlers for all assistants"""
        assistants = [a for a in [self.one, self.two, self.three, self.four, self.five] if a]
        
        if not assistants:
            LOGGER(__name__).warning("No assistants available for decorators")
            return

        CRITICAL_FLAGS = (
            ChatUpdate.Status.KICKED |
            ChatUpdate.Status.LEFT_GROUP |
            ChatUpdate.Status.CLOSED_VOICE_CHAT |
            ChatUpdate.Status.DISCARDED_CALL |
            ChatUpdate.Status.BUSY_CALL
        )

        async def unified_update_handler(client, update: Update) -> None:
            try:
                if isinstance(update, ChatUpdate):
                    if (update.status & ChatUpdate.Status.LEFT_CALL or 
                        update.status & CRITICAL_FLAGS):
                        await self.stop_stream(update.chat_id)
                        return

                elif isinstance(update, StreamEnded):
                    if update.stream_type in (StreamEnded.Type.AUDIO, StreamEnded.Type.VIDEO):
                        check = db.get(update.chat_id)
                        if not check or len(check) == 0:
                            await self.stop_stream(update.chat_id)
                            return
                        else:
                            await self.play(client, update.chat_id)

            except Exception as e:
                import sys, traceback
                exc_type, exc_obj, exc_tb = sys.exc_info()
                full_trace = "".join(traceback.format_exception(exc_type, exc_obj, exc_tb))
                caption = (
                    f"🚨 <b>Stream Update Error</b>\n"
                    f"📍 <b>Update Type:</b> <code>{type(update).__name__}</code>\n"
                    f"📍 <b>Error:</b> <code>{exc_type.__name__}</code>"
                )
                filename = f"update_error_{getattr(update, 'chat_id', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                await send_large_error(full_trace, caption, filename)

        # Register handlers for all assistants
        for assistant in assistants:
            assistant.on_update()(unified_update_handler)

Signal = Call()
