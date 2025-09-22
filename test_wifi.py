import pytest
from datetime import datetime, timedelta
from app import app, SessionLocal, Customer

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def setup_db():
    """Clean DB before each test"""
    db = SessionLocal()
    db.query(Customer).delete()
    db.commit()
    db.close()
    yield

def create_customer(**kwargs):
    """Helper to create test customers"""
    db = SessionLocal()
    customer = Customer(
        name=kwargs.get("name", "Test User"),
        phone=kwargs.get("phone", "123456789"),
        email=kwargs.get("email", "test@example.com"),
        location=kwargs.get("location", "Nairobi"),
        ip_address=kwargs.get("ip_address", "192.168.1.100"),
        billing_amount=kwargs.get("billing_amount", 100.0),
        start_date=kwargs.get("start_date", datetime.utcnow()),
        end_date=kwargs.get("end_date", datetime.utcnow() + timedelta(days=30)),
        grace_days=kwargs.get("grace_days", 0),
        status=kwargs.get("status", "active"),
        popup_shown=kwargs.get("popup_shown", 0),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    db.close()
    return customer

# ---------------------- TEST CASES ----------------------

def test_active_subscription(client):
    customer = create_customer(start_date=datetime.utcnow())
    resp = client.get(f"/wifi_access/{customer.ip_address}")
    assert b"Your WiFi subscription is active." in resp.data

def test_grace_redirects_to_popup(client):
    customer = create_customer(
        start_date=datetime.utcnow() - timedelta(days=31),
        grace_days=3,
        popup_shown=0
    )
    resp = client.get(f"/wifi_access/{customer.ip_address}", follow_redirects=False)
    # Should redirect to grace_popup
    assert resp.status_code == 302
    assert f"/grace_popup/{customer.ip_address}" in resp.headers["Location"]

def test_grace_with_popup_shown(client):
    customer = create_customer(
        start_date=datetime.utcnow() - timedelta(days=31),
        grace_days=3,
        popup_shown=1
    )
    resp = client.get(f"/wifi_access/{customer.ip_address}")
    assert b"Your subscription has expired. Please select a grace period below." in resp.data

def test_suspended_subscription(client):
    customer = create_customer(
        start_date=datetime.utcnow() - timedelta(days=40),
        grace_days=3,
        popup_shown=1
    )
    resp = client.get(f"/wifi_access/{customer.ip_address}")
    assert b"Your WiFi is suspended. Please contact admin to reset your subscription." in resp.data

def test_invalid_ip(client):
    resp = client.get("/wifi_access/255.255.255.255")
    assert resp.status_code == 404
    assert b"Customer not found" in resp.data

def test_grace_popup_form_submission(client):
    customer = create_customer(
        start_date=datetime.utcnow() - timedelta(days=31),
        grace_days=0,
        popup_shown=0
    )
    resp = client.post(
        f"/grace_popup/{customer.ip_address}",
        data={"grace_days": "2"},
        follow_redirects=True
    )
    assert b"Grace period selected: 2 day(s)" in resp.data
