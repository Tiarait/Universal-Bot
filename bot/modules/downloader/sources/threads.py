import json
import re
import ssl
import traceback
import urllib.parse
from html import escape

import aiohttp
import certifi

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from utils.constants import semaphore
from ..utils import normalize_url, shorten_url

class ThreadsDownloader:
    def __init__(self, url: str):
        self.url = normalize_url(url)
        m = re.search(r'/@(?P<username>[^/]+)/post/(?P<code>[^/?]+)', self.url)
        self.username = m.group('username') if m else "unknown"
        self.code = m.group('code') if m else "unknown"

    async def fetch_api(self) -> dict:
        result = {"error": "", "video_urls": [], "image_urls": []}
        api_url = f"https://api.threadsphotodownloader.com/v2/media?url={self.url}"

        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(api_url, ssl=ssl_context) as resp:
                    if resp.status != 200:
                        result["error"] = f"HTTP {resp.status}"
                        return result
                    try:
                        data = await resp.json()
                    except Exception:
                        result["error"] = "Invalid JSON response"
                        return result

            result["image_urls"] = data.get("image_urls", [])
            for vid in data.get("video_urls", []):
                if url := vid.get("download_url"):
                    result["video_urls"].append(url)
        except Exception as e:
            result["error"] = str(e)
        return result

    async def fetch(self) -> dict:
        r = {}
        _error = ""
        try:
            result = await self.scrape_thread()
            n_video_urls, n_image_urls = [], []
            for url in result.get("videos", []):
                n_video_urls.append(await shorten_url(url))
            for url in result.get("images", []):
                n_image_urls.append(await shorten_url(url))
            r = {
                "error": f"",
                "video_urls": n_video_urls,
                "image_urls": n_image_urls,
                "text": f"by <b>@<a href='{self.url}'>{escape(result.get('username'))}</a></b>👇🏻"+
                        f"<blockquote>{escape(result.get('text'))}</blockquote>"+
                        f"\n{result.get('link')}",
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
                    "text": f"by <b>@<a href='{self.url}'>{escape(self.username)}</a></b>",
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

    def _find_key(self, data, target):
        if isinstance(data, dict):
            for k, v in data.items():
                if k == target:
                    yield v
                elif isinstance(v, (dict, list)):
                    yield from self._find_key(v, target)
        elif isinstance(data, list):
            for item in data:
                yield from self._find_key(item, target)

    @staticmethod
    def _parse_thread(t: dict) -> dict:
        def filter_best_images(urls: list[str]) -> list[str]:
            best = []
            qualities: dict[str, dict[int, str]] = {}

            for url in urls:
                if "?stp=" not in url and "&stp=" not in url:
                    continue

                link_ = url.split("?")[0]
                key_part = url.split("?stp=")[1] if "?stp=" in url else url.split("&stp=")[1]
                key_part = key_part.split("&")[0]

                m_res = re.search(r"(\d{2,4})x(\d{2,4})", key_part)
                q = int(m_res.group(1)) if m_res else 9999

                ql = qualities.setdefault(link_, {})
                last_item = next(iter(ql.items()), (None, None))
                last_q, last_url = last_item
                if last_q is None or q > last_q:
                    if last_url in best:
                        best.remove(last_url)
                    ql[q] = url
                    best.append(url)

            return best

        post = t.get("post", {})
        user = post.get("user", {})
        images = [
                     c["url"]
                     for i in (post.get("carousel_media") or [])
                     for c in i.get("image_versions2", {}).get("candidates", [])
                 ] or []
        if images: images = filter_best_images(images)
        videos = [v["url"] for v in (post.get("video_versions") or [])]
        if not videos:
            videos = [
                v["url"] for v in ((post.get("text_post_app_info", {}) or {})
                    .get("linked_inline_media", {}) or {}).get("video_versions", [])
            ]
        link = ((post.get("text_post_app_info", {}) or {}).get("link_preview_attachment", {}) or {}).get("url", "")
        if link:
            link = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("u", [""])[0])

        return {
            "id": post.get("id"),
            "code": post.get("code"),
            "text": (post.get("caption", {}) or {}).get("text"),
            "link": link,
            "tag_name": ((post.get("text_post_app_info", {}) or {}).get("tag_header", {}) or {}).get("display_name", ""),
            "published_on": post.get("taken_at"),
            "username": user.get("username"),
            "user_pic": user.get("profile_pic_url"),
            "user_verified": user.get("is_verified"),
            "images": list(dict.fromkeys(images)),
            "videos": list(dict.fromkeys(videos))
        }

    async def scrape_thread(self) -> dict:
        async with semaphore:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(viewport={"width": 1280, "height": 720})
                page = await context.new_page()

                await page.goto(self.url, timeout=30000)
                # await page.wait_for_load_state("networkidle")
                await page.wait_for_selector("[data-pressable-container=true]", timeout=10000)

                html = await page.content()
                await browser.close()

                soup = BeautifulSoup(html, "html.parser")
                scripts = soup.find_all("script", {"type": "application/json", "data-sjs": True})

                for script in scripts:
                    text = script.string
                    if not text or 'thread_items' not in text:
                        continue
                    data_json = json.loads(text)
                    threads_items_groups = [
                        ti for ti in self._find_key(data_json, "thread_items")
                        if f"code': '{self.code}" in str(ti)
                    ]
                    threads_items = [
                        t for ti in threads_items_groups for t in ti
                        if f"code': '{self.code}" in str(t)
                    ]
                    if threads_items:
                        return self._parse_thread(threads_items[0])

                raise ValueError("thread data not found")
