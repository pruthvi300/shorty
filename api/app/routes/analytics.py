"""Analytics endpoints. Aggregates are computed on read from the clicks table."""

from datetime import timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select

from app import db
from app.models import Click, Link, utcnow

analytics_bp = Blueprint("analytics", __name__)

MAX_DAYS = 365


def _breakdown(column, link_id, since, limit=None, skip_null=False):
    query = (
        select(column, func.count(Click.id).label("count"))
        .where(Click.link_id == link_id, Click.clicked_at >= since)
        .group_by(column)
        .order_by(func.count(Click.id).desc())
    )
    if skip_null:
        query = query.where(column.isnot(None))
    if limit:
        query = query.limit(limit)
    return db.session.execute(query).all()


@analytics_bp.get("/links/<int:link_id>")
def get_link_analytics(link_id):
    """Query param `days` (1-365, default 7) sets the window."""
    link = db.get_or_404(Link, link_id)
    days = min(max(request.args.get("days", 7, type=int), 1), MAX_DAYS)
    since = utcnow() - timedelta(days=days)

    total_clicks = db.session.scalar(
        select(func.count(Click.id)).where(Click.link_id == link_id, Click.clicked_at >= since)
    )
    day = func.date(Click.clicked_at)
    clicks_by_day = db.session.execute(
        select(day.label("date"), func.count(Click.id).label("count"))
        .where(Click.link_id == link_id, Click.clicked_at >= since)
        .group_by(day)
        .order_by(day)
    ).all()

    return jsonify(
        {
            "link": link.to_dict(),
            "period_days": days,
            "total_clicks": total_clicks,
            "clicks_by_day": [{"date": str(row.date), "count": row.count} for row in clicks_by_day],
            "top_referrers": [
                {"referrer": r, "count": c} for r, c in _breakdown(Click.referrer, link_id, since, 5, skip_null=True)
            ],
            "device_breakdown": [
                {"device": d or "Unknown", "count": c} for d, c in _breakdown(Click.device_type, link_id, since)
            ],
            "browser_breakdown": [
                {"browser": b or "Unknown", "count": c} for b, c in _breakdown(Click.browser, link_id, since, 5)
            ],
            "country_breakdown": [
                {"country": c_, "count": c}
                for c_, c in _breakdown(Click.country, link_id, since, 10, skip_null=True)
            ],
        }
    )


@analytics_bp.get("/summary")
def get_summary():
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    top_links = db.session.scalars(
        select(Link).filter_by(is_active=True).order_by(Link.click_count.desc(), Link.id.desc()).limit(5)
    ).all()
    return jsonify(
        {
            "total_links": db.session.scalar(select(func.count(Link.id)).where(Link.is_active.is_(True))),
            "total_clicks": db.session.scalar(select(func.count(Click.id))),
            "clicks_today": db.session.scalar(select(func.count(Click.id)).where(Click.clicked_at >= today_start)),
            "top_links": [link.to_dict() for link in top_links],
        }
    )


@analytics_bp.get("/links/<int:link_id>/clicks")
def get_click_history(link_id):
    db.get_or_404(Link, link_id)
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)
    pagination = db.paginate(
        select(Click).filter_by(link_id=link_id).order_by(Click.clicked_at.desc(), Click.id.desc()),
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return jsonify(
        {
            "clicks": [c.to_dict() for c in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
        }
    )
