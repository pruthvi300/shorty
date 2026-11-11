"""
The hot path: /<short_code> → 302 to the destination.

1. Look up the link in Redis; on a miss, read MySQL and populate Redis.
2. Return 404 for unknown/inactive links, 410 for expired ones.
3. Record the click and bump the counter with one atomic UPDATE.
"""

from datetime import datetime

from flask import Blueprint, abort, redirect, request
from sqlalchemy import select, update

from app import db
from app.cache import link_cache
from app.models import Click, Link, utcnow
from app.utils import get_location_from_ip, parse_user_agent

redirect_bp = Blueprint("redirect", __name__)


def _lookup(short_code):
    entry = link_cache.get(short_code)
    if entry is not None:
        return entry
    link = db.session.execute(
        select(Link).filter_by(short_code=short_code, is_active=True)
    ).scalar_one_or_none()
    if link is None:
        return None
    entry = link.cache_entry()
    link_cache.set(short_code, entry)
    return entry


@redirect_bp.get("/<string:short_code>")
def redirect_to_url(short_code):
    entry = _lookup(short_code)
    if entry is None:
        abort(404, "Link not found")
    if entry["expires_at"] and datetime.fromisoformat(entry["expires_at"]) <= utcnow():
        abort(410, "Link has expired")

    record_click(entry["id"])
    db.session.execute(update(Link).where(Link.id == entry["id"]).values(click_count=Link.click_count + 1))
    db.session.commit()

    response = redirect(entry["url"], code=302)
    # Don't let browsers cache the redirect, or repeat visits would not be counted.
    response.headers["Cache-Control"] = "no-store"
    return response


def record_click(link_id):
    user_agent = request.headers.get("User-Agent", "")
    ua_info = parse_user_agent(user_agent)
    ip_address = request.remote_addr
    location = get_location_from_ip(ip_address)
    db.session.add(
        Click(
            link_id=link_id,
            ip_address=ip_address,
            user_agent=user_agent[:1000] or None,
            referrer=(request.referrer or "")[:2048] or None,
            device_type=ua_info["device_type"],
            browser=ua_info["browser"],
            os=ua_info["os"],
            country=location["country"],
            city=location["city"],
        )
    )
