import asyncio
import io
import os
import random
import ssl
import string
import time
import traceback

import aiohttp
import certifi
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InlineKeyboardButton, ReactionTypeEmoji, InputMediaVideo, InputMediaPhoto, \
    InputMediaAudio, CopyTextButton, ChatMemberAdministrator, ChatMemberOwner

from bs4 import BeautifulSoup, Comment


def b(title: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=title, callback_data=callback)

def cb(title: str, text: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=title, copy_text=CopyTextButton(text=str(text)))


ALLOWED_TAGS = {
    "a", "b", "strong", "i", "em", "u", "ins", "blockquote"
    "s", "strike", "del", "tg-spoiler", "code", "pre", "label"
}
ALLOWED_ATTRS = {
    "a": {"href"},
}

def _sanitize_html_for_telegram(html: str) -> str:
    html = html.replace("<blockquote>", " <label>").replace("</blockquote>", "</label> ")
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(string=lambda text: isinstance(text, Comment)):
        node.extract()
    for script in soup(["script", "style"]):
        script.decompose()

    for tag in soup.find_all():
        name = str(tag.name).lower()

        if name not in ALLOWED_TAGS:
            tag.unwrap()
            continue

        allowed = ALLOWED_ATTRS.get(name, set())
        for attr in list(tag.attrs):
            if attr not in allowed:
                del tag.attrs[attr]
    cleaned = "".join(str(x) for x in soup.body.contents) if soup.body else str(soup)
    cleaned = cleaned.replace("<label>", "<blockquote>").replace("</label>", "</blockquote>")
    return cleaned

async def try_send(
        bot: AsyncTeleBot,
        chat_id: int,
        text: str,
        markup = None,
        reply_to_message_id: int=None,
        **kwargs) -> Message | Exception | None:
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=_sanitize_html_for_telegram(text),
            reply_to_message_id=reply_to_message_id,
            reply_markup=markup,
            allow_sending_without_reply=True,
            **kwargs
        )
    except Exception as e:
        return e

async def try_delete(
        bot: AsyncTeleBot,
        chat_id: int = None,
        message_id: int = None,
        message: Message = None,
        timeout: int | None = None) -> bool | Exception:
    if message and not isinstance(message, Message): return False
    if not message_id and not chat_id and not message: return False
    try:
        if timeout:
            await asyncio.sleep(int(timeout / 1000))
        return await bot.delete_message(
            chat_id=message.chat.id if message else chat_id,
            message_id=message.message_id if message else message_id
        )
    except Exception as e:
        return e

async def try_sticker(
        bot: AsyncTeleBot,
        sticker: str,
        chat_id: int = None,
        message: Message = None,
        reply_to_message_id: int=None,
        **kwargs) -> Message | Exception | None:
    if not chat_id and not message: return None
    try:
        return await bot.send_sticker(
            chat_id=message.chat.id if message else chat_id,
            sticker=sticker,
            reply_to_message_id=reply_to_message_id,
            allow_sending_without_reply=True,
            **kwargs
        )
    except Exception as e:
        return e

async def try_edit(
        bot: AsyncTeleBot,
        text: str,
        chat_id: int = None,
        message_id: int = None,
        message: Message = None,
        markup = None,
        is_new = None,
        **kwargs) -> Message | Exception | None:
    try:
        if not message_id and not chat_id and not message: return None
        if is_new:
            return await try_send(
                bot=bot,
                chat_id=message.chat.id if message else chat_id,
                text=text,
                markup=markup,
                **kwargs
            )
        return await bot.edit_message_text(
            chat_id=message.chat.id if message else chat_id,
            message_id=message.message_id if message else message_id,
            text=_sanitize_html_for_telegram(text),
            reply_markup=markup,
            **kwargs
        )
    except Exception as e:
        return e


async def try_send_video_and_cleanup(
        bot: AsyncTeleBot,
        text: str,
        video: str,
        chat_id: int = None,
        message: Message = None,
        markup=None,
        reply_to_message_id: int = None,
        only_audio: bool = False,
        **kwargs
) -> Message | Exception | None:
    m = None
    try:
        target_chat_id = chat_id or (message.chat.id if message else None)
        if not target_chat_id:
            raise ValueError("chat_id not set")
        name = ''.join(random.choices(string.ascii_letters + string.digits, k=9))
        if isinstance(video, str):
            if os.path.exists(video):
                base = os.path.basename(video)
                name = os.path.splitext(base)[0]
                bio = io.BytesIO(open(video, "rb").read())
            else:
                bio = None
        elif isinstance(video, io.BytesIO):
            video.seek(0)
            bio = video
        elif isinstance(video, bytes):
            bio = io.BytesIO(video)
        else:
            bio = None
        if not bio:
            return await try_send(
                bot=bot,
                chat_id=target_chat_id,
                text=text,
                markup=markup,
                reply_to_message_id=reply_to_message_id,
                **kwargs
            )
        bio.name = name
        if only_audio and bio:
            from utils.utils import video_to_audio_bytes
            audio_bio = await video_to_audio_bytes(video_bytes=bio.read(), name=bio.name)
            m = await bot.send_audio(
                chat_id=target_chat_id,
                audio=InputMediaAudio(audio_bio).media,
                caption=text,
                reply_markup=markup,
                reply_to_message_id=reply_to_message_id,
                allow_sending_without_reply=True,
                **kwargs
            )
        else:
            m = await bot.send_video(
                chat_id=target_chat_id,
                video=InputMediaVideo(bio).media,
                caption=text,
                reply_markup=markup,
                reply_to_message_id=reply_to_message_id,
                allow_sending_without_reply=True,
                **kwargs
            )
    except Exception as e:
        traceback.print_exc()
        return e
    finally:
        if isinstance(video, str) and os.path.exists(video):
            os.remove(video)
        return m


