from app.utils import parse_user_agent


def test_link_analytics(client, make_link):
    link = make_link()
    for _ in range(3):
        client.get(f"/{link['short_code']}", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Firefox/120.0"})

    body = client.get(f"/api/analytics/links/{link['id']}?days=9999").get_json()
    assert body["period_days"] == 365
    assert body["total_clicks"] == 3
    assert sum(day["count"] for day in body["clicks_by_day"]) == 3
    assert body["device_breakdown"] == [{"device": "Desktop", "count": 3}]
    assert body["browser_breakdown"] == [{"browser": "Firefox", "count": 3}]
    assert body["top_referrers"] == []


def test_summary(client, make_link):
    a = make_link()
    make_link()
    client.get(f"/{a['short_code']}")
    body = client.get("/api/analytics/summary").get_json()
    assert body["total_links"] == 2
    assert body["total_clicks"] == 1
    assert body["clicks_today"] == 1
    assert body["top_links"][0]["id"] == a["id"]


def test_click_history_404_for_unknown_link(client):
    assert client.get("/api/analytics/links/42/clicks").status_code == 404


def test_user_agent_parsing():
    edge = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36 Edg/120.0"
    iphone = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile Safari/604.1"
    )
    ipad = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Safari/604.1"
    mac_chrome = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    assert parse_user_agent(edge) == {"device_type": "Desktop", "browser": "Edge", "os": "Windows"}
    assert parse_user_agent(iphone) == {"device_type": "Mobile", "browser": "Safari", "os": "iOS"}
    assert parse_user_agent(ipad) == {"device_type": "Tablet", "browser": "Safari", "os": "iOS"}
    assert parse_user_agent(mac_chrome) == {"device_type": "Desktop", "browser": "Chrome", "os": "macOS"}
    assert parse_user_agent("")["browser"] == "Unknown"
