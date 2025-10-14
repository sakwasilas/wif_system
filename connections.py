from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# ✅ Updated database URL
DATABASE_URL = "postgresql://wifi_9u5q_user:8R8b5PIa2TIOsNgURwM9x9nmCl9R937H@dpg-d3n0vdhr0fns739jktvg-a.oregon-postgres.render.com:5432/wifi_9u5q?sslmode=require"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create session factory
Session = scoped_session(sessionmaker(bind=engine))
SessionLocal = Session

# Declare base class for models
Base = declarative_base()
