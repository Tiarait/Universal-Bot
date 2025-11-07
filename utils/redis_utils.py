import redis

from .logging_utils import setup_temp_logger
from .utils import in_docker

class RedisClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init(*args, **kwargs)
        return cls._instance

    def _init(self, host="", port=6379, db=0, logger=None):
        from_docker = in_docker()
        self.stop_flag = False
        # self.host = host or ("redis" if from_docker else "localhost")
        self.host = host or "localhost"
        self.port = port
        self.db = db
        self.logger = logger or setup_temp_logger('RedisClient')
        # if not from_docker and not self.is_redis_running():
        #     self.start_redis()
        # self.redis = redis.StrictRedis(host=host, port=port, db=db, decode_responses=True)
        self.is_redis_running()
        self.pubsub = self.redis.pubsub()
        self.user_lang_cache = {}

    def is_redis_running(self) -> bool:
        try:
            self.redis = redis.StrictRedis(host=self.host, port=self.port, db=self.db, decode_responses=True)
            self.redis.ping()
            return True
        except Exception as e:
            self.logger.error(f"Cant run Redis [{self.host}:{self.port}]: {e}")
            return False

    # def start_redis(self):
    #     try:
    #         subprocess.Popen(['redis-server'])
    #         time.sleep(2)
    #         self.logger.info(f"Redis server running. [{self.host}:{self.port}]")
    #     except Exception as e:
    #         self.logger.error(f"Cant run Redis [{self.host}:{self.port}]: {e}")

    def get(self, key, default=None):
        return self.redis.get(key) or default

    def set(self, key, value, ex=None):
        self.redis.set(key, value, ex=ex)

    # -----------------

    def get_user_lang(self, user_id):
        lang = self.user_lang_cache.get(user_id)
        if lang is not None:
            return lang
        lang = self.redis.get(f"user:{user_id}:lang")
        self.user_lang_cache[user_id] = lang
        return lang

    def set_user_lang(self, user_id, lang: str):
        self.redis.set(f"user:{user_id}:lang", lang)
        self.user_lang_cache[user_id] = lang
        return lang