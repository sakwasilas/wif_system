from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# ✅ New database URL
DATABASE_URL = "postgresql://wifi_4z1b_user:ttgov76KC9Juh3be3GlDyKGCt3cvCmEI@dpg-d3jmlk9r0fns738cjhe0-a.oregon-postgres.render.com:5432/wifi_4z1b?sslmode=require"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create session factory
Session = scoped_session(sessionmaker(bind=engine))
SessionLocal = Session

# Declare base class for models
Base = declarative_base()
