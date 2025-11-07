import ssl
import traceback
from itertools import cycle

import aiohttp
import certifi

from utils import load_keys


async def apifreellm_com(msg: str) -> dict:
    api_url = f"https://apifreellm.com/api/chat"
    result = {"error": "", "message": ""}
    msg = msg.replace("\n\n", "\n").strip()
    msg += f"\n[text format with emoji]"
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(api_url, ssl=ssl_context, json={"message": msg}) as resp:
                if resp.status != 200:
                    result["error"] = f"HTTP {resp.status}"
                    return result
                try:
                    data = await resp.json()
                except Exception:
                    result["error"] = "Invalid JSON response"
                    return result
        if "error" in data:
            result["error"] = data["error"]
            return result
        if "response" in data:
            result["message"] = data["response"]
    except Exception as e:
        result["error"] = str(e)
    return result

_free_cerebras_key = cycle(load_keys("CEREBRAS_TOKENS"))
def get_cerebras_key() -> int:
    return next(_free_cerebras_key)

async def cerebras_ai(msgs: list[str], user, lang: str = None, is_help: bool = False) -> dict:
    is_help = True # TODO
    api_url = f"https://api.cerebras.ai/v1/chat/completions"
    # if utils.in_docker():
    #     # api_url = f"http://host.docker.internal:8000/chat"
    #     api_url = f"http://127.0.0.1:8000/chat"
    # else:
    #     api_url = f"http://127.0.0.1:8000/chat"
    result = {"error": "", "message": ""}
    key = get_cerebras_key()
    if not key:
        result["error"] = "Invalid API key"
        return result
    if not is_help:
        msgs[-1] += f"\n[short respond in text format with emoji, not show adult content]"
    messages = []
    if is_help:
        is_help_str = (
                f"You manage friendly a Telegram bot - 'P.O.I.'. Answer in robot style. Think fast. " + "\n" +
                "It can: /help (commands list), /ai (its you), /dl (download media), /mp3 (extract audio), /math (math & solve), /id (show info), /circle (make circle video or video note), /voice (make voice from audio file). " + "\n" +
                "If the user wants to use a command — politely suggest /help_{en command} with a short description." + "\n" +
                "If just chatting — reply naturally." + "\n" +
                "If unsure or can’t do — kindly recommend checking /help." + "\n" +
                "Always respond shortly in text format with emojis, not show adult content."
        )
        messages.append(
            {"role": "system", "content": is_help_str}
        )
    for msg in msgs:
        if not msg: continue
        messages.append(
            {"role": f"user", "content": msg.replace("\n\n", "\n").strip()}
        )

    messages[-1]["content"] += f"\n(use {lang})"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    }
    payload = {
        # "model": "llama3.1-8b",
        "model": "qwen-3-235b-a22b-instruct-2507",
        "stream": False,
        "messages": messages,
        "user": str(user),
        "temperature": 0.7,
        "seed": -1
    }
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(
                    api_url, json=payload, headers=headers, ssl=ssl_context,
            ) as resp:
                data = {"error": ""}
                if resp.status != 200:
                    data["error"] = f"HTTP {resp.status}"
                else:
                    try:
                        data = await resp.json()
                    except Exception:
                        data["error"] = "Invalid JSON response"
        if "error" in data and data["error"]:
            result["error"] = data["error"]
            return result
        choices = data.get("choices", []) or []

        if choices:
            result["message"] = choices[0].get("message", {}).get("content")
    except Exception as e:
        result["error"] = str(e)
        traceback.print_exc()
    return result