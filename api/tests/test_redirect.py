from datetime import timedelta

from app import db
from app.cache import link_cache
from app.models import Link, utcnow

CHROME_ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"


def test_redirect_counts_click(client, make_link):
    link = make_link()
    response = client.get(f"/{link['short_code']}", headers={"User-Agent": CHROME_ANDROID, "Referer": "https://t.co/x"})
    assert response.status_code == 302
    assert response.headers["Location"] == "https://example.com/page"
    assert response.headers["Cache-Control"] == "no-store"

    assert client.get(f"/api/links/{link['id']}").get_json()["click_count"] == 1
    clicks = client.get(f"/api/analytics/links/{link['id']}/clicks").get_json()["clicks"]
    assert clicks[0]["device_type"] == "Mobile"
    assert clicks[0]["browser"] == "Chrome"
    assert clicks[0]["os"] == "Android"
    assert clicks[0]["referrer"] == "https://t.co/x"


def test_redirect_populates_cache_and_serves_from_it(client, make_link):
    link = make_link()
    client.get(f"/{link['short_code']}")
    assert link_cache.get(link["short_code"])["url"] == "https://example.com/page"

    # Change the row behind the cache's back: the cached URL is still served.
    db.session.get(Link, link["id"]).original_url = "https://changed.example.com"
    db.session.commit()
    assert client.get(f"/{link['short_code']}").headers["Location"] == "https://example.com/page"


def test_delete_invalidates_cache(client, make_link):
    link = make_link()
    client.get(f"/{link['short_code']}")
    assert client.delete(f"/api/links/{link['id']}").status_code == 204
    assert link_cache.get(link["short_code"]) is None
    assert client.get(f"/{link['short_code']}").status_code == 404


def test_deactivate_via_update_invalidates_cache(client, make_link):
    link = make_link()
    client.get(f"/{link['short_code']}")
    client.patch(f"/api/links/{link['id']}", json={"is_active": False})
    assert client.get(f"/{link['short_code']}").status_code == 404


def test_redirect_works_when_redis_is_down(client, make_link, monkeypatch):
    import redis

    link = make_link()

    def boom(*args, **kwargs):
        raise redis.ConnectionError("down")

    monkeypatch.setattr(link_cache.client, "get", boom)
    monkeypatch.setattr(link_cache.client, "setex", boom)
    assert client.get(f"/{link['short_code']}").status_code == 302


def test_expired_link_returns_410(client, make_link):
    link = make_link(expires_in_days=1)
    db.session.get(Link, link["id"]).expires_at = utcnow() - timedelta(minutes=1)
    db.session.commit()
    response = client.get(f"/{link['short_code']}")
    assert response.status_code == 410
    assert response.get_json()["error"] == "Link has expired"


def test_unknown_code_is_404(client):
    assert client.get("/doesnotexist").status_code == 404


def test_health_route_is_not_shadowed(client):
    assert client.get("/health").get_json()["status"] == "healthy"
