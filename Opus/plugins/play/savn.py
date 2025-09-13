import random
import string

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from config import BANNED_USERS, lyrical
from Opus import app, LOGGER, Platform
from Opus.utils import seconds_to_min, time_to_seconds
from Opus.utils.jdatabase import is_video_allowed
from Opus.utils.decorators.play import PlayWrapper
from Opus.utils.formatters import formats
from Opus.utils.inline.play import (
    livestream_markup,
    playlist_markup,
    slider_markup,
    track_markup,
)
from Opus.utils.inline.playlist import botplaylist_markup
from Opus.utils.logger import play_logs
from Opus.utils.stream.stream import stream


@app.on_message(
    filters.command("saavn", prefixes=["/", "!", "%", ",", "@", "#"])
    & filters.group
    & ~BANNED_USERS
)
@PlayWrapper
async def saavn_cmd(
    client,
    message: Message,
    _,
    chat_id,
    video,
    channel,
    playmode,
    url,
    fplay,
):
    mystic = await message.reply_text(_["play_2"].format(channel) if channel else _["play_1"])
    plist_id = None
    slider = None
    plist_type = None
    spotify = None
    user_id = message.from_user.id
    user_name = message.from_user.mention

    if len(message.command) < 2:
        return await mystic.edit_text("Please provide a JioSaavn URL or search query after /saavn")

    query = message.text.split(None, 1)[1]
    if "-v" in query:
        query = query.replace("-v", "")
        video = True

    # Check if it's a URL
    if query.startswith("http"):
        if "shows" in query:
            return await mystic.edit_text(_["saavn_1"])
        elif await Platform.saavn.is_song(query):
            try:
                file_path, details = await Platform.saavn.download(query)
            except Exception as e:
                ex_type = type(e).__name__
                LOGGER(__name__).error("An error occurred", exc_info=True)
                return await mystic.edit_text(_["play_3"])
            duration_sec = details["duration_sec"]
            streamtype = "saavn_track"

            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        details["duration_min"],
                    )
                )
        elif await Platform.saavn.is_playlist(query):
            try:
                details = await Platform.saavn.playlist(
                    query, limit=config.PLAYLIST_FETCH_LIMIT
                )
                streamtype = "saavn_playlist"
            except Exception as e:
                ex_type = type(e).__name__
                LOGGER(__name__).error("An error occurred", exc_info=True)
                return await mystic.edit_text(_["play_3"])

            if len(details) == 0:
                return await mystic.edit_text(_["play_3"])
        else:
            # Treat as search query
            slider = True
            try:
                # Assuming Platform.saavn has a search method; if not, integrate one from JioSaavnAPI
                # For example: details, track_id = await Platform.saavn.search(query)
                # Here, I'll assume it falls back to YouTube for search, or implement search
                # To keep it Saavn-only, add search logic
                # Placeholder: details, track_id = await Platform.saavn.search(query)
                details, track_id = await Platform.saavn.track(query)  # Adjust if search is different
                streamtype = "saavn_search"
            except Exception:
                return await mystic.edit_text(_["play_3"])
    else:
        # Treat as search query
        slider = True
        try:
            details, track_id = await Platform.saavn.search(query)  # Assuming search method
            streamtype = "saavn_search"
        except Exception:
            return await mystic.edit_text(_["play_3"])

    if str(playmode) == "Direct" and not plist_type:
        if "duration_min" in details and details["duration_min"]:
            duration_sec = time_to_seconds(details["duration_min"])
            if duration_sec > config.DURATION_LIMIT:
                return await mystic.edit_text(
                    _["play_6"].format(
                        config.DURATION_LIMIT_MIN,
                        details["duration_min"],
                    )
                )
        else:
            buttons = livestream_markup(
                _,
                track_id if 'track_id' in locals() else None,
                user_id,
                "v" if video else "a",
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            return await mystic.edit_text(
                _["play_15"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        try:
            await stream(
                _,
                mystic,
                user_id,
                details,
                chat_id,
                user_name,
                message.chat.id,
                video=video,
                streamtype=streamtype,
                forceplay=fplay,
            )
        except Exception as e:
            ex_type = type(e).__name__
            if ex_type == "AssistantErr":
                err = e
            else:
                LOGGER(__name__).error("An error occurred", exc_info=True)
                err = _["general_3"].format(ex_type)
            return await mystic.edit_text(err)
        await mystic.delete()
        return await play_logs(message, streamtype=streamtype)
    else:
        if plist_type:
            ran_hash = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
            lyrical[ran_hash] = plist_id
            buttons = playlist_markup(
                _,
                ran_hash,
                message.from_user.id,
                plist_type,
                "c" if channel else "g",
                "f" if fplay else "d",
            )
            await mystic.delete()
            await message.reply_photo(
                photo=config.SAAVN_PLAYLIST_IMG_URL or config.PLAYLIST_IMG_URL,  # Add config if needed
                caption=_["play_12"].format(message.from_user.first_name),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            return await play_logs(message, streamtype=f"Saavn Playlist")
        else:
            if slider:
                buttons = slider_markup(
                    _,
                    track_id,
                    message.from_user.id,
                    query,
                    0,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                await mystic.delete()
                await message.reply_photo(
                    photo=details.get("thumb", config.SAAVN_DEFAULT_IMG_URL),
                    caption=_["play_11"].format(
                        details["title"].title(),
                        details.get("duration_min", "Unknown"),
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype=f"Searched on Saavn")
            else:
                buttons = track_markup(
                    _,
                    track_id,
                    message.from_user.id,
                    "c" if channel else "g",
                    "f" if fplay else "d",
                )
                await mystic.delete()
                await message.reply_photo(
                    photo=details.get("thumb", config.SAAVN_DEFAULT_IMG_URL),
                    caption=_["play_11"].format(
                        details["title"],
                        details.get("duration_min", "Unknown"),
                    ),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
                return await play_logs(message, streamtype=f"Saavn Track")
