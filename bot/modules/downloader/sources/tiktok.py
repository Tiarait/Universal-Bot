import asyncio
import os
import ssl
import traceback
from html import escape

import aiohttp
import certifi

from yt_dlp import YoutubeDL

from ..utils import normalize_url


class TiktokDownloader:
    def __init__(self, url: str):
        self.url = normalize_url(url)

    async def fetch_api(self) -> dict:
        result = {"error": "", "video_urls": [], "image_urls": []}
        api_url = f"https://alfan.app/api/prepare"

        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(api_url, ssl=ssl_context, json={"url": self.url}) as resp:
                    if resp.status != 200:
                        result["error"] = f"HTTP {resp.status}"
                        return result
                    try:
                        data = await resp.json()
                    except Exception:
                        result["error"] = "Invalid JSON response"
                        return result
            dl = data.get("downloadId", "")
            result["text"] = data.get("title", "")
            result["username"] = data.get("author", "")
            result["video_urls"] = [f"https://alfan.app/api/download/{dl}"]

            if not data or not dl:
                api_url = f"https://www.watermarkremover.io/api/video"
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.post(api_url, ssl=ssl_context, json={"url": self.url}) as resp:
                        if resp.status != 200:
                            result["error"] = f"HTTP {resp.status}"
                            return result
                        try:
                            data = await resp.json()
                        except Exception:
                            result["error"] = "Invalid JSON response"
                            return result
                    result["video_urls"] = [data.get("nowm", data.get("wm", ""))]
        except Exception as e:
            result["error"] = str(e)
        return result

    async def fetch(self) -> dict:
        r = {}
        _error = ""
        try:
            result = await self.scrape_tiktok()
            r = {
                "error": f"",
                "video_urls": result.get("videos", []),
                "image_urls": result.get("images", []),
                "video_file_path": result.get("video_file_path", ""),
                "text": f"by <b>@<a href='{self.url}'>{escape(result.get('username'))}</a></b>👇🏻" +
                        f"<blockquote>{escape(result.get('text'))}</blockquote>",
            }
        except Exception as e:
            traceback.print_exc()
            _error = str(e)

        if not r:
            try:
                result = await self.fetch_api()
                r = {
                    "error": f"",
                    "video_urls": result.get("video_urls", []),
                    "image_urls": result.get("image_urls", []),
                    "text": f"by <b>@<a href='{self.url}'>{escape(result.get('username', 'unknown'))}</a></b>👇🏻" +
                            f"<blockquote>{escape(result.get('text'))}</blockquote>",
                }
            except Exception as e:
                traceback.print_exc()
                _error = str(e)
        if not r:
            r = {
                "error": escape(_error),
                "video_urls": [],
                "image_urls": [],
                "text": escape(_error),
            }
        return r

    async def scrape_tiktok(self) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_ydl)

    def _get_ydl(self) -> dict:
        filename = self.url.strip("/")
        if "?" in filename: filename = filename.split("?")[0].strip("/")
        if "/" in filename: filename = filename.split("/")[-1]
        if "?" in filename: filename = filename.split("?")[0]
        output_path = os.path.join(".temp", f"{filename}.mp4")

        ydl_opts = {
            'outtmpl': output_path,
            'quiet': True,
            'noplaylist': True
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                ydl.download([self.url])

                return {
                    "text": info.get("description"),
                    "username": info.get("uploader"),
                    "video_file_path": output_path,
                }
        except Exception as e:
            traceback.print_exc()
            return {
                "error": str(e)
            }

