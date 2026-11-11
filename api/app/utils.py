"""Validation, user-agent parsing and IP geolocation helpers."""

import re
from urllib.parse import urlsplit

CUSTOM_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
# Paths owned by the app itself; a link with one of these codes could never be reached.
RESERVED_CODES = {"api", "health", "static", "admin", "login", "logout"}
MAX_URL_LENGTH = 2048


def normalise_url(raw):
    """
    Return a cleaned http(s) URL, or None if it is not acceptable.

    A missing scheme defaults to https. Other schemes (javascript:, data:,
    ftp:, ...) are rejected so a short link can only point at a web page.
    """
    if not isinstance(raw, str):
        return None
    url = raw.strip()
    if not url or len(url) > MAX_URL_LENGTH:
        return None
    if "://" not in url:
        url = "https://" + url
    if any(ch.isspace() for ch in url):
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname
        _ = parts.port  # raises ValueError for a malformed port
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not host:
        return None
    if "." not in host and host != "localhost":
        return None
    return url


def validate_custom_code(code):
    """Return an error message, or None if the code is acceptable."""
    if not isinstance(code, str) or not CUSTOM_CODE_RE.match(code):
        return "Custom code must be 3-32 characters: letters, digits, '-' or '_'"
    if code.lower() in RESERVED_CODES:
        return "That custom code is reserved"
    return None


def parse_user_agent(user_agent_string):
    """
    Very small user-agent classifier. Order matters: Edge and Opera include
    "chrome" in their UA, and Chrome includes "safari".
    """
    if not user_agent_string:
        return {"device_type": "Unknown", "browser": "Unknown", "os": "Unknown"}

    ua = user_agent_string.lower()

    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        device_type = "Tablet"
    elif "mobile" in ua or "iphone" in ua or "android" in ua:
        device_type = "Mobile"
    else:
        device_type = "Desktop"

    if "edg" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "firefox" in ua or "fxios" in ua:
        browser = "Firefox"
    elif "chrome" in ua or "crios" in ua:
        browser = "Chrome"
    elif "safari" in ua:
        browser = "Safari"
    else:
        browser = "Other"

    if "windows" in ua:
        os_name = "Windows"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "android" in ua:
        os_name = "Android"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    else:
        os_name = "Other"

    return {"device_type": device_type, "browser": browser, "os": os_name}


def get_location_from_ip(ip_address):
    """
    Placeholder geolocation. Plug in a local MaxMind GeoLite2 database here;
    avoid calling a remote API on the redirect path.
    """
    if ip_address in ("127.0.0.1", "localhost", "::1"):
        return {"country": "Local", "city": "Development"}
    return {"country": None, "city": None}
