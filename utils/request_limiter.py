import asyncio
import random
import string
from collections import defaultdict
from datetime import datetime, timedelta


class RequestLimiter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.rate_limits = defaultdict(lambda: timedelta(seconds=5))
        self.queues = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: asyncio.Queue())))
        self.queue_meta = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        self.last_request = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: datetime.min)))
        self.cleanup_interval = 300
        self.task_ids = {}

        asyncio.create_task(self.cleanup_loop())

    @staticmethod
    def _gen_task_id(length=5):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def set_rate_limit(self, name: str, seconds: int):
        self.rate_limits[name] = timedelta(seconds=seconds)


    async def run(self, name, proxy, user_id, coro, callback=None) -> str:
        task_id = self._gen_task_id()
        task = asyncio.create_task(coro)
        self.task_ids[task_id] = task

        q = self.queues[name][proxy][user_id]
        meta = self.queue_meta[name][proxy][user_id]
        await q.put((task_id, task, callback))
        meta.append(task_id)

        if not hasattr(q, "_processor_started"):
            asyncio.create_task(self._process_queue(name, proxy, user_id))
            q._processor_started = True

        return task_id

    async def _process_queue(self, name, proxy, user_id):
        async def try_callback(result_callback):
            try:
                await callback(result_callback)
            except Exception:
                pass

        q = self.queues[name][proxy][user_id]
        while not q.empty():
            now = datetime.now()
            last = self.last_request[name][proxy][user_id]
            if (now - last) < self.rate_limits[name]:
                await asyncio.sleep(0.5)
                continue

            task_id, task, callback = await q.get()
            self.last_request[name][proxy][user_id] = datetime.now()
            try:
                result = await task
                if callback: await try_callback(result)
            except Exception as e:
                if callback: await try_callback(e)
            finally:
                self.cancel_task(task_id)
                if q.empty():
                    self.queues[name][proxy].pop(user_id, None)
                    self.last_request[name][proxy].pop(user_id, None)

    def cancel_task(self, task_id: str) -> bool:
        task = self.task_ids.get(task_id)
        if not task:
            return False
        task.cancel()
        self.task_ids.pop(task_id, None)

        for name, proxies in self.queue_meta.items():
            for proxy, users in proxies.items():
                for user_id, meta in users.items():
                    if task_id in meta:
                        meta.remove(task_id)
                        q = self.queues[name][proxy][user_id]
                        try:
                            items = list(q._queue)
                            q._queue.clear()
                            for t in items:
                                if t is not task:
                                    q.put_nowait(t)
                        except Exception:
                            pass
        return True

    def get_queue_status(self, name, proxy, user_id):
        q = self.queues[name][proxy][user_id]
        size = q.qsize()
        return (0, 0) if size == 0 else (1, size)

    def get_task_position(self, task_id: str) -> tuple[int, int]:
        for name, proxies in self.queue_meta.items():
            for proxy, users in proxies.items():
                for user_id, meta in users.items():
                    if task_id in meta:
                        position = meta.index(task_id) + 1
                        total = len(meta)
                        return position, total
        return 0, 0

    async def cleanup_loop(self):
        while True:
            await self.cleanup()
            await asyncio.sleep(self.cleanup_interval)

    async def cleanup(self):
        now = datetime.now()
        for name, proxies in list(self.queues.items()):
            for proxy, users in list(proxies.items()):
                for user_id, q in list(users.items()):
                    last = self.last_request[name][proxy][user_id]
                    if q.empty() and (now - last).total_seconds() > self.cleanup_interval:
                        users.pop(user_id, None)
                        self.last_request[name][proxy].pop(user_id, None)
