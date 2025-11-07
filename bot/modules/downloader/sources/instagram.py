import asyncio
import ssl
import traceback
from html import escape

import aiohttp
import certifi

import instaloader

from yt_dlp import YoutubeDL

from ..utils import normalize_url, shorten_url


class InstagramDownloader:
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
        except Exception as e:
            result["error"] = str(e)
        return result

    async def fetch(self) -> dict:
        r = {}
        _error = ""

        if not r and "/reel/" in self.url:
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self._get_ydl)
                n_video_urls = []
                for url in result.get("video_urls", []):
                    n_video_urls.append(await shorten_url(url))
                    # n_video_urls.append(url)
                text = escape(result.get('text')) if result.get("text") else ""
                r = {
                    "error": f"",
                    "video_urls": n_video_urls,
                    "image_urls": result.get("image_urls", []),
                    "video_file_path": result.get("video_file_path", ""),
                    "text": f"by <b>@<a href='{self.url}'>{escape(result.get('username', 'unknown'))}</a></b>👇🏻" +
                            f"<blockquote>{text}</blockquote>",
                }
            except Exception as e:
                traceback.print_exc()
                _error = str(e)

        if not r and "/p/" in self.url:
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.fetch_loader_post)
                text = escape(result.get('text')) if result.get("text") else ""
                n_video_urls, n_image_urls = [], []
                for url in result.get("video_urls", []):
                    n_video_urls.append(await shorten_url(url))
                for url in result.get("image_urls", []):
                    n_image_urls.append(await shorten_url(url))

                r = {
                    "error": f"",
                    "video_urls": n_video_urls,
                    "image_urls": n_image_urls,
                    "text": f"by <b>@<a href='{self.url}'>{escape(result.get('username', 'unknown'))}</a></b>👇🏻" +
                            f"<blockquote>{text}</blockquote>",
                }
            except Exception as e:
                traceback.print_exc()
                _error = str(e)

        if not r and "/reel/" in self.url:
            try:
                result = await self.fetch_api()
                text = escape(result.get('text')) if result.get("text") else ""
                r = {
                    "error": f"",
                    "video_urls": result.get("video_urls", []),
                    "image_urls": result.get("image_urls", []),
                    "text": f"by <b>@<a href='{self.url}'>{escape(result.get('username', 'unknown'))}</a></b>👇🏻" +
                            f"<blockquote>{text}</blockquote>",
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

    def _get_ydl(self) -> dict:
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'noplaylist': True
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                # ydl.download([self.url])

                username = info.get("title").replace("Post by", "").replace("Video by ", "").strip()
                return {
                    "text": info.get("description"),
                    "username": username,
                    "video_urls": [info.get("url")],
                }
        except Exception as e:
            traceback.print_exc()
            return {
                "error": str(e)
            }

    def fetch_loader_post(self) -> dict:
        code = self.url.split("/p/", 1)[1]
        if "/" in code: code = code.split("/")[0]
        if "?" in code: code = code.split("?")[0]
        try:
            loader = instaloader.Instaloader(quiet=True, sanitize_paths=True)
            post = instaloader.Post.from_shortcode(loader.context, code)
            images_urls = []
            video_urls = []
            if post.typename == "GraphSidecar":
                for node in post.get_sidecar_nodes():
                    if node.is_video:
                        video_urls.append(node.video_url)
                    else:
                        images_urls.append(node.display_url)
            else:
                if post.is_video:
                    video_urls.append(post.video_url)
                else:
                    images_urls.append(post.url)


            return {
                "text": post.caption,
                "username": post.owner_username,
                "video_urls": video_urls,
                "image_urls": images_urls,
            }
        except Exception as e:
            traceback.print_exc()
            return {
                "error": str(e)
            }