def chunked(iterable: list, size: int) -> list[list]:
    return [iterable[i:i + size] for i in range(0, len(iterable), size)]

async def try_media_album_links(
        bot: AsyncTeleBot,
        text: str,
        urls: list[str],
        chat_id: int = None,
        message: Message = None,
        markup=None,
        reply_to_message_id: int = None,
        only_audio: bool = False,
        download: bool = True,
        **kwargs) -> list[Message] | Exception:
    media_group = []
    try:
        if download:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            async with aiohttp.ClientSession() as session:
                for url in urls:
                    async with session.get(url, ssl=ssl_context) as resp:
                        if resp.status != 200:
                            continue
                        content_type = resp.headers.get("Content-Type", "")
                        content = await resp.read()
                        bio = io.BytesIO(content)
                        bio.name = url.split("/")[-1]

                        if "video" in content_type:
                            if only_audio:
                                from utils.utils import video_to_audio_bytes
                                audio_bio = await video_to_audio_bytes(content, name=bio.name)
                                media_group.append(InputMediaAudio(audio_bio))
                            else:
                                media_group.append(InputMediaVideo(bio))
                        elif "image" in content_type:
                            media_group.append(InputMediaPhoto(bio))

        target_chat_id = chat_id or (message.chat.id if message else None)
        if not target_chat_id:
            raise ValueError("chat_id not set")

        sent_messages = []

        if len(media_group) > 1:
            media_group[-1].caption = text
            chunks = chunked(media_group, 10)
            last_message_id = reply_to_message_id
            for chunk in chunks:
                msgs = await bot.send_media_group(
                    chat_id=target_chat_id,
                    media=chunk,
                    reply_to_message_id=last_message_id,
                    allow_sending_without_reply=True,
                    **kwargs
                )
                last_message_id = msgs[-1].message_id
                sent_messages.extend(msgs)
        elif media_group:
            m = None
            first = media_group[0]
            if isinstance(first, InputMediaPhoto):
                m = await bot.send_photo(
                    chat_id=target_chat_id,
                    photo=first.media,
                    caption=text,
                    reply_markup=markup,
                    reply_to_message_id=reply_to_message_id,
                    allow_sending_without_reply=True,
                    **kwargs
                )
            elif isinstance(first, InputMediaVideo):
                m = await bot.send_video(
                    chat_id=target_chat_id,
                    video=first.media,
                    caption=text,
                    reply_markup=markup,
                    reply_to_message_id=reply_to_message_id,
                    allow_sending_without_reply=True,
                    **kwargs
                )
            elif isinstance(first, InputMediaAudio):
                m = await bot.send_audio(
                    chat_id=target_chat_id,
                    audio=first.media,
                    caption=text,
                    reply_markup=markup,
                    reply_to_message_id=reply_to_message_id,
                    allow_sending_without_reply=True,
                    **kwargs
                )
            if m:
                sent_messages.append(m)
        elif text:
            m = await try_send(
                bot=bot,
                chat_id=target_chat_id,
                text=text,
                markup=markup,
                reply_to_message_id=reply_to_message_id,
                **kwargs
            )
            if m:
                sent_messages.append(m)
        return sent_messages
    except Exception as e:
        traceback.print_exc()
        return e


async def try_video_note(
        bot: AsyncTeleBot,
        chat_id: int,
        video_bio: io.BytesIO,
        reply_to_message_id: int = None,
        size: int = 360
):
    try:
        return await bot.send_video_note(
            chat_id=chat_id,
            data=video_bio,
            allow_sending_without_reply=True,
            length=size,
            reply_to_message_id=reply_to_message_id
        )
    except Exception as e:
        return e


async def try_voice(
        bot: AsyncTeleBot,
        chat_id: int,
        audio_bio: io.BytesIO,
        reply_to_message_id: int = None
):
    try:
        return await bot.send_voice(
            chat_id=chat_id,
            voice=audio_bio,
            allow_sending_without_reply=True,
            reply_to_message_id=reply_to_message_id
        )
    except Exception as e:
        return e


async def try_reaction(
        bot: AsyncTeleBot,
        reaction: str,
        chat_id: int = None,
        message_id: int = None,
        message: Message = None,
        **kwargs) -> Exception | bool:
    if not message_id and not chat_id and not message: return False
    try:
        e_reaction = ReactionTypeEmoji(emoji=reaction)
        return await bot.set_message_reaction(
            chat_id=message.chat.id if message else chat_id,
            message_id=message.message_id if message else message_id,
            reaction=[e_reaction],
            **kwargs)
    except Exception as e:
        return e


async def is_admin(bot: AsyncTeleBot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
    except Exception:
        return False


hist_user_timecall = {}

def block_flood(chat_id: int, time_ms: int):
    hist = hist_user_timecall.setdefault(chat_id, {})
    cur_time = int(time.time() * 1000)
    hist["last"] = cur_time + time_ms


def check_flood(chat_id: int) -> int:
    hist = hist_user_timecall.setdefault(chat_id, {})
    cur_time = int(time.time() * 1000)
    last_update_ms = cur_time - hist.get("last", 0)
    return int((hist.get("last", 0) - cur_time) / 1000) if last_update_ms < 500 else 0

def is_owner_chat(message: Message) -> bool:
    return message.chat.id == message.from_user.id