from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# ✅ Updated database URL with SSL
path="mysql+pymysql://root:2480@localhost/wifi"

# Create SQLAlchemy engine
engine= create_engine(path)

# Create session factory
Session = scoped_session(sessionmaker(bind=engine))
SessionLocal = Session

# Declare base class for models
Base = declarative_base()
