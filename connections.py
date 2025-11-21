from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# ✅ Updated database URL with SSL
DATABASE_URL = "postgresql://wifi_yynl_user:KgfI3eoPpQyZbBFyaWzBPkaXjxw9Lbir@dpg-d4g5gr4hg0os73cqr0l0-a.oregon-postgres.render.com:5432/wifi_yynl?sslmode=require"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create session factory
Session = scoped_session(sessionmaker(bind=engine))
SessionLocal = Session

# Declare base class for models
Base = declarative_base()
