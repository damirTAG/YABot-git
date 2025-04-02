from cachetools import TTLCache

class Base:
    def __init__(self):
        self.soundcloud   = TTLCache(maxsize=1000, ttl=600)
        self.yandexmusic  = TTLCache(maxsize=1000, ttl=600)

    def add_to_cache(self, cache_name: str, key: str, value):
        cache: dict = getattr(self, cache_name, None)
        if cache is not None:
            cache[key] = value

    def get_from_cache(self, cache_name: str, key: str):
        cache: dict = getattr(self, cache_name, None)
        return cache.get(key) if cache is not None else None

    def clear_cache(self, cache_name: str):
        cache: dict = getattr(self, cache_name, None)
        if cache is not None:
            cache.clear()
