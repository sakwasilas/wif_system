from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
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
    
    # One branch -> many routers
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

    # ===== New fields for MikroTik API =====
    username = Column(String(50), nullable=False, default="admin")
    password = Column(String(100), nullable=False)  # store hashed if needed
    port = Column(Integer, default=8728)            # API port, default 8728

    branch = relationship("Branch", back_populates="routers")

    # One router -> many customers
    customers = relationship(
        "Customer",
        back_populates="router",
        cascade="all, delete-orphan"
    )


# ==================== CUSTOMER MODEL ====================
class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    email = Column(String(255))
    ip_address = Column(String(50), nullable=False, unique=True)
    location = Column(String(255))
    billing_amount = Column(Float, nullable=False)
    start_date = Column(DateTime, nullable=True)
    contract_date = Column(DateTime, nullable=True)
    grace_days = Column(Integer, default=0)
    status = Column(String(50), default="active")
    popup_shown = Column(Boolean, default=False)
    pre_expiry_popup_shown = Column(Boolean, default=False)

    account_no = Column(String(50), nullable=False, unique=True)
    mikrotik_password = Column(String(100))

    # Manual control fields (new)
    is_suspended = Column(Boolean, default=False, nullable=False)       # admin suspended
    is_on_hold = Column(Boolean, default=False, nullable=False)         # admin put on hold
    hold_start_date = Column(DateTime, nullable=True)                   # when hold started
    last_activation_date = Column(DateTime, nullable=True)              # last activation time (for 30-day cycle)

    # Foreign key -> Router
    router_id = Column(Integer, ForeignKey("routers.id"))

    # Relationships
    router = relationship("Router", back_populates="customers")
    network = relationship(
        "CustomerNetwork",
        back_populates="customer",
        uselist=False,
        cascade="all, delete-orphan"
    )


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

    # Back reference to customer
    customer = relationship("Customer", back_populates="network")
