from datetime import datetime, timezone

import shortuuid
from flask import current_app

from app import db


def utcnow():
    """Naive UTC timestamp (MySQL DATETIME has no time zone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_short_code(length=8):
    return shortuuid.ShortUUID().random(length=length)


class Link(db.Model):
    __tablename__ = "links"

    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    original_url = db.Column(db.Text, nullable=False)
    title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # Denormalised counter for the dashboard; incremented atomically in SQL.
    click_count = db.Column(db.Integer, default=0, nullable=False)

    clicks = db.relationship("Click", back_populates="link", lazy="select", passive_deletes=True)

    def is_expired(self, now=None):
        return self.expires_at is not None and self.expires_at <= (now or utcnow())

    def cache_entry(self):
        return {
            "id": self.id,
            "url": self.original_url,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    def to_dict(self):
        return {
            "id": self.id,
            "short_code": self.short_code,
            "short_url": f"{current_app.config['BASE_URL']}/{self.short_code}",
            "original_url": self.original_url,
            "title": self.title,
            "created_at": _iso(self.created_at),
            "expires_at": _iso(self.expires_at),
            "is_active": self.is_active,
            "click_count": self.click_count,
        }


class Click(db.Model):
    __tablename__ = "clicks"
    __table_args__ = (db.Index("ix_clicks_link_id_clicked_at", "link_id", "clicked_at"),)

    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey("links.id", ondelete="CASCADE"), nullable=False)
    clicked_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    referrer = db.Column(db.Text, nullable=True)

    device_type = db.Column(db.String(20), nullable=True)
    browser = db.Column(db.String(50), nullable=True)
    os = db.Column(db.String(50), nullable=True)

    country = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)

    link = db.relationship("Link", back_populates="clicks")

    def to_dict(self):
        return {
            "id": self.id,
            "link_id": self.link_id,
            "clicked_at": _iso(self.clicked_at),
            "device_type": self.device_type,
            "browser": self.browser,
            "os": self.os,
            "country": self.country,
            "city": self.city,
            "referrer": self.referrer,
        }


def _iso(value):
    # Stored values are naive UTC; mark them as UTC so browsers convert correctly.
    return value.isoformat() + "Z" if value else None
