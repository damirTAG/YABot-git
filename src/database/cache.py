from cachetools import TTLCache
import logging

logger = logging.getLogger(__name__)

class Base:
    def __init__(self):
        self.soundcloud = TTLCache(maxsize=1000, ttl=600)
        self.yandexmusic = TTLCache(maxsize=1000, ttl=600)

    def add_to_cache(self, cache_name: str, key: str, value):
        cache = getattr(self, cache_name, None)
        if cache is not None:
            cache[key] = value
            # logger.info(f"Added to cache: {cache_name} - {key}: {value}")
        else:
            logger.error(f"Cache {cache_name} not found")

    def get_from_cache(self, cache_name: str, key: str):
        cache = getattr(self, cache_name, None)
        if cache is not None:
            cached_value = cache.get(key)
            # if cached_value:
            #     logger.info(f"Cache hit for {cache_name} - {key}: {cached_value}")
            # else:
            #     logger.info(f"Cache miss for {cache_name} - {key}")
            return cached_value
        else:
            logger.error(f"Cache {cache_name} not found")
            return None

    def clear_cache(self, cache_name: str):
        cache = getattr(self, cache_name, None)
        if cache is not None:
            cache.clear()
            logger.info(f"Cache {cache_name} cleared")
        else:
            logger.error(f"Cache {cache_name} not found")

cache = Base()
