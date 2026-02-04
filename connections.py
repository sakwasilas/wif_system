from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

# Use the dedicated database user
DATABASE_URL = "mysql+pymysql://root:2480@localhost/wif"

# Create engine (FIXED)
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,   # ✅ prevents "MySQL server has gone away"
    pool_recycle=280,     # ✅ refresh connections before timeout
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

# Create session factory
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)

# Base class for ORM models
Base = declarative_base()
