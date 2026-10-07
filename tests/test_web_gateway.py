import pytest
from starlette.testclient import TestClient

from telegram_v1.server.core import TelegramServer
from telegram_v1.web.portal import create_web_portal


@pytest.fixture
def client():
    server = TelegramServer()
    app = create_web_portal(server)
    return TestClient(app)


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_public_channels_and_seo(client):
    # Test JSON API
    response = client.get("/api/public/channels")
    assert response.status_code == 200
    channels = response.json()["channels"]
    assert any(c["name"] == "#announcements" for c in channels)

    # Test SEO HTML render
    html_resp = client.get("/channel/announcements")
    assert html_resp.status_code == 200
    assert "og:title" in html_resp.text
    assert "#announcements" in html_resp.text


def test_direct_payment_intent(client):
    payload = {
        "from_user": "jasper",
        "to_user": "salom",
        "amount": 75000,
        "currency": "UZS",
        "memo": "Test xarid",
    }
    response = client.post("/api/pay/intent", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["amount"] == 75000
    assert data["fee_percent"] == 0.0
    assert "inv-" in data["invoice_id"]


def test_pwa_client_html_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Telegram v2" in response.text
    assert "messagesContainer" in response.text
