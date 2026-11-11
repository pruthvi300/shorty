import fakeredis
import pytest

from app import create_app, db
from app.cache import link_cache


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "BASE_URL": "https://sho.rt",
        }
    )
    link_cache.client = fakeredis.FakeRedis(decode_responses=True)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_link(client):
    def _make(url="https://example.com/page", **extra):
        response = client.post("/api/links", json={"url": url, **extra})
        assert response.status_code == 201, response.get_json()
        return response.get_json()

    return _make
