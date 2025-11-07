import asyncio
import os
import re
import io
import tempfile

from moviepy.video.io.VideoFileClip import VideoFileClip

TMP_DIR = os.path.join(".temp")

def highlight_html(_text: str, _query: str, tag:str = None) -> str:
    if not _text: return ""
    if not tag: tag = "b"
    pattern = re.escape(_query)
    return re.sub(pattern, f"<{tag}>{_query}</{tag}>", _text, flags=re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    if not text: return []
    pattern = re.compile(
        r"(?:https?://|www\.)\S+|[a-zA-Z0-9-]+\.[a-zA-Z]{2,10}/\S*"
    )
    return [u.rstrip(".,)") for u in pattern.findall(text)]


def in_docker():
    if os.path.exists('/.dockerenv'):
        return True
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read() or "containerd" in f.read()
    except FileNotFoundError:
        return False

async def video_to_audio_bytes(video_bytes: bytes, audio_format="mp3", name: str = None) -> io.BytesIO:
    loop = asyncio.get_event_loop()
    out_buffer = io.BytesIO()

    def _extract_audio(tmp_video_path: str):
        with VideoFileClip(tmp_video_path) as clip:
            with tempfile.NamedTemporaryFile(dir=TMP_DIR, suffix=f".{audio_format}", delete=True) as tmp_audio:
                clip.audio.write_audiofile(tmp_audio.name, fps=44100, codec=audio_format, write_logfile=False)
                tmp_audio.seek(0)
                out_buffer.write(tmp_audio.read())
        out_buffer.seek(0)

    with tempfile.NamedTemporaryFile(dir=TMP_DIR, suffix=".mp4", delete=True) as tmp_video:
        tmp_video.write(video_bytes)
        tmp_video.flush()
        await loop.run_in_executor(None, _extract_audio, tmp_video.name)
    if not name: name = "audio"
    out_buffer.name = f"{name}.{audio_format}"
    return out_buffer