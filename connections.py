from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# ✅ Updated database URL
DATABASE_URL = "postgresql://wifi_a7bg_user:hN8kqyFg0ZrdTuYHUz7fCqjpw1K46YI1@dpg-d3n19j15pdvs738juang-a.oregon-postgres.render.com:5432/wifi_a7bg?sslmode=require"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create session factory
Session = scoped_session(sessionmaker(bind=engine))
SessionLocal = Session

# Declare base class for models
Base = declarative_base()

