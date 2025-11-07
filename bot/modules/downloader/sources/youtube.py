import asyncio
import traceback
from html import escape

from yt_dlp import YoutubeDL

from ..utils import normalize_url, shorten_url


class YoutubeDownloader:
    def __init__(self, url: str):
        self.url = normalize_url(url)


    async def fetch(self) -> dict:
        r = {}
        _error = ""

        if not r:
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self._get_ydl)
                n_video_urls = []
                for url in result.get("video_urls", []):
                    n_video_urls.append(await shorten_url(url))
                r = {
                    "error": f"",
                    "video_urls": n_video_urls,
                    "image_urls": result.get("image_urls", []),
                    "video_file_path": result.get("video_file_path", ""),
                    "text": f"by <b>@<a href='{self.url}'>{escape(result.get('username', 'unknown'))}</a></b>👇🏻" +
                            f"<blockquote>{escape(result.get('text', ''))}</blockquote>",
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
        # filename = self.url.strip("/")
        # if "?" in filename: filename = filename.split("?")[0].strip("/")
        # if "/" in filename: filename = filename.split("/")[-1]
        # if "?" in filename: filename = filename.split("?")[0]
        # output_path = os.path.join(".temp", f"{filename}.mp4")

        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'noplaylist': True
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                # ydl.download([self.url])

                username = info.get("uploader_id").replace("@", "").strip()
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

