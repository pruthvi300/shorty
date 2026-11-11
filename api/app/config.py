import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "mysql+pymysql://shorty:shorty_secret@localhost:3306/shorty")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    # Public base used to build short URLs, e.g. https://sho.rt
    BASE_URL = os.getenv("BASE_URL", "http://localhost:5000").rstrip("/")
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

    # Empty REDIS_URL disables caching; redirects then always read the database.
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    LINK_CACHE_TTL_SECONDS = int(os.getenv("LINK_CACHE_TTL_SECONDS", "3600"))

    # Set to 1 when running behind one reverse proxy so request.remote_addr is the client IP.
    TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "0"))
