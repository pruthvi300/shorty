"""Link CRUD endpoints."""

from datetime import timedelta

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import db
from app.cache import link_cache
from app.models import Link, generate_short_code, utcnow
from app.utils import normalise_url, validate_custom_code

links_bp = Blueprint("links", __name__)

GENERATE_ATTEMPTS = 5
MAX_EXPIRY_DAYS = 3650


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, "Request body must be a JSON object")
    return data


@links_bp.post("")
def create_link():
    """
    Body: {"url": "...", "title": "...", "custom_code": "...", "expires_in_days": 30}
    Only "url" is required.
    """
    data = _json_body()

    original_url = normalise_url(data.get("url"))
    if original_url is None:
        return jsonify({"error": "A valid http(s) URL is required"}), 400

    title = data.get("title")
    if title is not None and (not isinstance(title, str) or len(title) > 255):
        return jsonify({"error": "Title must be a string of at most 255 characters"}), 400

    expires_at = None
    if data.get("expires_in_days") is not None:
        days = data["expires_in_days"]
        if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= MAX_EXPIRY_DAYS:
            return jsonify({"error": f"expires_in_days must be an integer from 1 to {MAX_EXPIRY_DAYS}"}), 400
        expires_at = utcnow() + timedelta(days=days)

    custom_code = data.get("custom_code") or None
    if custom_code is not None:
        error = validate_custom_code(custom_code)
        if error:
            return jsonify({"error": error}), 400

    # The unique index is the source of truth: retry generated codes on collision,
    # and report a taken custom code as a conflict (covers concurrent requests too).
    attempts = 1 if custom_code else GENERATE_ATTEMPTS
    for _ in range(attempts):
        link = Link(
            original_url=original_url,
            title=title,
            short_code=custom_code or generate_short_code(),
            expires_at=expires_at,
        )
        db.session.add(link)
        try:
            db.session.commit()
            return jsonify(link.to_dict()), 201
        except IntegrityError:
            db.session.rollback()

    if custom_code:
        return jsonify({"error": "Custom code already in use"}), 409
    return jsonify({"error": "Could not generate a unique short code, please retry"}), 503


@links_bp.get("")
def list_links():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

    pagination = db.paginate(
        select(Link).filter_by(is_active=True).order_by(Link.created_at.desc(), Link.id.desc()),
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return jsonify(
        {
            "links": [link.to_dict() for link in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages,
        }
    )


@links_bp.get("/<int:link_id>")
def get_link(link_id):
    return jsonify(db.get_or_404(Link, link_id).to_dict())


@links_bp.route("/<int:link_id>", methods=["PATCH", "PUT"])
def update_link(link_id):
    """Body: {"title": "...", "is_active": true|false}. Both optional."""
    link = db.get_or_404(Link, link_id)
    data = _json_body()

    if "title" in data:
        title = data["title"]
        if title is not None and (not isinstance(title, str) or len(title) > 255):
            return jsonify({"error": "Title must be a string of at most 255 characters"}), 400
        link.title = title
    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            return jsonify({"error": "is_active must be true or false"}), 400
        link.is_active = data["is_active"]

    db.session.commit()
    link_cache.delete(link.short_code)
    return jsonify(link.to_dict())


@links_bp.delete("/<int:link_id>")
def delete_link(link_id):
    """Soft delete: the link stops redirecting but its analytics are kept."""
    link = db.get_or_404(Link, link_id)
    link.is_active = False
    db.session.commit()
    link_cache.delete(link.short_code)
    return "", 204
