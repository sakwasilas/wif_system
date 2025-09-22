from sqlalchemy import Column, Integer, String, Float, DateTime
from connections import Base
from datetime import datetime

from sqlalchemy import Boolean, Column

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    security_question = Column(String(255))
    security_answer = Column(String(255))
    is_active = Column(Boolean, default=False)  # ✅ New field
    role = Column(String(50), default="user") 


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(120), nullable=True)
    location = Column(String(255), nullable=True)   # ✅ fixed spelling
    ip_address = Column(String(50), nullable=True)
    start_date = Column(DateTime, default=datetime.utcnow)  # subscription start
    end_date = Column(DateTime, nullable=True)             # subscription end
    grace_days = Column(Integer, default=0)                # chosen by customer later
    status = Column(String(20), default="active")          # active, grace, suspended
    popup_shown = Column(Integer, default=0)               # 0=no, 1=yes
    created_at = Column(DateTime, default=datetime.utcnow)
    billing_amount = Column(Float, nullable=False)         # monthly billing amount

