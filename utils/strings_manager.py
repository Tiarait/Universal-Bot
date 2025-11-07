import json
import os
import re
import traceback

from .redis_utils import RedisClient

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))  # path to .utils
BOT_ROOT = os.path.abspath(os.path.join(ROOT_DIR, ".."))
DIR_STRINGS = os.path.join(BOT_ROOT, "data", "strings")

class StringsManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # cls._instance._init(*args, **kwargs)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.strings_by_lang = {}
        self.redis = RedisClient()
        self.load_all_strings()

    def load_all_strings(self):
        def load_file(f_path: str, f_lang: str | None):
            with open(f_path, "r", encoding="utf-8") as f:
                self.strings_by_lang.setdefault(f_lang, {}).update(json.load(f))

        for entry in os.listdir(DIR_STRINGS):
            path = os.path.join(DIR_STRINGS, entry)
            if os.path.isdir(path):
                for f_name in os.listdir(path):
                    file_path = os.path.join(path, f_name)
                    if f_name == "strings.json":
                        load_file(file_path, None)
                    elif f_name.startswith("strings_") and f_name.endswith(".json"):
                        lang = f_name.split("_")[1].split(".")[0]
                        load_file(file_path, lang)

        for f_name in os.listdir(DIR_STRINGS):
            file_path = os.path.join(DIR_STRINGS, f_name)
            if f_name == "strings.json":
                load_file(file_path, None)
            elif f_name.startswith("strings_") and f_name.endswith(".json"):
                lang = f_name.split("_")[1].split(".")[0]
                load_file(file_path, lang)

    def get_cur_lang(self, user_id=None) -> str:
        return self.redis.get_user_lang(user_id) if user_id else None

    def get(self, key: str, user_id=None, *args, **kwargs):
        return self.get_with_lang(key, user_id, None, *args, **kwargs)

    def get_with_lang(self, key: str, user_id=None, lang: str = None, *args, **kwargs):
        if not key: return ""
        if not lang:
            lang = self.redis.get_user_lang(user_id) if user_id else None
        text = self.strings_by_lang.get(lang, {}).get(key)
        if text is None:
            text = self.strings_by_lang.get(None, {}).get(key, f"[!{key}]")
        if args or kwargs:
            try:
                def repl(m):
                    idx = int(m.group(1)) - 1
                    if idx < len(args):
                        return str(args[idx])
                    return m.group(0)

                text = re.sub(r"%(\d+)\$[sd]", repl, text)
                if "%" in text:
                    text = text % args if args else text % kwargs
            except Exception:
                traceback.print_exc()
        return text
