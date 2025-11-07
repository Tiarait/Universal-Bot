import os

from dotenv import load_dotenv


load_dotenv()

def load_keys(*env_keys) -> list:
    all_keys = []
    for key in env_keys:
        if isinstance(key, (list, tuple)):
            all_keys.extend(load_keys(*key))
        else:
            if value := os.getenv(key, ""):
                split_keys = [k.strip() for k in value.split(",")]
                all_keys.extend(split_keys)
    return all_keys

def load_key(key: str) -> str:
    return os.getenv(key, "")