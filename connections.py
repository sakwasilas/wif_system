from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# Use the dedicated database user
DATABASE_URL = "mysql+pymysql://root:2480@localhost/wifi"

# Create engine
engine = create_engine(DATABASE_URL, echo=False)  # echo=True for debug

# Create session factory
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# Base class for ORM models
Base = declarative_base()
