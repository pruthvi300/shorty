"""
Redis cache-aside for the redirect path.

Only the data needed to redirect is cached: link id, destination URL and
expiry. Redis failures are logged and treated as cache misses, so the
service keeps working (slower) when Redis is down.
"""

import json
import logging

import redis

log = logging.getLogger(__name__)


class LinkCache:
    def __init__(self):
        self.client = None
        self.ttl = 3600

    def init_app(self, app):
        self.ttl = app.config["LINK_CACHE_TTL_SECONDS"]
        url = app.config.get("REDIS_URL")
        self.client = (
            redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.25, socket_connect_timeout=0.25)
            if url
            else None
        )

    @staticmethod
    def _key(short_code):
        return f"link:{short_code}"

    def get(self, short_code):
        if self.client is None:
            return None
        try:
            raw = self.client.get(self._key(short_code))
        except redis.RedisError:
            log.warning("Redis unavailable, reading %s from the database", short_code)
            return None
        return json.loads(raw) if raw else None

    def set(self, short_code, entry):
        if self.client is None:
            return
        try:
            self.client.setex(self._key(short_code), self.ttl, json.dumps(entry))
        except redis.RedisError:
            log.warning("Redis unavailable, could not cache %s", short_code)

    def delete(self, short_code):
        if self.client is None:
            return
        try:
            self.client.delete(self._key(short_code))
        except redis.RedisError:
            # A stale entry expires after the TTL; log loudly because it may serve a deleted link until then.
            log.error("Redis unavailable, could not invalidate %s", short_code)


link_cache = LinkCache()
