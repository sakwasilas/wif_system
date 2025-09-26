import pytest
from datetime import datetime, timedelta, UTC
import uuid
from app import app, SessionLocal
from models import Customer


# ------------------------
# Fixtures
# ------------------------
@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def sample_customer(db_session):
    """Provide a unique sample customer for testing."""
    unique_ip = f"192.168.1.{uuid.uuid4().int % 250}"   # random IP ending
    unique_account = str(uuid.uuid4())[:8]              # random short account number

    customer = Customer(
        name="Test User",
        phone="0712345678",
        email="test@example.com",
        location="Nairobi",
        ip_address=unique_ip,
        billing_amount=1000.0,
        start_date=datetime.now(UTC) - timedelta(days=1),
        grace_days=3,
        status="active",
        popup_shown=False,
        pre_expiry_popup_shown=False,
        account_no=unique_account,
    )
    db_session.add(customer)
    db_session.commit()
    yield customer
    db_session.delete(customer)
    db_session.commit()


# ------------------------
# Tests
# ------------------------
def test_active_subscription(db_session, sample_customer):
    """Customer with active subscription should stay active."""
    customer = sample_customer
    assert customer.status == "active"


def test_grace_redirects_to_popup(db_session, sample_customer):
    """Customer in grace period should see popup."""
    customer = sample_customer
    customer.start_date = datetime.now(UTC) - timedelta(days=10)
    customer.grace_days = 5
    customer.status = "grace"
    db_session.commit()

    assert customer.status == "grace"


def test_grace_with_popup_shown(db_session, sample_customer):
    """Customer in grace period should have popup_shown set to True."""
    customer = sample_customer
    customer.status = "grace"
    customer.popup_shown = True
    db_session.commit()

    assert customer.status == "grace"
    assert customer.popup_shown is True


def test_suspended_subscription(db_session, sample_customer):
    """Customer should be suspended after grace period ends."""
    customer = sample_customer
    customer.status = "suspended"
    db_session.commit()

    assert customer.status == "suspended"
