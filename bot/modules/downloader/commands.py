import re
from html import escape

from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, \
    InlineKeyboardButton

from bot.command_handler import CommandHandler
from ..base_commands import BaseCommands
from .utils import (
    is_threads_link, is_tiktok_link,
    is_instagram_link, is_youtube_link)
from .sources import (
    Type,
    ThreadsDownloader, TiktokDownloader,
    InstagramDownloader, YoutubeDownloader
)
from .strings import *
from bot.utils.bot_utils import (
    try_media_album_links, try_send_video_and_cleanup, try_send, try_sticker,
    try_delete, chunked
)

from utils import constants
from utils.utils import extract_urls


class Commands(BaseCommands):
    def __init__(self, bot: AsyncTeleBot, handler: CommandHandler = None):
        cmd_func = {
            "dl": self._send_download,
            "download": self._send_download,
            "help_dl": self._send_h,
        }
        cmd_func_pattern = {
            re.compile(r"^/(dl|download)(?:@\w+)?", re.IGNORECASE): self._send_download,
            re.compile(r"^/help_(dl|download)(?:@\w+)?", re.IGNORECASE): self._send_h,
        }
        super().__init__(
            bot, cmd_func, cmd_func_pattern, NAME
        )
        self.command_handler = handler

    async def handle_inline(self, query: InlineQuery) -> list:
        text = query.query.strip()
        links = extract_urls(text)
        if not links: return []
        c_link, c_type = "", Type.UNK
        for link in links:
            if is_threads_link(link):
                c_link = link
                c_type = Type.THREADS
            if c_type != Type.UNK: break
        if not c_link: return []

        thumb = constants.THUMB_DEF
        title = self.strings.get('click_to_runcmd', query.from_user.id)
        result = f"/dl {text}"
        desc = result
        return [InlineQueryResultArticle(
            id=1,
            title=title,
            description=desc,
            thumbnail_url=thumb,
            input_message_content=InputTextMessageContent(
                message_text=result,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        )]


    async def _send_download(self, message: Message):
        only_audio = " mp3" in message.any_text or "mp3 " in message.any_text
        links = extract_urls(message.any_text)
        if not links and message.reply_to_message:
            links = extract_urls(message.reply_to_message.any_text)
        if not only_audio and message.reply_to_message:
            only_audio = " mp3" in message.reply_to_message.any_text or "mp3 " in message.reply_to_message.any_text
        if not links:
            raise ValueError(self.strings.get(LINK_NF, message.chat.id))

        c_link, c_type = "", Type.UNK
        for link in links:
            if is_threads_link(link):
                c_link = link
                c_type = Type.THREADS
            elif is_tiktok_link(link):
                c_link = link
                c_type = Type.TIKTOK
            elif is_instagram_link(link):
                c_link = link
                c_type = Type.INSTAGRAM
            elif is_youtube_link(link):
                c_link = link
                c_type = Type.YOUTUBE
            if c_type != Type.UNK: break
        if not c_link:
            raise ValueError(self.strings.get(SOURCE_NS, message.chat.id))
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            text=f"Open {c_type.name}",
            url=c_link,
        ))
        try_download = True
        sticker = constants.STICKER_MUSIC if only_audio else constants.STICKER_LOADING
        st_loading = await try_sticker(self.bot, sticker, message=message, reply_to_message_id=message.message_id)
        result = {"error": "", "video_urls": [], "image_urls": []}
        if c_type == Type.THREADS:
            _dl = ThreadsDownloader(c_link)
            result = await _dl.fetch()
        elif c_type == Type.TIKTOK:
            _dl = TiktokDownloader(c_link)
            result = await _dl.fetch()
        elif c_type == Type.INSTAGRAM:
            _dl = InstagramDownloader(c_link)
            result = await _dl.fetch()
        elif c_type == Type.YOUTUBE:
            _dl = YoutubeDownloader(c_link)
            result = await _dl.fetch()

        if (not result.get("error") and not result.get("video_urls") and
                not result.get("image_urls") and
                not result.get("video_file_path")):
            text = result.get("text") or self.strings.get(SOURCE_NS, message.chat.id)
            r = await try_send(
                self.bot, message.chat.id,
                text,
                reply_to_message_id=message.message_id,
                markup=markup,
            )
            if isinstance(r, Exception):
                self.logger.error(f"Cant _send_download error to chat [{message.chat.id}]: {r}")
            await try_delete(self.bot, message=st_loading)
            return

        if result.get("error"):
            r = await try_send(
                self.bot, message.chat.id,
                f"⚠️ Error <blockquote>{escape(result.get('error'))}</blockquote>",
                reply_to_message_id=message.message_id,
                markup=markup,
            )
            if isinstance(r, Exception):
                self.logger.error(f"Cant _send_download error to chat [{message.chat.id}]: {r}")
            await try_delete(self.bot, message=st_loading)
            return

        if result.get("video_file_path"):
            text = result.get("text", "")
            r = await try_send_video_and_cleanup(
                self.bot,
                message=message,
                reply_to_message_id=message.message_id,
                video=result.get("video_file_path"),
                text=text.strip(),
                only_audio=only_audio,
                markup=markup,
            )
            if isinstance(r, Exception):
                self.logger.error(f"Cant _send_download video_urls to chat [{message.chat.id}]: {r}")
        if result.get("video_urls"):
            links = [f"<a href='{l}'>link №{n}</a>" for n, l in enumerate(result["video_urls"], 1)]
            text = result.get("text", "")
            text += "\n\n🌐 Links: " + ", ".join(links)
            r = await try_media_album_links(
                self.bot,
                message=message,
                reply_to_message_id=message.message_id,
                urls=result["video_urls"],
                text=text.strip(),
                only_audio=only_audio,
                download=try_download,
                markup=markup,
            )
            if isinstance(r, Exception):
                self.logger.error(f"Cant _send_download video_urls to chat [{message.chat.id}]: {r}")
        if result.get("image_urls"):
            chunks = list(chunked(result.get("image_urls"), 10))
            total = len(chunks)
            for number, urls in enumerate(chunks, 1):
                text = f"<b>PART {number}/{total}</b>\n\n" if total > 1 else ""
                links = [f"<a href='{l}'>link №{n}</a>" for n, l in enumerate(urls, 1)]
                text += result.get("text", "")
                text += "\n\n🌐 Links: " + ", ".join(links)
                r = await try_media_album_links(
                    self.bot,
                    message=message,
                    reply_to_message_id=message.message_id,
                    urls=urls,
                    text=text.strip(),
                    markup=markup,
                )
                if isinstance(r, Exception):
                    self.logger.error(f"Cant _send_download image_urls to chat [{message.chat.id}]: {r}")
        await try_delete(self.bot, message=st_loading)
        return

    async def handle_any_message(self, message: Message) -> bool:
        only_audio = " mp3" in (message.any_text or '') or "mp3 " in (message.any_text or '')
        links = extract_urls(message.any_text)
        if not links and message.reply_to_message:
            links = extract_urls(message.reply_to_message.any_text)
        if not only_audio and message.reply_to_message:
            only_audio = " mp3" in message.reply_to_message.any_text or "mp3 " in message.reply_to_message.any_text
        if not links: return False
        c_link, c_type = "", Type.UNK
        for link in links:
            if is_threads_link(link):
                c_link = link
                c_type = Type.THREADS
            elif is_tiktok_link(link):
                c_link = link
                c_type = Type.TIKTOK
            elif is_instagram_link(link):
                c_link = link
                c_type = Type.INSTAGRAM
            elif is_youtube_link(link):
                c_link = link
                c_type = Type.YOUTUBE
            if c_type != Type.UNK: break
        if not c_link: return False

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            text=f"Open {c_type.name}",
            url=c_link,
        ))
        try_download = True
        sticker = constants.STICKER_MUSIC if only_audio else constants.STICKER_LOADING
        st_loading = await try_sticker(self.bot, sticker, message=message, reply_to_message_id=message.message_id)

        result = {"error": "", "video_urls": [], "image_urls": []}
        if c_type == Type.THREADS:
            td = ThreadsDownloader(c_link)
            result = await td.fetch()
        elif c_type == Type.TIKTOK:
            td = TiktokDownloader(c_link)
            result = await td.fetch()
        elif c_type == Type.INSTAGRAM:
            td = InstagramDownloader(c_link)
            result = await td.fetch()
        elif c_type == Type.YOUTUBE:
            _dl = YoutubeDownloader(c_link)
            result = await _dl.fetch()

        if (not result.get("error") and not result.get("video_urls") and
                not result.get("image_urls") and
                not result.get("video_file_path")):
            text = result.get("text") or self.strings.get(SOURCE_NS, message.chat.id)
            r = await try_send(
                self.bot, message.chat.id,
                text,
                reply_to_message_id=message.message_id,
                markup=markup,
            )
            if isinstance(r, Exception):
                self.logger.error(f"Cant _send_download error to chat [{message.chat.id}]: {r}")
            await try_delete(self.bot, message=st_loading)
            return True

        if result.get("error"):
            r = await try_send(
                self.bot, message.chat.id,
                f"⚠️ Error <blockquote>{result.get('error')}</blockquote>",
                reply_to_message_id=message.message_id,
                markup=markup,
            )
            if isinstance(r, Exception):
                self.logger.error(f"Cant _send_download error to chat [{message.chat.id}]: {r}")
            await try_delete(self.bot, message=st_loading)
            return True

        success = False
        if result.get("video_file_path"):
            text = result.get("text", "")
            r = await try_send_video_and_cleanup(
                self.bot,
                message=message,
                reply_to_message_id=message.message_id,
                video=result.get("video_file_path"),
                text=text.strip(),
                only_audio=only_audio,
                markup=markup,
            )
            if isinstance(r, Message):
                success = True
            if isinstance(r, Exception):
                self.logger.error(f"Cant _send_download video_urls to chat [{message.chat.id}]: {r}")
        if result.get("video_urls"):
            links = [f"<a href='{l}'>link №{n}</a>" for n, l in enumerate(result["video_urls"], 1)]
            text = result.get("text", "")
            text += "\n\n🌐 Links: " + ", ".join(links)
            r = await try_media_album_links(
                self.bot,
                message=message,
                reply_to_message_id=message.message_id,
                urls=result["video_urls"],
                text=text.strip(),
                only_audio=only_audio,
                download=try_download,
                markup=markup,
            )
            if isinstance(r, list):
                success = True
            if isinstance(r, Exception):
                self.logger.error(f"Cant _send_download video_urls to chat [{message.chat.id}]: {r}")
        if result.get("image_urls"):
            chunks = list(chunked(result.get("image_urls"), 10))
            total = len(chunks)
            for number, urls in enumerate(chunks, 1):
                text = f"<b>PART {number}/{total}</b>\n\n" if total > 1 else ""
                links = [f"<a href='{l}'>link №{n}</a>" for n, l in enumerate(urls, 1)]
                text += result.get("text", "")
                text += "\n\n🌐 Links: " + ", ".join(links)
                r = await try_media_album_links(
                    self.bot,
                    message=message,
                    reply_to_message_id=message.message_id,
                    urls=urls,
                    text=text.strip(),
                    markup=markup,
                )
                if isinstance(r, list):
                    success = True
                if isinstance(r, Exception):
                    self.logger.error(f"Cant _send_download image_urls to chat [{message.chat.id}]: {r}")
        await try_delete(self.bot, message=st_loading)
        return success

