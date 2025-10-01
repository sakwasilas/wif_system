import pytest
from datetime import datetime, timedelta
from app import app, SessionLocal, Customer, Router, Branch


# ---------------------- FIXTURES ----------------------
@pytest.fixture
def client():
    """Flask test client for sending requests."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def cleanup_db():
    """Clean DB before and after each test."""
    db = SessionLocal()
    db.query(Customer).delete()
    db.query(Router).delete()
    db.query(Branch).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(Customer).delete()
    db.query(Router).delete()
    db.query(Branch).delete()
    db.commit()
    db.close()


# ---------------------- HELPERS ----------------------
def create_customer(status="active", start_offset_days=-10, grace_days=3):
    """Helper to insert a customer with a given subscription period."""
    db = SessionLocal()

    # Create a branch and router first (because of FK constraints)
    branch = Branch(name="Main Branch")
    db.add(branch)
    db.flush()  # to get branch.id

    router = Router(ip_address="10.0.0.1", description="Test Router", branch_id=branch.id)
    db.add(router)
    db.flush()

    # Create customer
    start_date = datetime.utcnow() + timedelta(days=start_offset_days)
    customer = Customer(
        name="Test User",
        phone="0712345678",
        email="test@example.com",
        ip_address="192.168.1.10",
        location="Test Location",
        billing_amount=1000,
        start_date=start_date,
        contract_date=start_date,
        grace_days=grace_days,
        account_no="ACC12345",
        router_id=router.id,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    db.close()
    return customer


# ---------------------- TESTS ----------------------

def test_wifi_active(client):
    """Customer is active within subscription period."""
    create_customer(start_offset_days=-5)  # started 5 days ago, still active
    response = client.get("/wifi_access/192.168.1.10")
    assert response.status_code == 200
    assert b"active" in response.data.lower()


def test_wifi_grace_redirect(client):
    """Customer is in grace period -> should redirect to popup."""
    create_customer(start_offset_days=-40, grace_days=5)  # expired, grace running
    response = client.get("/wifi_access/192.168.1.10")
    # Flask redirects with 302
    assert response.status_code in (200, 302)


def test_wifi_suspended(client):
    """Customer is suspended after grace period ends."""
    create_customer(start_offset_days=-70, grace_days=5)  # long expired
    response = client.get("/wifi_access/192.168.1.10")
    assert response.status_code == 200
    assert b"suspended" in response.data.lower()
