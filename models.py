from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from connections import Base


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


# ==================== BRANCH MODEL ====================
class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

    routers = relationship(
        "Router",
        back_populates="branch",
        cascade="all, delete-orphan"
    )


# ==================== ROUTER MODEL ====================
class Router(Base):
    __tablename__ = "routers"

    id = Column(Integer, primary_key=True)
    ip_address = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)

    username = Column(String(50), nullable=False, default="admin")
    password = Column(String(100), nullable=False)
    port = Column(Integer, default=8728)

    branch = relationship("Branch", back_populates="routers")

    customers = relationship(
        "Customer",
        back_populates="router",
        cascade="all, delete-orphan"
    )


# ==================== CUSTOMER MODEL ====================
class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    ip_address = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)
    billing_amount = Column(Float, nullable=True)

    start_date = Column(DateTime, nullable=True)
    contract_date = Column(DateTime, nullable=True)

    # Legacy fields (keep)
    grace_days = Column(Integer, default=0, nullable=True)
    status = Column(String(50), default="active", nullable=True)
    popup_shown = Column(Boolean, default=False, nullable=True)
    pre_expiry_popup_shown = Column(Boolean, default=False, nullable=True)

    account_no = Column(String(50), unique=True, nullable=True)
    mikrotik_password = Column(String(100), nullable=True)

    manually_suspended = Column(Boolean, default=False, nullable=True)
    hold_status = Column(Boolean, default=False, nullable=True)
    activated_on = Column(DateTime, nullable=True)
    hold_until = Column(DateTime, nullable=True)

    router_id = Column(Integer, ForeignKey("routers.id"), nullable=True)
    router = relationship("Router", back_populates="customers")

    welcome_popup_last_shown = Column(Date, nullable=True)
    active_card_cycle_start = Column(Date, nullable=True)

    network = relationship(
        "CustomerNetwork",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan"
    )

    # ==================== NEW FIELDS (YOUR NEW FLOW) ====================

    # ✅ Daily GRACE: user must click on day 31/32/33 to browse THAT DAY
    grace_pass_date = Column(Date, nullable=True)

    # ✅ prevent popup spamming (show once per day)
    pre_expiry_popup_last_shown = Column(Date, nullable=True)   # day 25–30
    grace_offer_popup_last_shown = Column(Date, nullable=True)  # day 31–33
    suspended_popup_last_shown = Column(Date, nullable=True)    # optional


# ==================== CUSTOMER NETWORK MODEL ====================
class CustomerNetwork(Base):
    __tablename__ = "customer_network"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, unique=True)

    cable_no = Column(String(50))
    cable_type = Column(String(50))
    loop_no = Column(String(50))
    splitter = Column(String(50))
    tube_no = Column(String(50))
    core_used = Column(String(50))

    final_coordinates = Column(String(50))
    power_level = Column(String(50))
    coordinates = Column(String(255))

    customer = relationship("Customer", back_populates="network")
