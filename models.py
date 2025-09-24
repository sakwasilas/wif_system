from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from connections import Base
from datetime import datetime, UTC

# ==================== USER MODEL ====================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    security_question = Column(String(255))
    security_answer = Column(String(255))
    is_active = Column(Boolean, default=False)
    role = Column(String(50), default="user")


# ==================== CUSTOMER MODEL ====================
class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    email = Column(String(255))
    location = Column(String(255))
    ip_address = Column(String(50), nullable=False, unique=True)
    billing_amount = Column(Float, nullable=False)
    start_date = Column(DateTime, default=lambda: datetime.now(UTC))
    grace_days = Column(Integer, default=0)
    status = Column(String(50), default="active")
    popup_shown = Column(Boolean, default=False)
    pre_expiry_popup_shown = Column(Boolean, default=False)  # ✅ New column
    account_no = Column(String(50), nullable=False, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # One-to-one relationship with network info
    network = relationship("CustomerNetwork", back_populates="customer", uselist=False)


# ==================== CUSTOMER NETWORK MODEL ====================
class CustomerNetwork(Base):
    __tablename__ = "customer_network"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, unique=True)
    cable_no = Column(String(50))
    router_no = Column(String(50))
    loop_no = Column(String(50))
    power_level = Column(String(50))
    # signal_strength = Column(String(50))
    coordinates = Column(String(255))

    # Back reference to customer
    customer = relationship("Customer", back_populates="network")
