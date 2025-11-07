import re
import ssl
import urllib.parse

import aiohttp
import certifi


def normalize_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    return url

def is_threads_link(link: str) -> bool:
    pattern = re.compile(r"(https?://)?(www\.)?threads\.net|threads\.com/.+?/post/[A-Za-z0-9_-]+")
    return bool(pattern.search(link))

def is_tiktok_link(link: str) -> bool:
    _pattern = r'(https?://)?((?:vm|vt|www)\.)?tiktok\.com/.*'
    return bool(re.match(_pattern, link))

def is_instagram_link(link: str) -> bool:
    _pattern = r'(https?://)?(www\.)?instagram\.com/(p|reel)/.+'
    # _pattern = r'(https?://)?(www\.)?instagram\.com/reel/.+'
    return bool(re.match(_pattern, link))

def is_youtube_link(link: str) -> bool:
    _pattern = r'(https?://)?(www\.)?youtube\.com/(shorts/|watch?).+'
    return bool(re.match(_pattern, link))


async def shorten_url(url: str) -> str:
    try:
        encoded = urllib.parse.quote_plus(url)
        api = f"https://is.gd/create.php?format=simple&url={encoded}"
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(api, ssl=ssl_context) as resp:
                if resp.status == 200:
                    return await resp.text()
                return url
    except Exception:
        return url